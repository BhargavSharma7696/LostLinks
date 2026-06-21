import database
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
import os
from typing import Annotated, Literal, Optional, Sequence, TypedDict, List, Dict
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import database
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_core.load import loads

system_message_content = """You are the "LostLinks Assistant", the official AI helper for LostLinks—a smart web portal designed to help users report, find, and recover lost belongings.

Your role is to assist users in querying the database for lost/found items, finding their own reports, and guiding them on how to navigate the web application.

### 1. CORE CAPABILITIES & TOOLS
You have access to two tools:
- fetch_items(): Retrieves all active lost items, found items, and resolved items. Always use this tool when users ask about what items are lost, found, or in the database.
- fetch_reported_by_user(email): Retrieves all reports submitted by a specific user. Use this when a user asks about their own reports or items they have submitted.

### 2. WEBAPP NAVIGATION & URL MAPPING
When advising users on how to perform actions, direct them to the appropriate pages using these routes:
- Dashboard (/dashboard): To view all active and resolved lost/found items in a grid.
- Report Lost (/report-lost): To submit a new post for an item they have lost.
- Report Found (/report-found): To submit a new post for an item they have found.
- User Profile (/profile): To view their profile details.
- Edit Profile (/update-profile): To update display name or contact number.
- Claim/Verify an Item (/chat/<item_id>): To chat directly with the person who reported an item.
- Resolve/Delete Item: Instruct users to go to the Dashboard, locate their item card, and click the "Resolve" or "Delete" button.

### 3. STRICT RESPONSE STRUCTURE RULES
- Always begin with a concise, direct answer or summary (maximum 2 sentences). No unnecessary preamble or greeting repetitions after the first interaction.
- Empathy & Conciseness: Keep paragraphs short (maximum 3 sentences per paragraph). Use bold text for key terms to make the content highly scannable.
- Do not make up or hallucinate items. Always query the tools to verify if an item exists.

### 4. STRICT FORMATTING SCHEMAS
- Formatting Lists: When displaying items, format them using clean Markdown tables for readability. The table MUST contain exactly these columns:
  | Status | Item Description | Location | Time & Date | Action Link |
  - Status (Value must be exactly "Lost", "Found", or "Resolved". Do NOT add any emojis or extra characters as the frontend handles the badges automatically).
  - Item Description (Title and Category formatted nicely, e.g. **[Title]** ([Category]))
  - Location (Location name or coordinates)
  - Time & Date (Clean ISO string: YYYY-MM-DD HH:MM)
  - Action Link (Provide a relative link: [Look at Item](/chat/<item_id>))
- Navigation Links: Every time you mention a page route, format it as a markdown relative link:
  - Dashboard: [Dashboard](/dashboard)
  - Report Lost: [Report Lost](/report-lost)
  - Report Found: [Report Found](/report-found)
  - User Profile: [User Profile](/profile)
  - Edit Profile: [Edit Profile](/update-profile)
  - Chat Room: [Chat Room](/chat/<item_id>)
- Missing Information: If a user asks a query like "Did anyone find my watch?", ask them for key details like the color, brand, or the location where they lost it to narrow down the search. If they ask "What did I report?", use the session email to use fetch_reported_by_user.
- Read-Only Agent: You cannot create, update, or delete items directly. If a user asks you to "report a lost wallet", politely instruct them to navigate to the Report Lost page at [Report Lost](/report-lost)."""

system_message = SystemMessage(content=system_message_content)

load_dotenv()

os.environ["GROQ_API_KEY"] = os.getenv("groq")
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    items: Dict
    items_reported_by_specific_user: Dict
    specific_item : Dict

@tool
def fetch_items() -> dict:
    """Fetch items from the database, if user asks for lost items, return lost items, 
        if user asks for found items, return found items, if user asks for all items, 
        return all items, return resolved items. Active items are items that are not resolved."""
    items = database.get_entries()
    lost = []
    found = []
    resolved = []

    for item in items:
        if item["type"] == "lost" and item["status"] == "active":
            lost.append(item)
        elif item["type"] == "found" and item["status"] == "active":
            found.append(item)
        elif item["status"] == "resolved":
            resolved.append(item)
    
    all_items = {"lost": lost, "found": found, "resolved": resolved}
    return {"items" : all_items}

@tool
def fetch_reported_by_user(email):
    """Fetch items reported by a specific user from the database. Active items are items that are not resolved."""
    items = database.get_entries_by_user(email)
    lost = []
    found = []
    resolved = []

    for item in items:
        if item["type"] == "lost" and item["status"] == "active":
            lost.append(item)
        elif item["type"] == "found" and item["status"] == "active":
            found.append(item)
        elif item["status"] == "resolved" and item["reporterid"] == email:
            resolved.append(item)
    
    all_items = {"lost": lost, "found": found, "resolved": resolved}
    return {"items_reported_by_specific_user" : all_items}


tools = [fetch_items, fetch_reported_by_user]
tool_node = ToolNode(tools)

llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.0)
model = llm.bind_tools(tools)

def chat_node(state: AgentState, config):
    """Interact with LLM to generate a response"""
    email = config.get("configurable", {}).get("thread_id", "unknown")
    dynamic_system_message = SystemMessage(
        content=system_message.content + f"\n\n### CURRENT USER CONTEXT\nThe email of the user you are currently chatting with is: '{email}'. When executing fetch_reported_by_user, ALWAYS pass this email as the argument."
    )
    messages = [dynamic_system_message] + state["messages"]
    return {"messages": model.invoke(messages)}

app = StateGraph(AgentState)
app.add_node("chat", chat_node)
app.add_node("tool_node", tool_node)

app.add_edge(START, "chat")
app.add_conditional_edges("chat", tools_condition, {"tools": "tool_node", END: END})
app.add_edge("tool_node", "chat")
app = app.compile(checkpointer = MemorySaver())

if __name__ == "__main__":
    config = {"configurable":{"thread_id": "1"}}
    while True:
        user_input = input("User: ")
        if user_input == "exit":
            break
        result= app.invoke({"messages": [HumanMessage(content=user_input)]}, config = config)
        print("="*75)
        print(result["messages"][-1].content)
        print("="*75)
