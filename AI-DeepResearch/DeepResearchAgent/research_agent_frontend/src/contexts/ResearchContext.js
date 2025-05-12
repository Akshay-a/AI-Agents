import React, { createContext, useState, useEffect, useContext, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { startResearchJob, createWebSocketConnection } from '../services/api';

// Create the context
const ResearchContext = createContext();

// Create a provider component
export const ResearchProvider = ({ children }) => {
  // Generate a unique client ID for WebSocket connection
  const [clientId] = useState(() => uuidv4());
  
  // Research state
  const [query, setQuery] = useState('');
  const [jobId, setJobId] = useState(null);
  const [plan, setPlan] = useState([]);
  const [completedTaskIds, setCompletedTaskIds] = useState([]);
  const [report, setReport] = useState('');
  const [status, setStatus] = useState('idle'); // idle, loading, researching, completed, failed
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // connecting, connected, disconnected
  
  // Use a ref for the WebSocket connection to avoid unnecessary re-renders
  const wsConnectionRef = useRef(null);

  // Refs to hold current values of jobId and status for stable callbacks
  const jobIdRef = useRef(jobId);
  useEffect(() => { jobIdRef.current = jobId; }, [jobId]);

  const statusRef = useRef(status);
  useEffect(() => { statusRef.current = status; }, [status]);

  // Handle WebSocket messages using useCallback to avoid recreating the function on every render
  const handleWebSocketMessage = useCallback((data) => {
    console.log('ResearchContext received raw data:', JSON.stringify(data));
    console.log('Received WebSocket message:', data);
          
    // Validate message data
    if (!data || typeof data !== 'object') {
      console.error('Invalid WebSocket message format:', data);
      return;
    }
    
    // Use jobIdRef.current for comparison
    if (data.job_id && data.job_id !== jobIdRef.current && !['active_jobs'].includes(data.type)) {
      console.log(`Ignoring message for job ${data.job_id} (current context job ${jobIdRef.current})`);
      return;
    }

    switch (data.type) {
      case 'task_success':
        setCompletedTaskIds(prev => {
          // Avoid duplicates
          if (prev.includes(data.task_id)) return prev;
          return [...prev, data.task_id];
        });
        break;
      
      case 'job_status':
        // Important: When job_id matches, update main status
        if (data.job_id === jobIdRef.current || !jobIdRef.current) { // Process if it matches current job or if no job is set yet (e.g. initial status from a previous job)
            if (data.status === 'COMPLETED') {
              setStatus('completed');
            } else if (data.status === 'FAILED') {
              setStatus('failed');
              setError(data.detail || 'Research job failed');
            } else if (data.status === 'RUNNING') {
              setStatus('researching');
              // Clear any previous errors when job starts running
              setError(null);
            } else if (data.status === 'PAUSED') {
              setStatus('paused');
            }
        } else {
            console.log(`job_status for ${data.job_id} (status: ${data.status}) ignored as it doesn't match current job ${jobIdRef.current}`);
        }
        break;
      
      case 'final_report':
        try {
          console.log('ResearchContext: Matched final_report case. Data:', JSON.stringify(data));
          // Use jobIdRef.current for comparison
          if (jobIdRef.current && data.job_id !== jobIdRef.current) { 
            //Need to handle this scenario IN FUTURE , prolly add a db call to fetch if socket connection is lost
            console.warn(`ResearchContext: final_report for job ${data.job_id} does not match current context job ${jobIdRef.current}. Ignoring.`);
            return;
          }
          console.log('ResearchContext: job_id matches or initial load. Processing final_report.');
          
          if (typeof data.report_markdown === 'string' && data.report_markdown.trim()) {
            //debug logs to be removed after moved to aws
            console.log('Setting final report:', data.report_markdown.slice(0, 100) + '...');
            console.log('Final report length:', data.report_markdown.length);
            setReport(data.report_markdown);
            setStatus('completed'); // Ensure status is completed when report is set
          } else {
            console.error('Report markdown is invalid:', data.report_markdown);
            // Don't throw error here necessarily, could be an empty report
            // setError('Invalid or empty report_markdown received'); 
            // setStatus('failed');
            if (jobIdRef.current && data.job_id === jobIdRef.current) {
                console.warn("Final report markdown was empty or invalid for the current job. Report not set.")
            }
          }
        } catch (error) {
          console.error('Error processing final report:', error);
          if (jobIdRef.current && data.job_id === jobIdRef.current) { // Only set error if it's for the current job
            setError('Failed to process research report');
            setStatus('failed');
          }
        }
        break;
      
      case 'job_failed':
        // Only update error and status if it's for the current job
        if (data.job_id === jobIdRef.current) {
            setError(data.error_message || 'Research job failed');
            setStatus('failed');
        } else {
            console.log(`job_failed message for ${data.job_id} ignored as it doesn't match current job ${jobIdRef.current}`);
        }
        break;
      
      case 'task_streaming':
        if (data.job_id === jobIdRef.current && data.content) {
          setReport(prev => {
            // Only append if the content is new
            if (!prev.includes(data.content)) {
              return prev + '\n' + data.content;
            }
            return prev;
          });
        }
        break;
        
      case 'active_jobs':
        // Log active jobs for debugging
        console.log('Active jobs:', data.jobs);
        break;
      
      default:
        console.log('Unhandled WebSocket message type:', data.type, data);
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

  // Initialize WebSocket connection
  useEffect(() => {
    console.log("WebSocket Connection useEffect triggered.");
    if (!wsConnectionRef.current) {
      console.log('Creating new WebSocket connection via ResearchContext useEffect...');
      const ws = createWebSocketConnection(
        clientId,
        handleWebSocketMessage, // This function now has a stable reference
        handleReconnect         // This function also has a stable reference
      );
      wsConnectionRef.current = ws;
    }

    return () => {
      console.log("WebSocket Connection useEffect cleanup running.");
      if (wsConnectionRef.current) {
        console.log("Closing WebSocket connection from ResearchContext cleanup.");
        wsConnectionRef.current.close();
        wsConnectionRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]); // Now only depends on clientId (and implicitly stable handlers)
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
      setReport('');
      
      // Ensure WebSocket connection is active
      if (connectionStatus !== 'connected' && wsConnectionRef.current) {
        wsConnectionRef.current.reconnect();
      }
      
      // Start the research job
      const result = await startResearchJob(researchQuery);
      
      if (result.job_id && result.plan) {
        setJobId(result.job_id);
        setPlan(result.plan);
        setStatus('researching');
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error) {
      setError(error.message || 'Failed to start research');
      setStatus('failed');
    }
  };

  // Check if a task is completed
  const isTaskCompleted = (taskId) => {
    return completedTaskIds.includes(taskId);
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
    report,
    status,
    error,
    connectionStatus,
    startResearch,
    isTaskCompleted,
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
