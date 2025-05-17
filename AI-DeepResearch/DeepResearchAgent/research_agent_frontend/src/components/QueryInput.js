import React, { useState } from 'react';
import './QueryInput.css';
import { FiSend } from 'react-icons/fi';
import { useResearch } from '../contexts/ResearchContext';

const QueryInput = () => {
  const [query, setQuery] = useState('');
  const { startResearch, status } = useResearch();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && status !== 'loading' && status !== 'researching') {
      startResearch(query);
      setQuery(''); // Clear input after submission
    }
  };

  return (
    <div className="query-input-container">
      <form className="query-input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="query-input"
          placeholder="Ask a research question..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={status === 'loading' || status === 'researching'}
        />
        <button 
          type="submit"
          className="send-button"
          disabled={!query.trim() || status === 'loading' || status === 'researching'}
        >
          {status === 'loading' || status === 'researching' ? (
            <div className="button-spinner"></div>
          ) : (
            <FiSend size={18} />
          )}
        </button>
      </form>
    </div>
  );
};

export default QueryInput; 