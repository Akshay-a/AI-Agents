// src/components/SearchBar.js
import React, { useState } from 'react';
import './SearchBar.css';
import { FiSearch, FiPaperclip, FiMic, FiFilter, FiArrowRight } from 'react-icons/fi'; // Example icons
import { useResearch } from '../contexts/ResearchContext';

const SearchBar = () => {
  const [query, setQuery] = useState('');
  const { startResearch, status } = useResearch();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      startResearch(query);
    }
  };

  // Determine if the search button should be disabled
  const isSearchDisabled = !query.trim() || status === 'loading' || status === 'researching';

  return (
    <div className="search-container">
      <div className="perplexity-logo-main">
        DeepResearch
      </div>
      <form className="search-bar" onSubmit={handleSubmit}>
        <div className="search-input-wrapper">
          <FiSearch className="search-icon-prefix" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a research question..."
            disabled={status === 'loading' || status === 'researching'}
          />
          <div className="search-actions">
            <button type="button" className="action-button" title="Attach files">
              <FiPaperclip />
            </button>
            <button type="button" className="action-button" title="Focus"> {/* Replace with actual Focus icon/dropdown */}
              <FiFilter />
            </button>
            <button type="button" className="action-button" title="Voice search">
              <FiMic />
            </button>
          </div>
        </div>
        <div className="search-buttons">
          <button 
            type="submit" 
            className="search-submit-button" 
            disabled={isSearchDisabled}
          >
            {status === 'loading' || status === 'researching' ? (
              <span className="loading-spinner"></span>
            ) : (
              <FiArrowRight size={18}/>
            )}
          </button>
        </div>
      </form>
      {/* Focus options could be rendered here if needed */}
    </div>
  );
};

export default SearchBar;