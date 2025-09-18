
import gradio as gr
import time

# TODO: This is a mock chat history. need to dynamically load
# from a database or user session. The backend function to retrieve
# a user's chat history, which would be a list of dictionaries, each with keys like
# 'id', 'title', 'time', and 'type' ('Broad' or 'URL').
mock_chat_history_html = """
<h3>Recent Chats</h3>
<div class="history-item active">
    <div class="history-title">Columbia University Dataset Analysis</div>
    <div class="history-meta">
        <span class="history-time">2 hours ago</span>
        <span class="history-type broad">Broad</span>
    </div>
</div>
<div class="history-item">
    <div class="history-title">University Website Scraping</div>
    <div class="history-meta">
        <span class="history-time">Yesterday</span>
        <span class="history-type url">URL</span>
    </div>
</div>
<div class="history-item">
    <div class="history-title">Stanford Admissions Research</div>
    <div class="history-meta">
        <span class="history-time">3 days ago</span>
        <span class="history-type broad">Broad</span>
    </div>
</div>
<div class="history-item">
    <div class="history-title">Documentation Analysis</div>
    <div class="history-meta">
        <span class="history-time">1 week ago</span>
        <span class="history-type url">URL</span>
    </div>
</div>
"""

# CSS from the HTML mockup, with adjustments for Gradio components
css = """
:root {
    --primary-color: #4f46e5;
    --primary-hover: #4338ca;
    --secondary-color: #10b981;
    --secondary-hover: #059669;
    --text-dark: #2d3748;
    --text-light: #718096;
    --bg-main: white;
    --bg-sidebar: white;
    --bg-light: #f8fafc;
    --border-color: #e2e8f0;
}

/* Gradio overrides */
.gradio-container {
    background: var(--bg-light);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: var(--text-dark);
}
.gap.row { gap: 0 !important; }
.gap.column { gap: 0 !important; }
.panel, .panelflex {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    padding: 0 !important;
}
.main {
    display: flex;
    padding: 0;
    margin: 0;
    height: 100vh;
    overflow: hidden;
}

/* Sidebar */
.sidebar {
    width: 260px !important;
    min-width: 260px !important;
    background: #f7f7f8;
    border-right: 1px solid #e5e5e5;
    padding: 0;
    display: flex;
    flex-direction: column;
    height: 100vh;
    position: relative;
}
.sidebar-header { 
    padding: 8px 12px;
    background: #f7f7f8;
    position: sticky;
    top: 0;
    z-index: 10;
}
.sidebar-search {
    margin: 8px 12px;
    position: relative;
}
.sidebar-search input {
    width: 100%;
    padding: 10px 12px;
    padding-left: 32px;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    background: white;
    font-size: 13px;
    color: #40414f;
}
.sidebar-search::before {
    content: "🔍";
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 12px;
    opacity: 0.5;
}
.sidebar-logo {
    padding: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: #40414f;
}
.sidebar-logo img {
    width: 24px;
    height: 24px;
    border-radius: 4px;
}

.new-chat-btn {
    margin: 8px 12px;
    width: calc(100% - 24px);
    padding: 10px 12px;
    background: white;
    color: #40414f;
    border: 1px solid #e5e5e5;
    border-radius: 8px !important;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.new-chat-btn:hover { 
    background: #f5f5f5;
}
.new-chat-btn::before {
    content: "+";
    font-size: 16px;
    margin-right: 4px;
}

.chat-history { 
    flex: 1;
    overflow-y: auto;
    padding: 20px 0 20px 20px;
    margin-bottom: 80px;
}
.chat-history h3 { font-size: 13px; font-weight: 600; color: #4a5568; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.history-item { 
    padding: 14px 16px;
    margin: 0 0 6px 0;
    background: var(--bg-light);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid transparent;
    width: calc(100% - 32px);
}
.history-item:hover { 
    background: #e5e5e5;
}
.history-item.active { 
    background: #f5f5f5;
}
.history-title { 
    font-size: 13px;
    font-weight: 400;
    color: #40414f;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.history-meta { 
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
}
.history-time { 
    font-size: 11px;
    color: #8e8ea0;
}
.history-type { 
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
}
.history-type.broad { 
    background: #f0f0f0;
    color: #666;
}
.history-type.url { 
    background: #f0f0f0;
    color: #666;
}

/* Main Content */
.main-content { flex: 1; display: flex; flex-direction: column; background: var(--bg-main); height: 100vh; }

/* Tab Navigation */
.tab-nav button {
    padding: 12px 20px !important;
    background: none !important;
    border: none !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--text-light) !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    transition: all 0.2s;
    margin: 0 4px;
}
.tab-nav button.selected {
    color: var(--primary-color) !important;
    border-bottom-color: var(--primary-color) !important;
}
.tab-nav button:hover {
    color: var(--primary-hover) !important;
    background: rgba(79, 70, 229, 0.05) !important;
}
.tab-nav {
    background: var(--bg-main);
    border-bottom: 1px solid var(--border-color);
    padding: 0 20px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

/* URL Search Specific */
.url-input-section { 
    padding: 20px;
    background: var(--bg-main);
    border-bottom: 1px solid var(--border-color);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.url-input-section label { 
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-dark);
    margin-bottom: 8px;
}
.url-input textarea {
    min-height: 80px !important;
    padding: 12px;
    border: 1px solid var(--border-color) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    background: white !important;
    line-height: 1.5 !important;
}
.url-input textarea:focus { border-color: var(--primary-color) !important; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1) !important; }
.url-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; }
.url-count { font-size: 13px; color: var(--text-light); }
.scrape-btn {
    padding: 12px 20px;
    background: var(--secondary-color);
    color: white;
    border: none;
    border-radius: 8px !important;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
}
.scrape-btn:hover { background: var(--secondary-hover); transform: translateY(-1px); }

.context-banner { padding: 12px 24px; background: linear-gradient(90deg, #e6fffa, #f0fff4); border-bottom: 1px solid #c6f6d5; font-size: 13px; color: #2f855a; }
.context-banner strong { color: #22543d; }

/* Chat Area */
.chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
    max-width: 900px;
    margin: 0 auto;
    width: 100%;
    height: calc(100% - 60px);
    position: relative;
}
.chat-messages {
    flex: 1;
    overflow-y: auto;
    margin-bottom: 24px;
    padding-right: 8px;
}
.chat-messages .message-bubble {
    max-width: 75%;
    padding: 16px 20px !important;
    border-radius: 18px !important;
    font-size: 14px !important;
    line-height: 1.5;
    border: none !important;
}
.chat-messages .user-message { background: var(--primary-color) !important; color: white !important; }
.chat-messages .bot-message { background: var(--bg-light) !important; color: var(--text-dark) !important; border: 1px solid var(--border-color) !important; }

.chat-input-container {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    transition: all 0.2s;
    padding: 0;
    position: absolute;
    bottom: 20px;
    left: 20px;
    right: 20px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}
.chat-input-container:focus-within { 
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1);
}
.chat-input textarea {
    border: none !important;
    background: none !important;
    font-size: 14px !important;
    resize: none;
    min-height: 24px !important;
    padding: 12px 16px !important;
    line-height: 1.5;
}
.chat-input textarea:focus { box-shadow: none !important; }
.send-btn {
    min-width: 32px !important;
    width: 32px;
    height: 32px;
    background: var(--primary-color);
    color: white !important;
    border: none;
    border-radius: 8px !important;
    font-size: 14px !important;
    transition: all 0.2s;
    margin: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.send-btn:hover { 
    background: var(--primary-hover);
    transform: translateY(-1px);
}

.empty-state { text-align: center; margin: 80px auto; color: var(--text-light); padding: 20px; }
.empty-state-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.empty-state h3 { font-size: 18px; font-weight: 600; color: #4a5568; margin-bottom: 8px; }
.empty-state p { font-size: 14px; max-width: 400px; margin: 0 auto; line-height: 1.5; }
#url-chatbot .empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; margin: 0; }
"""

