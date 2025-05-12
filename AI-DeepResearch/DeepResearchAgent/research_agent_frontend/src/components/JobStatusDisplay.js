import React from 'react';
import './JobStatusDisplay.css';
import { useResearch } from '../contexts/ResearchContext';
import { FiLoader, FiAlertCircle } from 'react-icons/fi';

const JobStatusDisplay = () => {
  const { status, error } = useResearch();

  // Don't render if status is idle
  if (status === 'idle') {
    return null;
  }

  // Determine status message and icon
  let statusMessage = '';
  let statusClass = '';
  let StatusIcon = null;

  switch (status) {
    case 'loading':
      statusMessage = 'Starting research...';
      statusClass = 'loading';
      StatusIcon = FiLoader;
      break;
    case 'researching':
      statusMessage = 'Researching your query...';
      statusClass = 'researching';
      StatusIcon = FiLoader;
      break;
    case 'completed':
      return null; // Don't show status when completed, as the report will be displayed
    case 'failed':
      statusMessage = error || 'Research failed. Please try again.';
      statusClass = 'failed';
      StatusIcon = FiAlertCircle;
      break;
    default:
      return null;
  }

  return (
    <div className={`status-container ${statusClass}`}>
      {StatusIcon && <StatusIcon className="status-icon" />}
      <span className="status-message">{statusMessage}</span>
    </div>
  );
};

export default JobStatusDisplay;
