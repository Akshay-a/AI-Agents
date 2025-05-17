import React from 'react';
import './Sidebar.css';
import { FiPlus, FiClock, FiArrowRight } from 'react-icons/fi';
import { useResearch } from '../contexts/ResearchContext';

const Sidebar = () => {
  const { historyList, clearCurrentChat, loadHistoryItem, status } = useResearch();

  // Handle click on "New Research" button
  const handleNewResearch = () => {
    if (status !== 'loading' && status !== 'researching') {
      clearCurrentChat();
    }
  };

  // Handle click on history item
  const handleHistoryClick = (jobId) => {
    if (status !== 'loading' && status !== 'researching') {
      loadHistoryItem(jobId);
    }
  };

  // Truncate long query strings for display
  const truncateQuery = (query) => {
    if (!query) return "Untitled Research"; // Handle undefined or null query
    return query.length > 30 ? query.substring(0, 27) + '...' : query;
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-placeholder">❖</span>
        <span className="logo-text">DeepResearch</span>
      </div>
      
      <button 
        className="new-research-button" 
        onClick={handleNewResearch}
        disabled={status === 'loading' || status === 'researching'}
      >
        <FiPlus size={20} />
        <span>New Research</span>
      </button>
      
      {historyList && historyList.length > 0 ? (
        <div className="history-container">
          <h3 className="history-title">
            <FiClock size={16} />
            <span>History</span>
          </h3>
          <ul className="history-list">
            {historyList.map((item) => (
              <li 
                key={item.jobId} 
                className="history-item"
                onClick={() => handleHistoryClick(item.jobId)}
              >
                <span className="history-item-query">{truncateQuery(item.queryTitle)}</span>
                <FiArrowRight size={14} className="history-item-icon" />
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="empty-history-message">
          <p>No research history yet</p>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;