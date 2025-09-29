import React, { useState, useEffect, useCallback } from 'react';
import { FiPlus, FiLink, FiArrowUp } from 'react-icons/fi';
import './index.css'; // Make sure to import the CSS file

// --- API Service Layer ---
const API_BASE_URL = 'http://localhost:8000'; // FastAPI server URL

// Utility function to normalize URL data structure
const normalizeUrls = (urls) => {
  if (!Array.isArray(urls)) return [];

  return urls.map(url => {
    if (typeof url === 'string') {
      return { url, isEnabled: true };
    }
    return url; // Already an object
  });
};

// Utility function to extract domain from URL
const getDomainFromUrl = (url) => {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace('www.', '');
  } catch (error) {
    return url; // Return original URL if parsing fails
  }
};

// Utility function to generate title from message using keyword extraction
const generateTitleFromMessage = (message) => {
  if (!message || typeof message !== 'string') return 'New Chat';

  // Convert to lowercase and split into words
  const words = message.toLowerCase()
    .replace(/[^\w\s]/g, ' ') // Remove punctuation
    .split(/\s+/)
    .filter(word => word.length > 0);

  // Stop words to filter out
  const stopWords = new Set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall',
    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
    'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when', 'where', 'why', 'how'
  ]);

  // Extract meaningful keywords (4-8 characters, not stop words)
  const keywords = words
    .filter(word => word.length >= 3 && word.length <= 10 && !stopWords.has(word))
    .slice(0, 4); // Take first 4 meaningful keywords

  if (keywords.length === 0) {
    return 'New Chat';
  }

  // Create title by capitalizing first letter of each keyword
  const title = keywords
    .map(keyword => keyword.charAt(0).toUpperCase() + keyword.slice(1))
    .join(' ');

  return title.length <= 25 ? title : title.substring(0, 22) + '...';
};

// Utility function to get display text for URL
const getUrlDisplayText = (urlItem) => {
  return getDomainFromUrl(urlItem.url);
};

// CORS test removed to avoid interference

// Make testAPI available globally for debugging
window.testAPI = async () => {
  try {
    console.log('Testing API directly from browser console...');
    const response = await fetch('http://localhost:8000/sessions');
    console.log('Direct fetch response:', response);
    const data = await response.json();
    console.log('Direct fetch data:', data);
    return data;
  } catch (error) {
    console.error('Direct fetch error:', error);
    throw error;
  }
};

