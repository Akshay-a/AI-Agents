// src/App.js
import React from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import { ResearchProvider } from './contexts/ResearchContext';

// The App component is the top-level component that sets up the overall layout
// and wraps the application with necessary context providers.
function App() {
  return (
    // Wrap the entire application with the ResearchProvider to make research state
    // and functions available to all components
    <ResearchProvider>
      <div className="app-container"> {/* display: flex; height: 100vh */}
        <Sidebar />
        <div className="content-wrapper"> {/* display: flex; flex-direction: column; flex-grow: 1; height: 100vh */}
          <ChatView />
        </div>
      </div>
    </ResearchProvider>
  );
}

export default App;
