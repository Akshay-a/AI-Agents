import React from 'react';
import './Sidebar.css';
import { FiPlus, FiHome, FiCompass, FiStar, FiUser } from 'react-icons/fi'; // Example icons

//Thought Process:
//Component Identification: The left bar is a distinct, self-contained UI element.
//Props: Currently, it doesn't take props, but it could if, for example, the list of navigation items was dynamic or if the user icon needed to change based on login status.
//Styling: Sidebar.css handles its fixed width, background color, and internal arrangement of elements (again, often using flexbox for vertical stacking and spacing of its children).
//Icons: Used react-icons for visual cues, making the UI more intuitive.
//How it Evolves:
//Dynamic Content: Navigation links could be fetched from an API or be based on user roles.
//Statefulness: The "New Thread" button might trigger an action that changes state elsewhere in the app. The active navigation link would likely be managed by state (possibly through a routing library).
//Collapsibility: The sidebar might become collapsible, requiring state to manage its open/closed status and more complex CSS for animations.
const Sidebar = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        {/* Replace with an actual SVG or image logo if you have one */}
        <span className="logo-placeholder">❖</span>
      </div>
      <button className="new-thread-button">
        <FiPlus size={20} />
        <span>New Thread</span>
      </button>
      <nav className="sidebar-nav">
        <a href="#home" className="nav-item active">
          <FiHome size={20} />
          <span>Home</span>
        </a>
        <a href="#discover" className="nav-item">
          <FiCompass size={20} />
          <span>Discover</span>
        </a>
        <a href="#spaces" className="nav-item">
          <FiStar size={20} /> {/* Using FiStar as a placeholder for Spaces */}
          <span>Spaces</span>
        </a>
      </nav>
      <div className="sidebar-user">
        <FiUser size={24} />
      </div>
    </aside>
  );
};

export default Sidebar;