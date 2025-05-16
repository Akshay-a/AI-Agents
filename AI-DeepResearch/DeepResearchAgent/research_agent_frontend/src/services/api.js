/**
 * API service for communicating with the backend
 */

// Backend API URL - can be moved to environment variables later
const API_BASE_URL = 'http://localhost:8000';

/**
 * Start a new research job
 * @param {string} query - The research query
 * @param {string} clientId - Unique client identifier
 * @returns {Promise<Object>} - The response containing job_id and plan
 */
export const startResearchJob = async (query, clientId) => {
  try {
    console.log(`Starting research job with query: "${query}" and client ID: ${clientId}`);
    const response = await fetch(`${API_BASE_URL}/start_job`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Client-ID': clientId, // Send client ID in header to match WebSocket connection
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to start research job: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error starting research job:', error);
    throw error;
  }
};

/**
 * Create a WebSocket connection to the backend with auto-reconnect functionality
 * @param {string} clientId - Unique client identifier
 * @param {Function} onMessage - Callback function for handling messages
 * @param {Function} onReconnect - Optional callback when reconnection happens
 * @param {Function} onConnectionStatus - Optional callback for connection status updates
 * @returns {Object} - WebSocket connection with additional control methods
 */
export const createWebSocketConnection = (clientId, onMessage, onReconnect, onConnectionStatus) => {
  let ws = null;
  let reconnectAttempts = 0;
  let scheduledReconnectTimer = null; 
  let isConnecting = false;
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY_MS = 3000;
  
  const clearScheduledReconnect = () => {
    if (scheduledReconnectTimer) {
      clearTimeout(scheduledReconnectTimer);
      scheduledReconnectTimer = null;
    }
  };

  const scheduleReconnect = () => {
    clearScheduledReconnect();

    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('Max reconnection attempts reached. Not scheduling new reconnect.');
      return;
    }

    scheduledReconnectTimer = setTimeout(() => {
        reconnectAttempts++;
        console.log(`Attempting to reconnect via schedule (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
        connect();

        if (onReconnect && typeof onReconnect === 'function') {
            onReconnect(reconnectAttempts);
        }
    }, RECONNECT_DELAY_MS);
  };
  
  const connect = () => {
    if (isConnecting) {
      console.log('Connection attempt already in progress (isConnecting flag).');
      return;
    }

    if (ws && ws.readyState !== WebSocket.CLOSED) {
      console.log(`Attempting to close existing WebSocket (readyState: ${ws.readyState}) before creating a new one.`);
      try {
        ws.onopen = null; 
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null; 
        ws.close(1000, "Client initiated new connection"); 
      } catch (e) {
        console.warn('Error trying to close previous WebSocket connection:', e);
      }
    }
    ws = null; 
    isConnecting = true;
    
    clearScheduledReconnect();
    
    console.log(`Creating new WebSocket to ws://localhost:8000/ws/${clientId}`);
    try {
      ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
    } catch (error) {
      console.error("Error creating WebSocket object:", error);
      isConnecting = false;
      scheduleReconnect();
      return;
    }
    
    ws.onopen = () => {
      console.log('WebSocket connection established');
      isConnecting = false;
      reconnectAttempts = 0; 
      // Notify about connection status
      if (onConnectionStatus && typeof onConnectionStatus === 'function') {
        onConnectionStatus(true);
      }
    };
    
    ws.onmessage = (event) => {
      try {
        const rawData = event.data;
        console.log('Raw WebSocket message received:', rawData.substring(0, 200) + '...');
        
        const data = JSON.parse(rawData);
        console.log('Parsed WebSocket message type:', data.type);
        console.log('Parsed WebSocket message structure:', JSON.stringify(data, null, 2));
        
        if (onMessage && typeof onMessage === 'function') {
          onMessage(data);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error, event.data?.substring(0, 200));
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (ws && ws.readyState !== WebSocket.OPEN) {
        isConnecting = false;
      }
    };
    
    ws.onclose = (event) => {
      console.log(`WebSocket connection closed: ${event.code} ${event.reason}`);
      isConnecting = false; 
      
      // Notify about connection status
      if (onConnectionStatus && typeof onConnectionStatus === 'function') {
        onConnectionStatus(false);
      }

      if (event.code !== 1000) {
        console.log("Connection closed unexpectedly. Scheduling reconnect.");
        scheduleReconnect();
      } else {
        console.log("WebSocket closed cleanly (code 1000). No automatic reconnect from onclose.");
      }
    };
  };
  
  connect();
  
  return {
    getWebSocket: () => ws,
    reconnect: () => {
      console.log("External reconnect() called.");
      reconnectAttempts = 0;
      clearScheduledReconnect();
      connect();
    },
    close: () => {
      console.log("External close() called.");
      clearScheduledReconnect();
      if (ws) {
        console.log(`Closing WebSocket (readyState: ${ws.readyState}) due to external close call.`);
        ws.onclose = null;
        ws.close(1000, 'Closed by client');
        ws = null;
      }
      isConnecting = false;
    },
    sendMessage: (message) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(typeof message === 'string' ? message : JSON.stringify(message));
        return true;
      }
      return false;
    }
  };
};
