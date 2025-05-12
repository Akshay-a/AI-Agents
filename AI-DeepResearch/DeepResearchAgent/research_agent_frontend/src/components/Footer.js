// src/components/Footer.js

// Line 1: import React from 'react';
// Explanation: Standard React import for JSX and component definition.
import React from 'react';

// Line 2: import './Footer.css';
// Explanation: Importing the CSS file specific to this Footer component.
import './Footer.css';

// Line 3: NEW - Import the FiHelpCircle icon from react-icons
// Explanation: We need this icon for the help button in the footer.
import { FiHelpCircle } from 'react-icons/fi';

// Line 4: const Footer = () => { ... };
// Explanation: Defining the functional component for our footer.
const Footer = () => {

  // Line 5: return ( <footer className="footer"> ... </footer> );
  // Explanation:
  // - `<footer>`: Using the semantic HTML `<footer>` tag, which is appropriate for site-wide footer content.
  // - `className="footer"`: Assigning a CSS class for styling this main footer container.
  return (
    <footer className="footer">

      {/* Line 6: <div className="footer-links"> ... </div> */}
      {/* Explanation:
          - A `div` to group all the navigation links in the footer.
          - `className="footer-links"`: For styling this group of links (e.g., using flexbox to space them out). */}
      <div className="footer-links">
        {/* Lines 7-13: Anchor (<a>) tags for footer navigation */}
        {/* Explanation:
            - `<a>`: Standard HTML anchor tag for hyperlinks.
            - `href="#pro"`: The `href` attribute specifies the link's destination. Using `#` followed by a name creates a "hash link" or "fragment identifier." Clicking these will try to navigate to an element with that ID on the current page or simply add the hash to the URL. For now, these are placeholders. In a real app, they would point to actual URLs (e.g., `/pro`, `/enterprise`).
            - Text like "Pro", "Enterprise": This is the visible text of the link.
            - Thought Process: These are common informational links found in SaaS application footers. We're replicating the ones visible in the Perplexity UI.
        */}
        <a href="#pro">Pro</a>
        <a href="#enterprise">Enterprise</a>
        <a href="#api">API</a>
        <a href="#blog">Blog</a>
        <a href="#careers">Careers</a>
        <a href="#store">Store</a> {/* Perplexity doesn't have 'Store', but it was in the screenshot's footer text */}
        <a href="#finance">Finance</a> {/* Same as above */}
        {/* You could add other common links here like:
        <a href="#terms">Terms</a>
        <a href="#privacy">Privacy</a>
        */}
      </div>

      {/* Line 14: <div className="footer-actions"> ... </div> */}
      {/* Explanation:
          - A `div` to group the interactive elements on the right side of the footer (language selector, help button).
          - `className="footer-actions"`: For styling this group. */}
      <div className="footer-actions">

        {/* Lines 15-19: Language Selector (<select> element) */}
        {/* Explanation:
            - `<select>`: Standard HTML element for a dropdown list.
            - `className="language-selector"`: For styling the dropdown.
            - `defaultValue="English"`: Sets the initially selected option. For a fully functional language selector, this would be controlled by React state and an `onChange` handler. For now, it's static.
            - `<option value="English">English</option>`: Defines an option within the dropdown. `value` is the internal value, and "English" is the displayed text.
            - Thought Process: Mimicking the language dropdown seen on Perplexity. A real implementation would involve internationalization (i18n) libraries and state management.
        */}
        <select className="language-selector" defaultValue="English" aria-label="Select language">
          <option value="English">English</option>
          <option value="Spanish">Español</option>
          {/* Add other languages as needed */}
        </select>

        {/* Lines 20-22: Help Button (<button> element) */}
        {/* Explanation:
            - `<button>`: Standard HTML button element.
            - `className="help-button"`: For styling the button.
            - `aria-label="Help"`: Provides an accessible name for screen readers, as the button only contains an icon.
            - `<FiHelpCircle size={20} />`: Renders the help icon imported from `react-icons`.
              - `size={20}`: A prop specific to `react-icons` components to set the icon size.
            - Thought Process: Replicating the help icon button. This would typically open a help modal, navigate to an FAQ page, or trigger a support chat.
        */}
        <button className="help-button" aria-label="Help">
          <FiHelpCircle size={20} />
        </button>
      </div>
    </footer> // End of footer element
  ); // End of return statement
}; // End of Footer component

// Line 23: export default Footer;
// Explanation: Makes the Footer component available for use in other files (like App.js).
export default Footer;