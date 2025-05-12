// Line 1: import React from 'react';
// Explanation:
// - As always, we import `React` because this file will contain a React component and use JSX.
import React from 'react';

// Line 2: import './SuggestionCard.css';
// Explanation:
// - We import the CSS file that will specifically style this `SuggestionCard` component.
// - Thought Process (Encapsulation): This keeps the styles closely related to the component, making it easier to understand and modify the card's appearance without affecting other parts of the application.
import './SuggestionCard.css';

// Line 3: const SuggestionCard = ({ icon, title, subtitle, source, image }) => { ... };
// Explanation:
// - `const SuggestionCard = (...) => { ... }`: Defines a functional component named `SuggestionCard`.
// - `({ icon, title, subtitle, source, image })`: This is JavaScript "destructuring" syntax used for props.
//   - When we use this component elsewhere (e.g., in `MainContent.js`), we'll pass it properties like `<SuggestionCard title="My News" ... />`.
//   - Instead of receiving a single `props` object and then doing `props.title`, `props.icon`, etc., inside the component, we destructure these properties directly from the `props` object in the function parameters.
//   - This makes the code cleaner as we can use `title` directly instead of `props.title`.
//   - These props (`icon`, `title`, `subtitle`, `source`, `image`) are the pieces of data our card can display. Not all of them need to be provided every time; we'll handle that in the JSX.
// - Thought Process (Reusable Components & Props): The goal is to make this card generic. By defining these props, we can reuse the same `SuggestionCard` component to display weather, news, or other types of suggestions just by passing different data.
//Thought Process:
//Presentational Component: Its primary role is to display data it receives via props. It's largely "dumb" – it doesn't have much internal logic or state of its own (though it could if a card had internal interactive states).
//Props-Driven: Its appearance and content are entirely determined by the props passed to it. This makes it highly reusable.
//Conditional Rendering: Uses && to optionally display parts of the card (like an image or icon) based on whether the corresponding prop was provided.
//How it Evolves:
//Click Handlers: Cards might become clickable, requiring an onClick prop to be passed in from MainContent to handle the action.
//Variations: You might have different types of suggestion cards with slightly different layouts. This could be handled by passing a type prop and using conditional rendering within SuggestionCard, or by creating separate specialized card components (e.g., WeatherCard, NewsCard) that might share some common styling.
const SuggestionCard = ({ icon, title, subtitle, source, image }) => {

  // Line 4: return ( <div className="suggestion-card"> ... </div> );
  // Explanation:
  // - The `return` statement provides the JSX structure for this component.
  // - `<div className="suggestion-card">`: This is the main container for each individual card.
  //   - `div`: A generic block-level HTML element used to group other elements.
  //   - `className="suggestion-card"`: Assigns a CSS class for styling this container. We'll define styles for `.suggestion-card` in `SuggestionCard.css`.
  return (
    <div className="suggestion-card">

      {/* Line 5: {image && <img src={image} alt={title} className="suggestion-card-image" />} */}
      {/* Explanation: */}
      {/* - Conditional rendering for an image. */}
      {/* - `{image && ...}`: This uses the JavaScript logical AND (`&&`) operator. */}
      {/*   - If the `image` prop is provided (is "truthy", meaning it's not null, undefined, or an empty string), then the `<img ... />` tag will be rendered. */}
      {/*   - If `image` is not provided, this entire part is skipped. */}
      {/* - `<img src={image} alt={title} className="suggestion-card-image" />`: Standard HTML `<img>` tag. */}
      {/*   - `src={image}`: The `src` attribute is set to the value of the `image` prop (which should be a URL to an image). */}
      {/*   - `alt={title}`: The `alt` attribute provides alternative text for the image. This is important for accessibility (screen readers will read it) and if the image fails to load. We use the `title` prop as a sensible default for the alt text. */}
      {/*   - `className="suggestion-card-image"`: A CSS class for styling the image within the card. */}
      {/* - Thought Process (Flexibility): Some cards might have images (like news articles), others might not (like simple weather text). This makes the component flexible. */}
      {image && <img src={image} alt={title} className="suggestion-card-image" />}

      {/* Line 6: <div className="suggestion-card-content"> ... </div> */}
      {/* Explanation: */}
      {/* - This `div` groups the main textual content of the card, separate from a potential full-width image above it or a source link below. */}
      {/* - `className="suggestion-card-content"`: CSS class for styling this content area. */}
      <div className="suggestion-card-content">

        {/* Line 7: {icon && <span className="suggestion-card-icon">{icon}</span>} */}
        {/* Explanation: */}
        {/* - Conditional rendering for an icon. */}
        {/* - `{icon && ...}`: If an `icon` prop is provided (this would likely be a React Icon component passed from the parent), then the `<span>` containing the icon is rendered. */}
        {/* - `<span className="suggestion-card-icon">{icon}</span>`: */}
        {/*   - `<span>`: An inline HTML element, often used to group inline elements or apply styles to a piece of text/icon. */}
        {/*   - `className="suggestion-card-icon"`: CSS class for styling the icon (e.g., size, color, margin). */}
        {/*   - `{icon}`: Renders the icon component that was passed as a prop. */}
        {/* - Thought Process: Some cards might have a leading icon (like a sun for weather), others might not. */}
        {icon && <span className="suggestion-card-icon">{icon}</span>}

        {/* Line 8: <div className="suggestion-card-text"> ... </div> */}
        {/* Explanation: */}
        {/* - This `div` groups the title and subtitle together, allowing them to be styled or positioned as a block, potentially next to an icon. */}
        {/* - `className="suggestion-card-text"`: CSS class for this text block. */}
        <div className="suggestion-card-text">

          {/* Line 9: <h4 className="suggestion-card-title">{title}</h4> */}
          {/* Explanation: */}
          {/* - `<h4>`: An HTML heading tag. We use `h4` assuming these cards are supplementary content on the page, and `h1`, `h2`, `h3` might be used for more primary page sections. Choosing the right heading level is good for document structure and accessibility. */}
          {/* - `className="suggestion-card-title"`: CSS class for styling the title. */}
          {/* - `{title}`: Renders the `title` prop. We assume a title will always be provided for a suggestion card. */}
          <h4 className="suggestion-card-title">{title}</h4>

          {/* Line 10: {subtitle && <p className="suggestion-card-subtitle">{subtitle}</p>} */}
          {/* Explanation: */}
          {/* - Conditional rendering for the subtitle. */}
          {/* - `{subtitle && ...}`: If a `subtitle` prop is provided, the `<p>` tag is rendered. */}
          {/* - `<p className="suggestion-card-subtitle">{subtitle}</p>`: */}
          {/*   - `<p>`: HTML paragraph tag. */}
          {/*   - `className="suggestion-card-subtitle"`: CSS class for styling the subtitle. */}
          {/*   - `{subtitle}`: Renders the `subtitle` prop. */}
          {/* - Thought Process: Not all cards may need a subtitle. */}
          {subtitle && <p className="suggestion-card-subtitle">{subtitle}</p>}

        </div> {/* End of .suggestion-card-text */}
      </div> {/* End of .suggestion-card-content */}

      {/* Line 11: {source && <p className="suggestion-card-source">{source}</p>} */}
      {/* Explanation: */}
      {/* - Conditional rendering for the source information (e.g., "weather.com", "Reuters"). */}
      {/* - `{source && ...}`: If a `source` prop is provided, this paragraph is rendered. */}
      {/* - `<p className="suggestion-card-source">{source}</p>`: */}
      {/*   - `<p>`: HTML paragraph tag. */}
      {/*   - `className="suggestion-card-source"`: CSS class for styling the source text (often smaller and a different color). */}
      {/*   - `{source}`: Renders the `source` prop. */}
      {source && <p className="suggestion-card-source">{source}</p>}

    </div> // End of .suggestion-card
  ); // End of return statement
}; // End of SuggestionCard component

// Line 12: export default SuggestionCard;
// Explanation:
// - Makes the `SuggestionCard` component available for import and use in other parts of our application (specifically, we'll use it in `MainContent.js` in the next step).
export default SuggestionCard;