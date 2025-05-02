import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict, Union

# LangGraph and LangChain imports
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# Initialize the LLM
#llm = ChatAnthropic(model="claude-3-haiku-20240307")
llm= ChatGoogleGenerativeAI(model="gemini-2.0-flash-001", temperature=0.2, max_output_tokens=2048,max_retries=2)

# Define database path
DB_PATH = "customer_support.db"

# ==================== DATABASE SETUP ====================

def setup_database():
    """Create the database and populate it with sample data."""
    # Check if database exists, if not create it
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)  # Remove existing DB for fresh start
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute('''
    CREATE TABLE users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        membership_level TEXT,
        created_at TEXT
    )
    ''')
    
    # Create Products table
    cursor.execute('''
    CREATE TABLE products (
        product_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        category TEXT,
        in_stock INTEGER
    )
    ''')
    
    # Create Orders table
    cursor.execute('''
    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT NOT NULL,
        total_amount REAL NOT NULL,
        payment_method TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Create Order_Items table (for items in each order)
    cursor.execute('''
    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price_at_purchase REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    )
    ''')
    
    # Create Shipping table
    cursor.execute('''
    CREATE TABLE shipping (
        shipping_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        tracking_number TEXT,
        carrier TEXT,
        shipping_date TEXT,
        estimated_delivery TEXT,
        actual_delivery TEXT,
        status TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
    )
    ''')
    
    # Create Support_Tickets table
    cursor.execute('''
    CREATE TABLE support_tickets (
        ticket_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        order_id TEXT,
        created_at TEXT NOT NULL,
        subject TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        priority TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
    )
    ''')
    
    # Insert sample data
    
    # Users
    users = [
        ('U12345', 'John Doe', 'john.doe@example.com', '555-123-4567', '123 Main St, Springfield', 'Gold', '2022-01-15'),
        ('U67890', 'Jane Smith', 'jane.smith@example.com', '555-987-6543', '456 Oak Ave, Rivertown', 'Silver', '2022-03-20'),
        ('U11223', 'Bob Johnson', 'bob.johnson@example.com', '555-222-3333', '789 Pine Rd, Lakeside', 'Bronze', '2022-05-10')
    ]
    cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)', users)
    
    # Products
    products = [
        ('P1001', 'Smartphone X', '6.7-inch display, 256GB storage', 999.99, 'Electronics', 1),
        ('P1002', 'Laptop Pro', '15-inch, 16GB RAM, 512GB SSD', 1299.99, 'Electronics', 1),
        ('P1003', 'Wireless Headphones', 'Noise cancelling, 20hr battery', 199.99, 'Audio', 1),
        ('P1004', 'Smart Watch', 'Fitness tracker, heart monitor', 249.99, 'Wearables', 0),
        ('P1005', 'Coffee Maker', 'Programmable, 12-cup', 79.99, 'Kitchen', 1)
    ]
    cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)', products)
    
    # Orders
    orders = [
        ('ORD-2024-001', 'U12345', '2024-03-15', 'Delivered', 1199.98, 'Credit Card'),
        ('ORD-2024-002', 'U67890', '2024-03-18', 'Shipped', 199.99, 'PayPal'),
        ('ORD-2024-003', 'U11223', '2024-03-20', 'Processing', 1299.99, 'Credit Card'),
        ('ORD-2024-004', 'U12345', '2024-04-05', 'Cancelled', 249.99, 'Credit Card'),
        ('ORD-2024-005', 'U67890', '2024-04-10', 'Processing', 79.99, 'PayPal')
    ]
    cursor.executemany('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)', orders)
    
    # Order Items
    order_items = [
        ('ORD-2024-001', 'P1001', 1, 999.99),
        ('ORD-2024-001', 'P1003', 1, 199.99),
        ('ORD-2024-002', 'P1003', 1, 199.99),
        ('ORD-2024-003', 'P1002', 1, 1299.99),
        ('ORD-2024-004', 'P1004', 1, 249.99),
        ('ORD-2024-005', 'P1005', 1, 79.99)
    ]
    cursor.executemany('INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (?, ?, ?, ?)', order_items)
    
    # Shipping
    shipping_data = [
        ('SH1001', 'ORD-2024-001', 'TRK123456789', 'FedEx', '2024-03-16', '2024-03-19', '2024-03-18', 'Delivered'),
        ('SH1002', 'ORD-2024-002', 'TRK987654321', 'UPS', '2024-03-19', '2024-03-22', None, 'In Transit'),
        ('SH1003', 'ORD-2024-003', None, None, None, None, None, 'Pending'),
        ('SH1004', 'ORD-2024-004', None, None, None, None, None, 'Cancelled'),
        ('SH1005', 'ORD-2024-005', None, None, None, None, None, 'Pending')
    ]
    cursor.executemany('INSERT INTO shipping VALUES (?, ?, ?, ?, ?, ?, ?, ?)', shipping_data)
    
    # Support Tickets
    tickets = [
        ('TKT-001', 'U12345', 'ORD-2024-001', '2024-03-20', 'Missing item', 'One item was missing from my order', 'Resolved', 'Medium'),
        ('TKT-002', 'U67890', 'ORD-2024-002', '2024-03-21', 'Shipping delay', 'My order has not arrived yet', 'Open', 'High'),
        ('TKT-003', 'U11223', None, '2024-03-22', 'Account access', 'I cannot log into my account', 'In Progress', 'Low')
    ]
    cursor.executemany('INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)', tickets)
    
    conn.commit()
    conn.close()
    
    print("Database created and populated with sample data!")

# ==================== DATABASE TOOLS ====================

@tool
def get_customer_info(user_id: str) -> Dict[str, Any]:
    """
    Retrieve customer information from the database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return {"error": f"No customer found with ID {user_id}"}
    
    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "address": user["address"],
        "membership_level": user["membership_level"],
        "created_at": user["created_at"]
    }

@tool
def get_order_details(order_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed information about a specific order.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get order information
    cursor.execute("""
        SELECT o.*, u.name as customer_name 
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        WHERE o.order_id = ?
    """, (order_id,))
    
    order = cursor.fetchone()
    if not order:
        conn.close()
        return {"error": f"No order found with ID {order_id}"}
    
    # Get order items
    cursor.execute("""
        SELECT oi.*, p.name as product_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """, (order_id,))
    
    items = [dict(item) for item in cursor.fetchall()]
    
    # Get shipping information
    cursor.execute("SELECT * FROM shipping WHERE order_id = ?", (order_id,))
    shipping = cursor.fetchone()
    
    conn.close()
    
    result = {
        "order_id": order["order_id"],
        "user_id": order["user_id"],
        "customer_name": order["customer_name"],
        "order_date": order["order_date"],
        "status": order["status"],
        "total_amount": order["total_amount"],
        "payment_method": order["payment_method"],
        "items": items
    }
    
    if shipping:
        result["shipping"] = dict(shipping)
    
    return result

@tool
def get_customer_orders(user_id: str) -> Dict[str, Any]:
    """
    Retrieve all orders for a specific customer.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT o.*, s.status as shipping_status, s.tracking_number, s.estimated_delivery
        FROM orders o
        LEFT JOIN shipping s ON o.order_id = s.order_id
        WHERE o.user_id = ?
        ORDER BY o.order_date DESC
    """, (user_id,))
    
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        return {"error": f"No orders found for customer {user_id}"}
    
    result = {"user_id": user_id, "orders": [dict(order) for order in orders]}
    return result

@tool
def track_order_shipping(order_id: str) -> Dict[str, Any]:
    """
    Get shipping and tracking information for an order.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.*, o.user_id, o.order_date, o.status as order_status
        FROM shipping s
        JOIN orders o ON s.order_id = o.order_id
        WHERE s.order_id = ?
    """, (order_id,))
    
    shipping = cursor.fetchone()
    conn.close()
    
    if not shipping:
        return {"error": f"No shipping information found for order {order_id}"}
    
    return dict(shipping)

@tool
def get_customer_support_tickets(user_id: str) -> Dict[str, Any]:
    """
    Get all support tickets for a specific customer.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM support_tickets
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    tickets = cursor.fetchall()
    conn.close()
    
    if not tickets:
        return {"error": f"No support tickets found for customer {user_id}"}
    
    return {"user_id": user_id, "tickets": [dict(ticket) for ticket in tickets]}

@tool
def get_ticket_details(ticket_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific support ticket.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.*, u.name as customer_name
        FROM support_tickets t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.ticket_id = ?
    """, (ticket_id,))
    
    ticket = cursor.fetchone()
    conn.close()
    
    if not ticket:
        return {"error": f"No ticket found with ID {ticket_id}"}
    
    return dict(ticket)

@tool
def create_support_ticket(
    user_id: str, 
    subject: str, 
    description: str, 
    order_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new support ticket for a customer.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verify the user exists
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        return {"error": f"No customer found with ID {user_id}"}
    
    # Verify the order exists if provided
    if order_id:
        cursor.execute("SELECT order_id FROM orders WHERE order_id = ?", (order_id,))
        if not cursor.fetchone():
            conn.close()
            return {"error": f"No order found with ID {order_id}"}
    
    # Generate new ticket ID
    ticket_id = f"TKT-{str(uuid.uuid4())[:8]}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Insert new ticket
    cursor.execute("""
        INSERT INTO support_tickets 
        (ticket_id, user_id, order_id, created_at, subject, description, status, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, user_id, order_id, created_at, subject, description, "Open", "Medium"))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": "Support ticket created successfully",
        "ticket_id": ticket_id,
        "created_at": created_at
    }

@tool
def check_product_availability(product_id: str) -> Dict[str, Any]:
    """
    Check if a product is available in stock.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        return {"error": f"No product found with ID {product_id}"}
    
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "price": product["price"],
        "in_stock": bool(product["in_stock"]),
        "availability": "In Stock" if product["in_stock"] else "Out of Stock"
    }

@tool
def search_orders_by_date(user_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Search for customer orders within a specific date range.
    Format: YYYY-MM-DD
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM orders
        WHERE user_id = ? AND order_date BETWEEN ? AND ?
        ORDER BY order_date DESC
    """, (user_id, start_date, end_date))
    
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        return {"error": f"No orders found for customer {user_id} between {start_date} and {end_date}"}
    
    return {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date,
        "orders": [dict(order) for order in orders]
    }

@tool
def update_customer_address(user_id: str, new_address: str) -> Dict[str, Any]:
    """
    Update a customer's address in the database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        return {"error": f"No customer found with ID {user_id}"}
    
    cursor.execute("""
        UPDATE users
        SET address = ?
        WHERE user_id = ?
    """, (new_address, user_id))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"Address updated successfully for customer {user_id}",
        "new_address": new_address
    }

# ==================== LANGGRAPH STATE AND NODES ====================

# Define the graph state
class State(TypedDict):
    """State for the customer support agent graph."""
    messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
    user_id: Optional[str]
    current_query_type: Optional[str]
    error: Optional[str]
    tool_results: Optional[Dict[str, Any]]

# List of available tools
tools = [
    get_customer_info,
    get_order_details,
    get_customer_orders,
    track_order_shipping,
    get_customer_support_tickets,
    get_ticket_details,
    create_support_ticket,
    check_product_availability,
    search_orders_by_date,
    update_customer_address
]

# Define graph nodes
def query_classifier(state: State) -> Dict[str, Any]:
    """Classify the user's query to determine which actions to take."""
    messages = state["messages"]
    human_message = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    
    # Generate a system prompt
    prompt = f"""You are a customer service query classifier.
    Your job is to identify what type of support query the customer is asking about.
    
    Query types:
    - account_info: Questions about account details
    - order_status: Questions about order status or details
    - shipping_tracking: Questions about shipping or tracking information
    - support_ticket: Questions about support tickets or creating new tickets
    - product_info: Questions about product availability or details
    - address_update: Requests to update address information
    - general: General questions or greetings
    
    Customer query: {human_message}
    
    Return only the query type as a single word.
    """
    
    response = llm.invoke([
        HumanMessage(content=prompt)
    ])
    
    query_type = response.content.strip().lower()
    
    # Validate and normalize the query type
    valid_types = ["account_info", "order_status", "shipping_tracking", 
                  "support_ticket", "product_info", "address_update", "general"]
    
    if query_type not in valid_types:
        query_type = "general"
    
    return {"current_query_type": query_type}

def detect_user_id(state: State) -> Dict[str, Any]:
    """Extract user ID from the message or ask for it if not present."""
    messages = state["messages"]
    current_user_id = state.get("user_id")
    
    # If we already have a user ID, return it
    if current_user_id:
        return {"user_id": current_user_id}
    
    # Try to extract user ID from the last message
    human_message = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    
    prompt = f"""Extract the user ID from the following message if present.
    User IDs typically start with 'U' followed by numbers (e.g., U12345).
    If no user ID is found, respond with 'None'.
    
    Message: {human_message}
    
    Return only the user ID or 'None'.
    """
    
    response = llm.invoke([
        HumanMessage(content=prompt)
    ])
    
    extracted_id = response.content.strip()
    
    # Validate the format
    if extracted_id.startswith('U') and extracted_id[1:].isdigit():
        return {"user_id": extracted_id}
    else:
        # Return a message asking for user ID
        return {
            "messages": [AIMessage(content="I need your customer ID to assist you. Please provide your customer ID (it starts with 'U' followed by numbers, e.g., U12345).")],
            "current_query_type": "general"
        }

def execute_tools(state: State) -> Dict[str, Any]:
    """Execute the appropriate tools based on query type."""
    query_type = state.get("current_query_type", "general")
    user_id = state.get("user_id")
    messages = state["messages"]
    human_message = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    
    results = {}
    
    if query_type == "account_info" and user_id:
        results = get_customer_info(user_id)
    
    elif query_type == "order_status" and user_id:
        # First check if there's a specific order ID mentioned
        prompt = f"""Extract the order ID from the following message if present.
        Order IDs typically start with 'ORD-' followed by numbers and letters.
        If no order ID is found, respond with 'None'.
        
        Message: {human_message}
        
        Return only the order ID or 'None'.
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        order_id = response.content.strip()
        
        if order_id.startswith('ORD-'):
            results = get_order_details(order_id)
        else:
            results = get_customer_orders(user_id)
    
    elif query_type == "shipping_tracking":
        prompt = f"""Extract the order ID from the following message if present.
        Order IDs typically start with 'ORD-' followed by numbers and letters.
        If no order ID is found, respond with 'None'.
        
        Message: {human_message}
        
        Return only the order ID or 'None'.
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        order_id = response.content.strip()
        
        if order_id.startswith('ORD-'):
            results = track_order_shipping(order_id)
        elif user_id:
            # Get all orders for the user
            results = get_customer_orders(user_id)
    
    elif query_type == "support_ticket":
        # Check if they're asking about existing tickets or creating a new one
        if "new" in human_message.lower() or "create" in human_message.lower():
            # For this demo we'll just return info about creating tickets
            results = {
                "message": "To create a new support ticket, please provide: subject, description, and optionally an order ID."
            }
        elif user_id:
            results = get_customer_support_tickets(user_id)
    
    elif query_type == "product_info":
        prompt = f"""Extract the product ID from the following message if present.
        Product IDs typically start with 'P' followed by numbers.
        If no product ID is found, respond with 'None'.
        
        Message: {human_message}
        
        Return only the product ID or 'None'.
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        product_id = response.content.strip()
        
        if product_id.startswith('P'):
            results = check_product_availability(product_id)
        else:
            results = {
                "message": "I can only check availability for specific products using their product ID (e.g., P1001). I cannot perform general product searches or browse catalogs."
            }
    
    elif query_type == "address_update":
        # For this demo we'll just return info about updating address
        results = {
            "message": "To update your address, please provide your new address."
        }
    
    # Default to returning user info if we have user_id
    elif user_id:
        results = get_customer_info(user_id)
    else:
        results = {
            "message": "I need your customer ID to assist you. Please provide your customer ID (it starts with 'U' followed by numbers, e.g., U12345)."
        }
        
    return {"tool_results": results}

def generate_response(state: State) -> Dict[str, Any]:
    """Generate a response based on tool results and conversation history."""
    messages = state["messages"]
    query_type = state.get("current_query_type", "general")
    tool_results = state.get("tool_results", {})
    user_id = state.get("user_id")
    
    # Create a system prompt
    system_prompt = """You are a helpful customer support agent for an e-commerce store.
    Your job is to assist customers with their queries about orders, shipping, products, and account information.
    Be polite, helpful, and concise.
    
    IMPORTANT LIMITATIONS:
    1. You can only help with customer support queries related to orders, shipping, products, and account information
    2. You cannot perform general searches or browse products
    3. You need a valid customer ID to access customer-specific information
    4. You can only check product availability using product IDs
    5. You cannot provide general product recommendations or browse catalogs
    
    Based on the query type and tool results, provide a helpful response to the customer.
    If the query is outside your scope, politely inform the customer about your limitations.
    If there was an error in the tool results, apologize and ask for clarification.
    If the exact query is not clear, ask the customer for more details (like order ID, product ID, etc.).
    """
    
    # Prepare context for the LLM
    context = f"""
    Customer ID: {user_id if user_id else 'Unknown'}
    Query Type: {query_type}
    
    Tool Results:
    {tool_results}
    """
    
    # Get the last few messages for context (limit to 5 for brevity)
    recent_messages = messages[-5:] if len(messages) > 5 else messages
    message_history = "\n".join([
        f"{'Customer' if isinstance(msg, HumanMessage) else 'Agent'}: {msg.content}"
        for msg in recent_messages
    ])
    
    prompt = f"""
    {system_prompt}
    
    Context Information:
    {context}
    
    Recent Message History:
    {message_history}
    
    Generate a helpful response to the customer's latest query.
    If the query is about searching or browsing products, politely inform them that you can only check specific product availability using product IDs.
    """
    
    response = llm.invoke([
        HumanMessage(content=prompt)
    ])
    
    return {"messages": [AIMessage(content=response.content)]}

# Define routing logic
def route_based_on_query(state: State) -> str:
    """Route to the appropriate next node based on the query type."""
    query_type = state.get("current_query_type", "general")
    
    if query_type == "general":
        return "generate_response"
    else:
        return "execute_tools"

# ==================== LANGGRAPH SETUP ====================

def build_graph():
    """Build the LangGraph for the customer support agent."""
    #we have to refer this module for langgraph cli to pick up and build and visualize in studio
    # Create the graph
    graph = StateGraph(State)
    
    # Add nodes
    graph.add_node("query_classifier", query_classifier)
    graph.add_node("detect_user_id", detect_user_id)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("generate_response", generate_response)
    
    # Define the edges
    graph.add_edge(START, "query_classifier")
    graph.add_edge("query_classifier", "detect_user_id")
    
    # Add conditional edges
    graph.add_conditional_edges(
        "detect_user_id",
        route_based_on_query,
        {
            "generate_response": "generate_response",
            "execute_tools": "execute_tools"
        }
    )
    
    graph.add_edge("execute_tools", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph

# ==================== MAIN APPLICATION ====================

def run_customer_support_agent():
    #Set up and run the customer support agent
    # Setup the database (POC Verision)
    setup_database()
    
    # Build the graph
    builder = build_graph()
    
    # Setup persistence with memory saver
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    print("Customer Support Agent is ready! Type 'exit' to quit.")
    print("Example queries:") 
    print("- Hello, I'm John Doe, customer U12345. What are my recent orders?")
    print("- Can you check the status of order ORD-2024-002?")
    print("- I want to create a support ticket for my missing item.")
    print("- What's the tracking number for my last order?")
    print()
    
    # Create a unique thread ID for this conversation
    thread_id = str(uuid.uuid4())
    
    while True:
        # Get user input
        user_input = input("Customer: ")
        if user_input.lower() == "exit":
            break
        
        # Set up config with thread_id for persistence
        config = {"configurable": {"thread_id": thread_id}}
        
        # Create initial state with the human message
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "user_id": None,
            "current_query_type": None,
            "error": None,
            "tool_results": None
        }
        
        # Process user input through the graph
        print("Agent: ", end="", flush=True)
        
        # Stream response
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            if "messages" in event and len(event["messages"]) > 0:
                last_message = event["messages"][-1]
                if isinstance(last_message, AIMessage):
                    print(last_message.content)
        
        print()  # Extra line for readability

if __name__ == "__main__":
    run_customer_support_agent()