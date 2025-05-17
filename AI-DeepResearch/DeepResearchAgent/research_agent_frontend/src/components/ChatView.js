import React, { useRef, useEffect } from 'react';
import './ChatView.css';
import QueryInput from './QueryInput';
import { useResearch } from '../contexts/ResearchContext';
import { FiAlertCircle } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ChatView = () => {
  const { query, report, status, error, currentChatMessages } = useResearch();
  const messagesEndRef = useRef(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [currentChatMessages]);

  return (
    <main className="chat-view">
      <div className="messages-container">
        {currentChatMessages.length === 0 ? (
          <div className="welcome-message">
            <h1>Welcome to DeepResearch</h1>
            <p>Your AI-powered research assistant</p>
          </div>
        ) : (
          currentChatMessages.map((message, index) => (
            <div 
              key={index} 
              className={`message ${message.type === 'user' ? 'user-message' : 'ai-message'}`}
            >
              <div className="message-avatar">
                {message.type === 'user' ? '👤' : '🤖'}
              </div>
              <div className="message-content">
                {message.type === 'user' ? (
                  <p>{message.content}</p>
                ) : message.isError ? (
                  <div className="error-message">
                    <FiAlertCircle size={20} />
                    <p>{message.content}</p>
                  </div>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          ))
        )}
        
        {/* Loading indicator */}
        {status === 'loading' || status === 'researching' ? (
          <div className="loading-message">
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>{status === 'loading' ? 'Planning research...' : 'Researching...'}</p>
          </div>
        ) : null}
        
        <div ref={messagesEndRef} />
      </div>
      
      <QueryInput />
    </main>
  );
};

export default ChatView; 