class WebScraperApp:
    def __init__(self):
        self.broad_chat_history = []
        self.url_chat_history = []
        self.url_context = ""

    def add_broad_chat_message(self, user_message, history):
        history.append((user_message, None))
        yield history, gr.update(value="", interactive=False)

        # TODO: Backend function call for broad search.
        # The backend function `process_broad_search(query: str, history: list)` should:
        # 1. Take the user's query and the conversation history.
        # 2. Search a vector database for relevant context.
        # 3. If needed, perform a web search.
        # 4. Synthesize the information and generate a response.
        # 5. Return a single string as the response.
        # For now, we simulate a streaming response.
        bot_response = f"I'm searching for information about \"{user_message}\". Let me check the vector database and perform a web search if needed..."
        history[-1] = (user_message, "")
        for char in bot_response:
            history[-1] = (user_message, history[-1][1] + char)
            time.sleep(0.01)
            yield history, gr.update(interactive=False)
        
        yield history, gr.update(interactive=True)

    def add_url_chat_message(self, user_message, history):
        history.append((user_message, None))
        yield history, gr.update(value="", interactive=False)

        # TODO: Backend function call for URL-based RAG.
        # The backend function `process_url_query(query: str, history: list, context: str)` should:
        # 1. Take the user's query, conversation history, and the active URL context.
        # 2. Query the RAG system (which has processed the URLs) to find answers.
        # 3. Generate a response based *only* on the provided context.
        # 4. Return a single string as the response.
        bot_response = f"Based on the scraped content, here's what I found about \"{user_message}\"..."
        history[-1] = (user_message, "")
        for char in bot_response:
            history[-1] = (user_message, history[-1][1] + char)
            time.sleep(0.01)
            yield history, gr.update(interactive=False)

        yield history, gr.update(interactive=True)

    def start_url_analysis(self, urls_text):
        urls = [url.strip() for url in urls_text.strip().split('\n') if url.strip()]
        if not urls:
            return (
                gr.update(),
                gr.update(),
                gr.update(visible=False),
                gr.update()
            )
        
        url_count = len(urls)
        
        # TODO: Backend function call to scrape and process URLs.
        # The backend function `scrape_and_process_urls(urls: list[str])` should:
        # 1. Take a list of URLs.
        # 2. Crawl/scrape the content from each URL.
        # 3. Process and clean the text.
        # 4. Store the content in a vector database (e.g., ChromaDB) for RAG.
        # 5. Return a context identifier or a success message. For now, we just return the count.
        self.url_context = f"Analysis complete for {url_count} URLs."
        
        initial_message = (None, f"I've successfully analyzed content from {url_count} URL{'s' if url_count > 1 else ''}. You can now ask me questions about the scraped content!")
        
        return (
            gr.update(value=[initial_message]),
            gr.update(value="Start Analysis", interactive=False),
            gr.update(visible=True, value=f'<div class="context-banner"><strong>Active Context:</strong> Analyzing content from {url_count} URLs</div>'),
            gr.update(interactive=True) # Enable chat input
        )

    def update_url_count(self, urls_text):
        urls = [url.strip() for url in urls_text.strip().split('\n') if url.strip()]
        url_count = len(urls)
        return f"{url_count} URL{'s' if url_count != 1 else ''} entered"

    def new_chat(self):
        self.broad_chat_history = []
        self.url_chat_history = []
        self.url_context = ""
        return (
            [], # Clear broad chat
            [], # Clear url chat
            "", # Clear url input
            "0 URLs entered", # Reset url count
            gr.update(visible=False, value=""), # Hide context banner
            gr.update(value="Start Analysis", interactive=True), # Reset scrape button
            gr.update(interactive=False) # Disable URL chat input initially
        )

    def build_ui(self):
        with gr.Blocks(css=css, theme=gr.themes.Base()) as demo:
            with gr.Row(elem_classes="main"):
                # Sidebar
                with gr.Column(elem_classes="sidebar"):
                    gr.HTML('''
                        <div class="sidebar-header">
                            <div class="sidebar-logo">
                                <img src="https://api.iconify.design/fluent:bot-24-regular.svg" alt="Bot Icon"/>
                                Web Scraper Bot
                            </div>
                            <div class="sidebar-search">
                                <input type="text" placeholder="Search chats..." />
                            </div>
                        </div>
                    ''')
                    new_chat_btn = gr.Button("New chat", elem_classes="new-chat-btn")
                    gr.HTML(f'<div class="chat-history">{mock_chat_history_html}</div>')

                # Main Content
                with gr.Column(elem_classes="main-content"):
                    with gr.Tabs(elem_classes="tab-nav") as tabs:
                        with gr.Tab("Broad Search", id="broad"):
                            with gr.Column(elem_classes="chat-container"):
                                broad_chatbot = gr.Chatbot(
                                    elem_id="broad-chatbot",
                                    elem_classes="chat-messages",
                                    value=[],
                                    show_label=False,
                                    bubble_full_width=False,
                                    height=500
                                )
                                with gr.Row(elem_classes="chat-input-container"):
                                    broad_chat_input = gr.Textbox(
                                        placeholder="Ask me anything...",
                                        show_label=False,
                                        elem_classes="chat-input",
                                        scale=4
                                    )
                                    broad_send_btn = gr.Button("⟶", elem_classes="send-btn")

                        with gr.Tab("URL Analysis", id="url"):
                            with gr.Column(elem_classes="url-input-section"):
                                url_input = gr.Textbox(
                                    label="Enter URLs to analyze (one per line):",
                                    placeholder="https://example.com\nhttps://university.edu/admissions",
                                    lines=4,
                                    elem_classes="url-input"
                                )
                                with gr.Row(elem_classes="url-actions"):
                                    url_count_display = gr.Markdown("0 URLs entered", elem_classes="url-count")
                                    scrape_btn = gr.Button("Start Analysis", elem_classes="scrape-btn")
                            
                            context_banner = gr.HTML(visible=False, elem_classes="context-banner")

                            with gr.Column(elem_classes="chat-container"):
                                url_chatbot = gr.Chatbot(
                                    elem_id="url-chatbot",
                                    elem_classes="chat-messages",
                                    value=[],
                                    show_label=False,
                                    bubble_full_width=False,
                                    height=500
                                )
                                with gr.Row(elem_classes="chat-input-container"):
                                    url_chat_input = gr.Textbox(
                                        placeholder="Enter a question about the analyzed content...",
                                        show_label=False,
                                        elem_classes="chat-input",
                                        scale=4,
                                        interactive=False # Disabled until analysis is done
                                    )
                                    url_send_btn = gr.Button("⟶", elem_classes="send-btn")

            # Event Handlers
            broad_chat_input.submit(
                self.add_broad_chat_message,
                [broad_chat_input, broad_chatbot],
                [broad_chatbot, broad_chat_input]
            )
            broad_send_btn.click(
                self.add_broad_chat_message,
                [broad_chat_input, broad_chatbot],
                [broad_chatbot, broad_chat_input]
            )

            url_input.input(self.update_url_count, url_input, url_count_display)
            
            scrape_btn.click(
                self.start_url_analysis,
                [url_input],
                [url_chatbot, scrape_btn, context_banner, url_chat_input]
            )

            url_chat_input.submit(
                self.add_url_chat_message,
                [url_chat_input, url_chatbot],
                [url_chatbot, url_chat_input]
            )
            url_send_btn.click(
                self.add_url_chat_message,
                [url_chat_input, url_chatbot],
                [url_chatbot, url_chat_input]
            )
            
            new_chat_btn.click(
                self.new_chat,
                [],
                [broad_chatbot, url_chatbot, url_input, url_count_display, context_banner, scrape_btn, url_chat_input]
            )

        return demo

if __name__ == "__main__":
    app = WebScraperApp()
    app.build_ui().launch()
