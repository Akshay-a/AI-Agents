import React from 'react';
import './PlanDisplay.css';
import { useResearch } from '../contexts/ResearchContext';
import { FiClock, FiCheck, FiLoader, FiAlertCircle, FiInfo, FiX } from 'react-icons/fi';

const PlanDisplay = () => {
  const { plan, isTaskCompleted, getTaskStatus, getTaskError, status, error, connectionStatus, currentStatusMessage } = useResearch();

  // Don't render if there's no plan
  if (!plan || plan.length === 0) {
    return null;
  }

  // Calculate overall progress percentage
  const completedTasks = plan.filter(task => isTaskCompleted(task.id)).length;
  const progressPercentage = plan.length > 0 ? (completedTasks / plan.length) * 100 : 0;

  return (
    <div className="plan-container">
      <div className="plan-header-container">
        <h3 className="plan-header">Research Plan</h3>
        {status === 'researching' && (
          <div className="plan-status">
            <div className="progress-bar-container">
              <div 
                className="progress-bar" 
                style={{ width: `${progressPercentage}%` }}
              ></div>
            </div>
            <span className="progress-text">{Math.round(progressPercentage)}% Complete</span>
            {currentStatusMessage && (
              <div className="current-status-message">
                <span>{currentStatusMessage}</span>
              </div>
            )}
          </div>
        )}
        {status === 'completed' && (
          <div className="plan-status completed">
            <FiCheck className="status-icon completed" />
            <span>Research Complete</span>
          </div>
        )}
        {status === 'failed' && (
          <div className="plan-status failed">
            <FiAlertCircle className="status-icon failed" />
            <span>Research Failed</span>
          </div>
        )}
        {connectionStatus !== 'connected' && (
          <div className="connection-status">
            <FiInfo className="status-icon" />
            <span>{connectionStatus === 'connecting' ? 'Reconnecting...' : 'Disconnected'}</span>
          </div>
        )}
      </div>
      
      {error && status !== 'completed' && (
        <div className="plan-error">
          <FiAlertCircle className="error-icon" />
          <span>{error}</span>
        </div>
      )}
      
      <ul className="plan-list">
        {plan.map((task, index) => {
          // Get the task status from the context
          const taskStatus = getTaskStatus(task.id);
          const taskError = getTaskError(task.id);
          
          // Determine if the task is completed or has an error
          const isCompleted = taskStatus === 'COMPLETED';
          const hasError = taskStatus === 'ERROR';
          
          // Determine if the task is running (for animation purposes)
          const isRunning = !isCompleted && !hasError && 
            ((index === 0 && status === 'researching') || 
             (index > 0 && isTaskCompleted(plan[index - 1]?.id) && !isTaskCompleted(task.id)));
          
          // Determine the task class and icon
          let taskClass = 'pending';
          let TaskIcon = FiClock;
          
          if (isCompleted) {
            taskClass = 'completed';
            TaskIcon = FiCheck;
          } else if (hasError) {
            taskClass = 'error';
            TaskIcon = FiX;
          } else if (isRunning) {
            taskClass = 'running';
            TaskIcon = FiLoader;
          }
          
          return (
            <li 
              key={task.id || `task-${index}`} 
              id={`task-item-${task.id || index}`}
              className={`plan-item ${taskClass}`}
            >
              <div className="task-icon-container">
                <span className={`task-icon ${taskClass}`}>
                  <TaskIcon />
                </span>
                {index > 0 && !isCompleted && !isRunning && (
                  <div className="task-connector"></div>
                )}
              </div>
              <div className="task-content">
                <span className="task-description">{task.description}</span>
                {isRunning && (
                  <span className="task-status-text">In progress...</span>
                )}
                {hasError && (
                  <span className="task-error-text">{taskError || 'Task failed'}</span>
                )}
                {isCompleted && task.type === 'SEARCH' && (
                  <span className="task-result-summary">Found relevant sources</span>
                )}
                {isCompleted && task.type === 'FILTER' && (
                  <span className="task-result-summary">Filtered and organized information</span>
                )}
                {isCompleted && task.type === 'SYNTHESIZE' && (
                  <span className="task-result-summary">Synthesized research findings</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default PlanDisplay;
