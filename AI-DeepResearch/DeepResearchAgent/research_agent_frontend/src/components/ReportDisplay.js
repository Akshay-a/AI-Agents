import React, { useState, useEffect } from 'react';
import './ReportDisplay.css';
import { useResearch } from '../contexts/ResearchContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FiFileText, FiDownload, FiCopy, FiLoader } from 'react-icons/fi';

const ReportDisplay = () => {
  const { report, status, query } = useResearch();
  const [copied, setCopied] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Handle loading state when research is in progress
  useEffect(() => {
    console.log('Status changed:', status);
    if (status === 'researching' || status === 'loading') {
      setIsGenerating(true);
    } else {
      setIsGenerating(false);
    }
  }, [status]);

  // Reset copied state after 2 seconds
  useEffect(() => {
    let timer;
    if (copied) {
      timer = setTimeout(() => setCopied(false), 2000);
    }
    return () => clearTimeout(timer);
  }, [copied]);

  // Log when report changes
  useEffect(() => {
    if (report) {
      console.log('Report received in ReportDisplay component:', report.substring(0, 100) + '...');
    }
  }, [report]);

  // Don't render if there's no query
  if (!query) {
    return null;
  }

  // Handle copy to clipboard
  const handleCopy = () => {
    if (report) {
      navigator.clipboard.writeText(report)
        .then(() => setCopied(true))
        .catch(err => console.error('Failed to copy text: ', err));
    }
  };

  // Handle download as markdown
  const handleDownload = () => {
    if (report) {
      const blob = new Blob([report], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `research-report-${new Date().toISOString().split('T')[0]}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="report-container">
      <div className="report-header-container">
        <h2 className="report-header">
          <FiFileText className="report-icon" />
          Research Report
        </h2>
        {report && (
          <div className="report-actions">
            <button 
              className="report-action-button" 
              onClick={handleCopy}
              title="Copy to clipboard"
            >
              <FiCopy />
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
            <button 
              className="report-action-button" 
              onClick={handleDownload}
              title="Download as markdown"
            >
              <FiDownload />
              <span>Download</span>
            </button>
          </div>
        )}
      </div>
      
      <div className="report-content">
        {report ? (
          <div className="markdown-content">
            {console.log('Rendering report in JSX')}
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({node, ...props}) => <p className="report-paragraph" {...props} />,
                h1: ({node, children, ...props}) => <h1 className="report-heading-1" {...props}>{children}</h1>,
                h2: ({node, children, ...props}) => <h2 className="report-heading-2" {...props}>{children}</h2>,
                h3: ({node, children, ...props}) => <h3 className="report-heading-3" {...props}>{children}</h3>,
                ul: ({node, ...props}) => <ul className="report-list" {...props} />,
                li: ({node, ...props}) => <li className="report-list-item" {...props} />
              }}
            >
              {report}
            </ReactMarkdown>
          </div>
        ) : isGenerating ? (
          <div className="report-generating">
            <div className="report-loading-spinner">
              <FiLoader className="spinner-icon" />
            </div>
            <p className="report-generating-text">
              Generating your research report...
            </p>
            <p className="report-generating-subtext">
              We're analyzing and synthesizing information from multiple sources.
              This may take a few minutes depending on the complexity of your query.
            </p>
          </div>
        ) : (
          <p className="report-placeholder">
            Your research report will appear here once it's generated.
          </p>
        )}
      </div>
    </div>
  );
};

export default ReportDisplay;
