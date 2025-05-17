import React, { createContext, useState, useEffect, useContext, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { startResearchJob, createWebSocketConnection, fetchHistory, fetchJobReport } from '../services/api';

// Create the context
const ResearchContext = createContext();

// Create a provider component
export const ResearchProvider = ({ children }) => {
  // Generate a unique client ID for WebSocket connection/communication as we will pass this in headers
  const [clientId] = useState(() => uuidv4());
  
  // Research state
  const [query, setQuery] = useState('');
  const [jobId, setJobId] = useState(null);
  const [plan, setPlan] = useState([]);
  const [completedTaskIds, setCompletedTaskIds] = useState([]);
  const [taskStatuses, setTaskStatuses] = useState({}); // Store task statuses: { taskId: 'COMPLETED'|'ERROR'|'PENDING' }
  const [taskErrors, setTaskErrors] = useState({}); // Store error messages for failed tasks
  const [report, setReport] = useState('');
  const [status, setStatus] = useState('idle'); // idle, loading, researching, completed, failed
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // connecting, connected, disconnected
  const [currentStatusMessage, setCurrentStatusMessage] = useState(''); // Track current job progress message
  
  // New state for chat-like interface
  const [currentChatMessages, setCurrentChatMessages] = useState([]);
  const [historyList, setHistoryList] = useState([]);
  
  // Use a ref for the WebSocket connection to avoid unnecessary re-renders
  const wsConnectionRef = useRef(null);

  // Refs to hold current values of jobId and status for stable callbacks
  const jobIdRef = useRef(jobId);
  useEffect(() => { jobIdRef.current = jobId; }, [jobId]);

  const statusRef = useRef(status);
  useEffect(() => { statusRef.current = status; }, [status]);

  // Fetch history on initial load
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const history = await fetchHistory();
        // Ensure all history items have a valid queryTitle
        const sanitizedHistory = history.map(item => ({
          ...item,
          queryTitle: item.queryTitle || "Untitled Research"
        }));
        setHistoryList(sanitizedHistory);
      } catch (error) {
        console.error('Failed to load history:', error);
        // Set empty history list on error instead of leaving it undefined
        setHistoryList([]);
      }
    };
    
    loadHistory();
  }, []);

  // Handle WebSocket messages using useCallback to avoid recreating the function on every render
  const handleWebSocketMessage = useCallback((data) => {
    console.log('ResearchContext received raw data:', JSON.stringify(data));
    console.log('Received WebSocket message:', data);
          
    // Validate message data
    if (!data || typeof data !== 'object') {
      console.error('Invalid WebSocket message format:', data);
      return;
    }
    
    // Extract payload if present
    const messageData = data.payload || data;
    const messageType = data.type;
    
    // Check job_id match with current context
    const jobIdInMessage = messageData.job_id;
    
    // If we don't have a jobId set yet but we're receiving messages for a job,
    // and we're in a loading or researching state, let's adopt that job ID
    if (jobIdInMessage && !jobIdRef.current && (statusRef.current === 'loading' || statusRef.current === 'researching')) {
      console.log(`Adopting job ID ${jobIdInMessage} as the current context job`);
      setJobId(jobIdInMessage);
      // Update the ref immediately to ensure subsequent message handling works
      jobIdRef.current = jobIdInMessage;
    }
    
    // Now check if this message is for our current job
    if (jobIdInMessage && jobIdInMessage !== jobIdRef.current && !['active_jobs'].includes(messageType)) {
      console.log(`Ignoring message for job ${jobIdInMessage} (current context job ${jobIdRef.current})`);
      return;
    }

    switch (messageType) {
      case 'job_progress':
        // Handle job progress messages
        console.log('Processing job_progress message:', messageData.message);
        setCurrentStatusMessage(messageData.message || '');
        
        // If this is the first message about the research plan being generated, make sure we're in researching state
        if (messageData.message && messageData.message.includes('Generating research plan')) {
          setStatus('researching');
        }
        break;
        
      case 'task_failed':
        // Handle task failure messages
        console.log('Processing task_failed message:', messageData);
        if (messageData.error_message) {
          setError(messageData.error_message);
        }
        
        // Update task status to ERROR
        if (messageData.task_id) {
          setTaskStatuses(prev => ({
            ...prev,
            [messageData.task_id]: 'ERROR'
          }));
          
          // Store the error message for this task
          setTaskErrors(prev => ({
            ...prev,
            [messageData.task_id]: messageData.error_message || 'Task failed'
          }));
        }
        break;
        
      case 'task_success':
        // Update completedTaskIds for backward compatibility
        setCompletedTaskIds(prev => {
          // Avoid duplicates
          if (prev.includes(messageData.task_id)) return prev;
          return [...prev, messageData.task_id];
        });
        
        // Update task status to COMPLETED
        if (messageData.task_id) {
          setTaskStatuses(prev => ({
            ...prev,
            [messageData.task_id]: 'COMPLETED'
          }));
        }
        break;
      
      case 'job_status':
        // Important: When job_id matches, update main status
        if (jobIdInMessage === jobIdRef.current || !jobIdRef.current) { // Process if it matches current job or if no job is set yet
            if (messageData.status === 'COMPLETED') {
              setStatus('completed');
            } else if (messageData.status === 'FAILED') {
              setStatus('failed');
              setError(messageData.detail || 'Research job failed');
              
              // Add error message to chat
              setCurrentChatMessages(prev => [
                ...prev,
                { 
                  type: 'ai', 
                  content: messageData.detail || 'Research job failed', 
                  isError: true 
                }
              ]);
            } else if (messageData.status === 'RUNNING') {
              setStatus('researching');
              // Clear any previous errors when job starts running
              setError(null);
            } else if (messageData.status === 'PAUSED') {
              setStatus('paused');
            }
        } else {
            console.log(`job_status for ${jobIdInMessage} (status: ${messageData.status}) ignored as it doesn't match current job ${jobIdRef.current}`);
        }
        break;
      
      case 'final_report':
        try {
          console.log('ResearchContext: Matched final_report case. Data:', JSON.stringify(messageData));
          // Use jobIdRef.current for comparison
          if (jobIdRef.current && jobIdInMessage !== jobIdRef.current) { 
            console.warn(`ResearchContext: final_report for job ${jobIdInMessage} does not match current context job ${jobIdRef.current}. Ignoring.`);
            return;
          }
          console.log('ResearchContext: job_id matches or initial load. Processing final_report.');
          
          // Check for report_markdown in both direct and payload structure
          const reportMarkdown = messageData.report_markdown;
          
          if (typeof reportMarkdown === 'string' && reportMarkdown.trim()) {
            console.log('Setting final report:', reportMarkdown.slice(0, 100) + '...');
            console.log('Final report length:', reportMarkdown.length);
            setReport(reportMarkdown);
            setStatus('completed');
            
            // Add report to chat messages
            setCurrentChatMessages(prev => [
              ...prev, 
              { type: 'ai', content: reportMarkdown }
            ]);
            
            // Update history list with the new job
            const newHistoryItem = {
              jobId: jobIdInMessage,
              queryTitle: query || "Untitled Research",
              timestamp: new Date().toISOString()
            };
            
            setHistoryList(prev => [newHistoryItem, ...prev]);
          } else {
            console.error('Report markdown is invalid:', reportMarkdown);
            if (jobIdRef.current && jobIdInMessage === jobIdRef.current) {
                console.warn("Final report markdown was empty or invalid for the current job. Report not set.")
            }
          }
        } catch (error) {
          console.error('Error processing final report:', error);
          if (jobIdRef.current && jobIdInMessage === jobIdRef.current) { // Only set error if it's for the current job
            setError('Failed to process research report');
            setStatus('failed');
            
            // Add error to chat
            setCurrentChatMessages(prev => [
              ...prev,
              { 
                type: 'ai', 
                content: 'Failed to process research report', 
                isError: true 
              }
            ]);
          }
        }
        break;
      
      case 'job_failed':
        // Only update error and status if it's for the current job
        if (jobIdInMessage === jobIdRef.current) {
            // Get error message from appropriate property
            const errorMessage = messageData.error_message || messageData.error || 'Research job failed';
            console.log('Setting error state from job_failed message:', errorMessage);
            setError(errorMessage);
            setStatus('failed');
            
            // Add error to chat
            setCurrentChatMessages(prev => [
              ...prev,
              { 
                type: 'ai', 
                content: errorMessage, 
                isError: true 
              }
            ]);
        } else {
            console.log(`job_failed message for ${jobIdInMessage} ignored as it doesn't match current job ${jobIdRef.current}`);
        }
        break;
      
      case 'task_streaming':
        if (jobIdInMessage === jobIdRef.current && messageData.content) {
          setReport(prev => {
            // Only append if the content is new
            if (!prev.includes(messageData.content)) {
              return prev + '\n' + messageData.content;
            }
            return prev;
          });
        }
        break;
        
      case 'active_jobs':
        // Log active jobs for debugging
        console.log('Active jobs:', messageData.jobs);
        break;
      
      default:
        console.log('Unhandled WebSocket message type:', messageType, data);
    }
  }, []); // REMOVED jobId from dependencies, handlers use refs now

  // Handle WebSocket reconnection
  const handleReconnect = useCallback((attemptCount) => {
    setConnectionStatus('connecting');
    console.log(`WebSocket reconnection attempt ${attemptCount}`);
    
    // Use statusRef.current
    if (statusRef.current === 'researching') {
      setError(`Connection lost. Reconnecting (attempt ${attemptCount})...`);
    }
  }, []); // REMOVED status from dependencies, handlers use refs now

  // Initialize WebSocket connection - only create/destroy on mount/unmount
  useEffect(() => {
    console.log("WebSocket Connection useEffect triggered.");
    const createConnection = () => {
      console.log('Creating new WebSocket connection via ResearchContext useEffect...');
      const ws = createWebSocketConnection(
        clientId,
        handleWebSocketMessage, // This function now has a stable reference
        handleReconnect,        // This function also has a stable reference
        (isConnected) => {      // Add connection status callback
          setConnectionStatus(isConnected ? 'connected' : 'connecting');
        }
      );
      wsConnectionRef.current = ws;
    };

    if (!wsConnectionRef.current) {
      createConnection();
    }

    // Try to reconnect if no connection is present
    const checkConnectionInterval = setInterval(() => {
      if (wsConnectionRef.current && wsConnectionRef.current.getWebSocket()?.readyState !== WebSocket.OPEN) {
        console.log("WebSocket connection check: Connection not open, attempting to reconnect...");
        createConnection();
      }
    }, 10000); // Check every 10 seconds

    // Only run cleanup when component unmounts, not on every render
    return () => {
      console.log("WebSocket Connection useEffect cleanup running - COMPONENT UNMOUNTING.");
      clearInterval(checkConnectionInterval);
      if (wsConnectionRef.current) {
        console.log("Closing WebSocket connection from ResearchContext cleanup.");
        wsConnectionRef.current.close();
        wsConnectionRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty dependency array - only run on mount/unmount
  // Note: ESLint might complain about handleWebSocketMessage and handleReconnect missing, 
  // but they are stable due to their own empty dependency arrays in useCallback.
  // If ESLint is strict, they can be added, as their references won't change.

  // Start a new research job
  const startResearch = async (researchQuery) => {
    try {
      // Reset state
      setQuery(researchQuery);
      setStatus('loading');
      setError(null);
      setJobId(null);
      setPlan([]);
      setCompletedTaskIds([]);
      setTaskStatuses({});
      setTaskErrors({});
      setReport('');
      
      // Add user query to chat messages
      setCurrentChatMessages(prev => [
        ...prev,
        { type: 'user', content: researchQuery }
      ]);
      
      // Ensure WebSocket connection is active
      if (connectionStatus !== 'connected' && wsConnectionRef.current) {
        wsConnectionRef.current.reconnect();
      }
      
      // Start the research job - pass clientId to match WebSocket connection
      console.log(`Starting research with query "${researchQuery}" and client ID "${clientId}"`);
      const result = await startResearchJob(researchQuery, clientId);
      
      if (result.job_id && result.plan) {
        setJobId(result.job_id);
        setPlan(result.plan);
        setStatus('researching');
        console.log(`Research job ${result.job_id} started successfully with ${result.plan.length} planned tasks`);
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error) {
      console.error('Failed to start research:', error);
      setError(error.message || 'Failed to start research');
      setStatus('failed');
      
      // Add error to chat messages
      setCurrentChatMessages(prev => [
        ...prev,
        { 
          type: 'ai', 
          content: error.message || 'Failed to start research', 
          isError: true 
        }
      ]);
    }
  };

  // Clear current chat and reset state
  const clearCurrentChat = () => {
    setQuery('');
    setJobId(null);
    setPlan([]);
    setCompletedTaskIds([]);
    setTaskStatuses({});
    setTaskErrors({});
    setReport('');
    setStatus('idle');
    setError(null);
    setCurrentStatusMessage('');
    setCurrentChatMessages([]);
  };
  
  // Load a history item by job ID
  const loadHistoryItem = async (jobId) => {
    try {
      // First find the history item to get the query
      const historyItem = historyList.find(item => item.jobId === jobId);
      
      if (!historyItem) {
        throw new Error('History item not found');
      }
      
      // Ensure queryTitle is valid
      const safeQueryTitle = historyItem.queryTitle || "Untitled Research";
      
      // Set the query from history
      setQuery(safeQueryTitle);
      
      // Reset other state
      setJobId(jobId);
      setPlan([]);
      setCompletedTaskIds([]);
      setTaskStatuses({});
      setTaskErrors({});
      setStatus('loading');
      setError(null);
      
      // Start with just the user query in chat
      setCurrentChatMessages([
        { type: 'user', content: safeQueryTitle }
      ]);
      
      // Fetch the report for this job
      const report = await fetchJobReport(jobId);
      
      if (report) {
        setReport(report);
        setStatus('completed');
        
        // Add report to chat messages
        setCurrentChatMessages(prev => [
          ...prev,
          { type: 'ai', content: report }
        ]);
      } else {
        throw new Error('Failed to load report');
      }
    } catch (error) {
      console.error('Failed to load history item:', error);
      setError(error.message || 'Failed to load history item');
      setStatus('failed');
      
      // Add error to chat messages
      setCurrentChatMessages(prev => [
        ...prev,
        { 
          type: 'ai', 
          content: error.message || 'Failed to load history item', 
          isError: true 
        }
      ]);
    }
  };

  // Check if a task is completed
  const isTaskCompleted = (taskId) => {
    return completedTaskIds.includes(taskId) || taskStatuses[taskId] === 'COMPLETED';
  };
  
  // Get the status of a task
  const getTaskStatus = (taskId) => {
    return taskStatuses[taskId] || 'PENDING';
  };
  
  // Get the error message for a task
  const getTaskError = (taskId) => {
    return taskErrors[taskId] || null;
  };
  
  // Send a message through the WebSocket
  const sendMessage = (message) => {
    if (wsConnectionRef.current) {
      return wsConnectionRef.current.sendMessage(message);
    }
    return false;
  };

  // Context value
  const value = {
    query,
    jobId,
    plan,
    completedTaskIds,
    taskStatuses,
    taskErrors,
    report,
    status,
    error,
    connectionStatus,
    currentStatusMessage,
    currentChatMessages,
    historyList,
    startResearch,
    clearCurrentChat,
    loadHistoryItem,
    isTaskCompleted,
    getTaskStatus,
    getTaskError,
    sendMessage,
  };

  return (
    <ResearchContext.Provider value={value}>
      {children}
    </ResearchContext.Provider>
  );
};

// Custom hook to use the research context
export const useResearch = () => {
  const context = useContext(ResearchContext);
  if (!context) {
    throw new Error('useResearch must be used within a ResearchProvider');
  }
  return context;
};