const apiService = {
  async createSession() {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) throw new Error('Failed to create session');
      return await response.json();
    } catch (error) {
      console.error('Error creating session:', error);
      throw error;
    }
  },

  async getSessions() {
    try {
      console.log('Making GET request to:', `${API_BASE_URL}/sessions`);
      const response = await fetch(`${API_BASE_URL}/sessions`);
      console.log('Response status:', response.status);
      console.log('Response headers:', response.headers);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Response not ok:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText || 'Failed to fetch sessions'}`);
      }
      const data = await response.json();
      console.log('Response data:', data);
      console.log('Data type:', typeof data);
      console.log('Is array:', Array.isArray(data));
      if (!Array.isArray(data)) {
        console.error('Response is not an array:', data);
        throw new Error('API response is not an array');
      }
      return data;
    } catch (error) {
      console.error('Error fetching sessions:', error);
      throw error;
    }
  },

  async addUrlsToSession(sessionId, urls) {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/urls`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ urls }),
      });
      if (!response.ok) throw new Error('Failed to add URLs to session');
      return await response.json();
    } catch (error) {
      console.error('Error adding URLs to session:', error);
      throw error;
    }
  },

  async getSessionMessages(sessionId) {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`);
      if (!response.ok) throw new Error('Failed to fetch messages');
      return await response.json();
    } catch (error) {
      console.error('Error fetching messages:', error);
      throw error;
    }
  },

  async postMessage(sessionId, message) {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: message }),
      });
      if (!response.ok) throw new Error('Failed to post message');
      return await response.json();
    } catch (error) {
      console.error('Error posting message:', error);
      throw error;
    }
  },

  async updateSession(sessionId, updateData) {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      });
      if (!response.ok) throw new Error('Failed to update session');
      return await response.json();
    } catch (error) {
      console.error('Error updating session:', error);
      throw error;
    }
  },
};

// --- Reusable Toggle Switch Component ---
const ToggleSwitch = ({ isEnabled, onToggle }) => {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" checked={isEnabled} onChange={onToggle} className="sr-only peer" />
      <div className="w-11 h-6 bg-gray-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-black"></div>
    </label>
  );
};

// --- URL Input Modal Component ---
const UrlInputModal = ({ isVisible, value, onChange, onAdd, onCancel, loading }) => {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Add URL to Session</h3>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="https://example.com"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onAdd();
            } else if (e.key === 'Escape') {
              onCancel();
            }
          }}
          autoFocus
        />
        <div className="flex justify-end space-x-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={onAdd}
            disabled={loading || !value.trim()}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Adding...' : 'Add URL'}
          </button>
        </div>
      </div>
    </div>
  );
};

// --- URL Pills Component ---
const UrlPills = ({ urls, onRemove }) => {
  if (!urls || urls.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-4 px-6">
      {urls.map((urlItem, index) => (
        <div
          key={index}
          className="inline-flex items-center bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm border border-blue-200"
        >
          <span className="truncate max-w-xs" title={urlItem.url}>{getUrlDisplayText(urlItem)}</span>
          <button
            onClick={() => onRemove && onRemove(index)}
            className="ml-2 text-blue-600 hover:text-blue-800 w-4 h-4 flex items-center justify-center rounded-full hover:bg-blue-200"
            title="Remove URL"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};


// --- Main App Component ---
function App() {
  console.log('App component rendering...');

  // Session management state
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);

  // UI state
  const [urls, setUrls] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');

  // URL input modal state
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlInputValue, setUrlInputValue] = useState('');
  const [urlPills, setUrlPills] = useState([]);

  // Loading and error states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load sessions from backend
  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('Loading sessions from backend...');
      const sessionList = await apiService.getSessions();

      // Sort sessions by creation date (newest first) and set
      const sortedSessions = sessionList ? [...sessionList].sort((a, b) => {
        // Assuming sessions have a created_at or similar field, otherwise use ID
        return b.id - a.id; // Higher ID = newer session
      }) : [];

      setSessions(sortedSessions);

      // Auto-select the first session if none is currently selected
      if (sessionList && sessionList.length > 0 && !currentSession) {
        const firstSession = sessionList[0];
        setCurrentSession(firstSession);

        // Load messages for the auto-selected session
        loadSessionMessages(firstSession.id).then(() => {
          const normalizedUrls = normalizeUrls(firstSession.urls || []);
          setUrls(normalizedUrls);
          setUrlPills(normalizedUrls);
        }).catch(error => {
          console.error('Failed to load messages for auto-selected session:', error);
          // Still set URLs even if message loading fails
          const normalizedUrls = normalizeUrls(firstSession.urls || []);
          setUrls(normalizedUrls);
          setUrlPills(normalizedUrls);
        });
      }
    } catch (error) {
      console.error('Error loading sessions:', error);
      setError(`Failed to load sessions: ${error.message}. Please make sure the backend server is running.`);
    } finally {
      setLoading(false);
    }
  }, [currentSession]);

  // Load sessions on component mount - only once
  useEffect(() => {
    loadSessions();
  }, []); // Only run once on mount


  // Clear current session (start new chat)
  const createNewSession = async () => {
    try {
      setLoading(true);
      setError(null);

      // Always clear current state first
      setCurrentSession(null);
      setMessages([]);
      setUrls([]);
      setUrlPills([]);

      // Create a new session for immediate use
      const newSession = await apiService.createSession();
      setCurrentSession(newSession);
    } catch (error) {
      setError('Failed to start new chat.');
      console.error('Error starting new chat:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load messages for a session
  const loadSessionMessages = async (sessionId) => {
    try {
      setLoading(true);
      setError(null);
      const sessionMessages = await apiService.getSessionMessages(sessionId);
      setMessages(sessionMessages || []);
    } catch (error) {
      setError('Failed to load messages.');
      console.error('Error loading messages:', error);
    } finally {
      setLoading(false);
    }
  };

  // Handle session selection
  const handleSessionSelect = async (session) => {
    if (!session || !session.id) return;

    // Clear current state first
    setMessages([]);
    setUrls([]);
    setUrlPills([]);

    setCurrentSession(session);

    // Load messages for the selected session
    await loadSessionMessages(session.id);

    // Extract URLs from session for display
    const sessionUrls = normalizeUrls(session.urls || []);
    setUrls(sessionUrls);
    setUrlPills(sessionUrls);
  };

  // Handler for the toggle switch in the sidebar
  const handleToggleUrl = (indexToToggle) => {
    const updatedUrls = urls.map((urlItem, index) =>
      index === indexToToggle ? { ...urlItem, isEnabled: !urlItem.isEnabled } : urlItem
    );
    setUrls(updatedUrls);
  };

  // Handler for adding URL from the input modal
  const handleUrlModalAdd = async () => {
    const url = urlInputValue.trim();

    if (!url) {
      setError('Please enter a URL to add to the session.');
      return;
    }

    // Simple URL validation
    const urlPattern = /^https?:\/\/.+/i;
    if (!urlPattern.test(url)) {
      setError('Please enter a valid URL (starting with http:// or https://).');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      let sessionToUse = currentSession;

      // If no current session, create one first
      if (!currentSession) {
        const newSession = await apiService.createSession();
        setCurrentSession(newSession);
        setMessages([]);
        setUrls([]);
        setUrlPills([]);
        sessionToUse = newSession;
        // Don't add to sessions list yet - only add when there's actual content
      }

      // Add URL to current session
      await apiService.addUrlsToSession(sessionToUse.id, [url]);

      // Update both URL pills and sidebar URLs
      const newUrlPill = { url, isEnabled: true };
      setUrlPills(prev => [...prev, newUrlPill]);
      setUrls(prev => [...prev, newUrlPill]);

      // Update the session in the sessions list with the new URLs
      setSessions(prev => prev.map(s =>
        s.id === sessionToUse.id
          ? { ...s, urls: [...(s.urls || []), url] }
          : s
      ));

      // If this is a newly created session, also add it to the sessions list
      if (sessionToUse && !sessions.find(s => s.id === sessionToUse.id)) {
        setSessions(prev => [sessionToUse, ...prev]);
      }

      // Clear modal state
      setUrlInputValue('');
      setShowUrlInput(false);

    } catch (error) {
      setError(`Failed to add URL: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handler for canceling URL input modal
  const handleUrlModalCancel = () => {
    setUrlInputValue('');
    setShowUrlInput(false);
    setError(null);
  };

  // Filter sessions to only show those with content
  const getSessionsWithContent = () => {
    return sessions.filter(session => {
      // Show session if it has URLs (primary indicator of content)
      // We don't check messages here since they're not loaded for all sessions
      return session.urls && session.urls.length > 0;
    });
  };

  // Handler for removing URL from pills
  const handleRemoveUrlPill = (indexToRemove) => {
    // Remove from both urlPills and urls (sidebar)
    setUrlPills(prev => prev.filter((_, index) => index !== indexToRemove));
    setUrls(prev => prev.filter((_, index) => index !== indexToRemove));
  };

  // Handler for plus button click - show URL input modal
  const handlePlusClick = () => {
    console.log('Plus button clicked - showing URL input modal');
    setShowUrlInput(true);
    setUrlInputValue('');
    setError(null);
  };

  // Handler for form submission (send message to backend)
  const handleSubmit = async (e) => {
    e.preventDefault();
    const userMessage = inputValue.trim();
    if (userMessage === '') return;

    // Simple URL validation for questions vs URLs
    const urlPattern = /^https?:\/\/.+/i;

    try {
      setLoading(true);
      setError(null);

      let sessionToUse = currentSession;

      // If no current session, create one first
      if (!currentSession) {
        const newSession = await apiService.createSession();
        setCurrentSession(newSession);
        setMessages([]);
        setUrls([]);
        setUrlPills([]);
        sessionToUse = newSession;
        // Add to sessions list since user is actively using it
        if (!sessions.find(s => s.id === newSession.id)) {
          setSessions(prev => [newSession, ...prev]);
        }
      }

      // Add user message to local state immediately for better UX
      const newUserMessage = {
        id: Date.now(), // Temporary ID
        role: 'user',
        content: userMessage,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, newUserMessage]);

      // Generate title from first message if this is a new conversation
      const isFirstMessage = !currentSession || currentSession.title === 'New Session';
      if (isFirstMessage && !urlPattern.test(userMessage)) {
        const generatedTitle = generateTitleFromMessage(userMessage);

        // Update the session title in the frontend state
        if (currentSession) {
          const updatedSession = { ...currentSession, title: generatedTitle };
          setCurrentSession(updatedSession);

          // Also update in the sessions list
          setSessions(prev => prev.map(session =>
            session.id === currentSession.id
              ? updatedSession
              : session
          ));

          // Optionally sync title to backend (non-blocking)
          apiService.updateSession(currentSession.id, { title: generatedTitle })
            .catch(error => {
              console.warn('Failed to sync title to backend:', error);
              // Title still works in frontend even if backend sync fails
            });
        }
      }

      if (!!urlPattern.test(userMessage)) {
        // If it's a URL, add it to the session and show it
        await apiService.addUrlsToSession(sessionToUse.id, [userMessage]);
        setUrls(prev => [...prev, { url: userMessage, isEnabled: true }]);
        setUrlPills(prev => [...prev, { url: userMessage, isEnabled: true }]);
      } else {
        // If it's a question, post it to get AI response
        const response = await apiService.postMessage(sessionToUse.id, userMessage);

        // Add AI response to messages
        const newAiMessage = {
          id: response.id,
          role: 'assistant',
          content: response.content,
          created_at: response.created_at
        };
        setMessages(prev => [...prev, newAiMessage]);
      }

      setInputValue('');
    } catch (error) {
      setError('Failed to process message.');
      console.error('Error processing message:', error);
      // Remove the optimistic message if there was an error
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      {/* URL Input Modal */}
      <UrlInputModal
        isVisible={showUrlInput}
        value={urlInputValue}
        onChange={setUrlInputValue}
        onAdd={handleUrlModalAdd}
        onCancel={handleUrlModalCancel}
        loading={loading}
      />

      {/* --- Sidebar --- */}
      <aside className="w-72 bg-white flex flex-col border-r border-gray-200">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-xl font-bold text-black">scraperBot</h1>
        </div>

        <div className="p-4">
          <button
            onClick={createNewSession}
            disabled={loading}
            className="w-full bg-black text-white py-2 px-4 rounded-md flex items-center justify-center text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <FiPlus className="mr-2" /> New chat
          </button>
        </div>

        <div className="px-4 mt-4 flex-grow overflow-y-auto">
          {/* Links Section */}
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-black mb-3 flex items-center">
              <FiLink className="mr-2" /> Links
            </h2>
            <div className="space-y-3">
              {loading && (
                <div className="flex items-center justify-center py-2">
                  <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin mr-2"></div>
                  <p className="text-sm text-gray-500">Processing URL...</p>
                </div>
              )}
              {urls.length > 0 ? (
                urls.map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-2 rounded border border-gray-100 hover:bg-gray-50">
                    <div className="flex-1 min-w-0">
                      <span
                        className={`text-sm block truncate ${item.isEnabled ? 'text-gray-800' : 'text-gray-400 line-through'}`}
                        title={item.url} // Show full URL on hover
                      >
                        {getUrlDisplayText(item)}
                      </span>
                    </div>
                    <ToggleSwitch isEnabled={item.isEnabled} onToggle={() => handleToggleUrl(index)} />
                  </div>
                ))
              ) : (
                <div className="text-center py-4">
                  <p className="text-sm text-gray-400 mb-2">No URLs added yet.</p>
                  <p className="text-xs text-gray-300">Type a URL and click the + button to add it</p>
                </div>
              )}
            </div>
          </div>

          {/* Chats Section */}
          <div>
            <h2 className="text-sm font-semibold text-black mb-3">Chats</h2>
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin mr-2"></div>
                <p className="text-sm text-gray-400">Loading sessions...</p>
              </div>
            ) : error ? (
              <div className="text-center py-4">
                <p className="text-sm text-red-400 mb-2">{error}</p>
                <button
                  onClick={loadSessions}
                  className="text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 px-2 py-1 rounded"
                >
                  Retry
                </button>
              </div>
            ) : getSessionsWithContent().length > 0 ? (
              <ul className="space-y-2">
                {getSessionsWithContent().map((session) => (
                  <li
                    key={session.id}
                    onClick={() => handleSessionSelect(session)}
                    className={`text-sm cursor-pointer hover:bg-gray-50 p-2 rounded transition-colors ${
                      currentSession && currentSession.id === session.id
                        ? 'bg-blue-50 text-blue-700 border-l-2 border-blue-500'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate flex-1">{session.title}</span>
                      <span className="text-xs text-gray-400 ml-2">
                        {session.urls ? session.urls.length : 0} URLs
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No sessions yet. Click "New chat" to get started.</p>
            )}
          </div>
        </div>

        {/* User Profile Section */}
        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center">
            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center font-bold text-gray-500">
              A
            </div>
            <div className="ml-3">
              <p className="text-sm font-semibold text-black">{process.env.REACT_APP_USER_NAME || 'Akshay Apsingi'}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* --- Main Chat Area --- */}
      <main className="flex-1 flex flex-col">
        {/* Error Banner */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 text-red-700 px-4 py-3 mx-4 mt-4 rounded">
            <div className="flex justify-between items-center">
              <span className="text-sm">{error}</span>
              <button
                onClick={() => setError(null)}
                className="text-red-500 hover:text-red-700 text-lg leading-none ml-2"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Messages Area - Always scrollable */}
        <div className="flex-1 p-6 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-600">
              <div className="text-center">
                <h2 className="text-3xl mb-4 text-gray-800">Where should we begin?</h2>
                <p className="text-gray-500 mb-8">Start by adding URLs to a session or asking a question about your content.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, index) => (
                <div key={msg.id || index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-lg ${msg.role === 'user' ? 'ml-auto' : 'mr-auto'}`}>
                    <div className={`p-3 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-gray-800 text-white'
                        : 'bg-gray-100 text-gray-800 border border-gray-200'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                    <p className={`text-xs mt-1 px-2 ${
                      msg.role === 'user' ? 'text-right text-gray-400' : 'text-left text-gray-500'
                    }`}>
                      {new Date(msg.created_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Fixed Input Area at Bottom */}
        <div className="p-6 border-t border-gray-200 bg-white">
          <div className="flex justify-center">
            <div className="w-full max-w-2xl">
              <form onSubmit={handleSubmit} className="chat-input-container flex items-center p-1 bg-white rounded-full shadow-sm border border-gray-200">
                <button
                  type="button"
                  onClick={() => {
                    console.log('Plus button clicked!');
                    handlePlusClick();
                  }}
                  disabled={loading}
                  className="plus-button w-10 h-10 rounded-full flex items-center justify-center mr-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 transition-colors"
                  title="Add URL to session"
                >
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <FiPlus className="text-gray-600 w-4 h-4" />
                  )}
                </button>
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Ask anything or paste a URL..."
                  className="flex-1 py-3 px-4 text-sm bg-transparent border-none focus:outline-none placeholder-gray-400"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !inputValue.trim()}
                  className="send-button w-10 h-10 rounded-full flex items-center justify-center ml-2 shadow-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Send message"
                >
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <FiArrowUp className="w-4 h-4 text-white" />
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
