// src/components/MainContent.js
import React from 'react';
import './MainContent.css';
import SearchBar from './SearchBar';
import PlanDisplay from './PlanDisplay';
import ReportDisplay from './ReportDisplay';
import JobStatusDisplay from './JobStatusDisplay';
import SuggestionCard from './SuggestionCard';
import { FiSun, FiSearch, FiBook, FiDatabase } from 'react-icons/fi';
import { useResearch } from '../contexts/ResearchContext';

const MainContent = () => {
  const { status, report, error } = useResearch();

  // Suggestions for initial state
  const suggestions = [
    {
      id: 1,
      icon: <FiSearch size={24} />,
      title: 'How does quantum computing work?',
      subtitle: 'Explore the principles of quantum mechanics in computing',
      source: 'Research Topic',
    },
    {
      id: 2,
      icon: <FiBook size={24} />,
      title: 'What are the environmental impacts of renewable energy?',
      subtitle: 'Compare different renewable energy sources',
      source: 'Research Topic',
    },
    {
      id: 3,
      icon: <FiDatabase size={24} />,
      title: 'Explain the history and evolution of artificial intelligence',
      subtitle: 'From early concepts to modern applications',
      source: 'Research Topic',
    },
    {
      id: 4,
      icon: <FiSun size={24} />,
      title: 'What are the latest advancements in solar energy technology?',
      subtitle: 'Recent breakthroughs and future prospects',
      source: 'Research Topic',
    },
  ];

  return (
    <main className="main-content">
      <SearchBar />
      
      {/* Always show JobStatusDisplay to ensure errors are visible */}
      <JobStatusDisplay />
      
      {/* Only show PlanDisplay when in active states */}
      {(status === 'researching' || status === 'loading' || status === 'completed' || status === 'failed') && (
        <PlanDisplay />
      )}
      
      {/* Show report when there's content or when in appropriate states */}
      {(report || status === 'researching' || status === 'completed') && (
        <ReportDisplay />
      )}

      {/* Show suggestions only in idle state and when no error */}
      {status === 'idle' && !error && !report && (
        <div className="suggestions-area">
          <div className="info-banner">
            <img
              src="https://www.perplexity.ai/windows.png"
              alt="DeepResearch Info"
              className="banner-icon"
            />
            <div className="banner-text">
              <strong>Welcome to DeepResearch</strong>
              <p>Your AI-powered research assistant</p>
            </div>
            <button className="banner-button" aria-label="Learn more about DeepResearch">
              →
            </button>
          </div>

          <h3 className="suggestions-header">Try researching these topics:</h3>

          <div className="suggestion-cards-grid">
            {suggestions.map(suggestion => (
              <SuggestionCard
                key={suggestion.id}
                icon={suggestion.icon}
                title={suggestion.title}
                subtitle={suggestion.subtitle}
                source={suggestion.source}
                image={suggestion.image}
              />
            ))}
          </div>
        </div>
      )}
    </main>
  );
};

export default MainContent;