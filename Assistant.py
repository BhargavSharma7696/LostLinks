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
from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.load import loads
import difflib
import re
import google.generativeai as genai

system_message_content = """You are the "LostLinks Assistant", the official AI helper for LostLinks—a smart web portal designed to help users report, find, and recover lost belongings.

Your role is to assist users in querying the database for lost/found items, finding their own reports, and guiding them on how to navigate the web application.

### 1. CORE CAPABILITIES & TOOLS
You have access to these tools:
- fetch_items(): Retrieves all active lost items, found items, and resolved items. Always use this tool when users ask about what items are lost, found, or in the database.
- fetch_reported_by_user(email): Retrieves all reports submitted by a specific user. Use this when a user asks about their own reports or items they have submitted.
- fetch_items_nearby(location): Retrieves active items that are nearby a specific campus landmark. Always use this tool when a user asks about items lost, found, or reported near a particular location (e.g., a hostel, Mess, ground, parking, etc.).
- fetch_similar_items(query_text): Retrieves items similar to the query_text using vector similarity. Always use this tool when a user asks about items similar to a given text.

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

LANDMARKS = {"kanhar" : (21.2448, 81.3219),
      "shivnath" : (21.2406, 81.32015),
      "indravati" : (21.24311, 81.32076),
      "gopad" : (21.244, 81.32065),
      "tech cafe" : (21.24368, 81.32092),
      "njc" : (21.24330, 81.32030),
      "mess" : (21.24354, 81.3219),
      "mess parking" : (21.24315, 81.32165),
      "kanhar parking" : (21.24474, 81.32102),
      "lhc 500" : (21.24610, 81.31899),
      "lhc 300" : (21.24583, 81.31848),
      "ed 1" : (21.24591, 81.31787),
      "ed 2" : (21.24625, 81.31769),
      "sd 1" : (21.24731, 81.31996),
      "sd 2" : (21.24766, 81.31980),
      "cif" : (21.24731, 81.31868),
      "health centre" : (21.24207, 81.31323),
      "lh 101" : (21.24548, 81.31921),
      "lh 102" : (21.24548, 81.31921),
      "lh 103" : (21.24548, 81.31921),
      "lh 104" : (21.24548, 81.31921),
      "lh 105" : (21.24548, 81.31921),
      "lh 106" : (21.24548, 81.31921),
      "lh 107" : (21.24548, 81.31921),
      "lh 108" : (21.24548, 81.31921),
      "lh 201" : (21.24548, 81.31921),
      "lh 202" : (21.24548, 81.31921),
      "lh 203" : (21.24548, 81.31921),
      "lh 204" : (21.24548, 81.31921),
      "lh 205" : (21.24548, 81.31921),
      "lh 206" : (21.24548, 81.31921),
      "lh 207" : (21.24548, 81.31921),
      "lh 208" : (21.24548, 81.31921),
      "ldc" : (21.24643, 81.31966),
      "shopping complex" : (21.24178, 81.31345),
      "at mart" : (21.24178, 81.31345),
      "cpf" : (21.24780, 81.31793),
      "basketball" : (21.24613, 81.32187),
      "volleyball" : (21.24613, 81.32187),
      "football ground" : (21.24711, 81.32187),
      "cricket ground" : (21.24711, 81.32187),
      "gate 1" : (21.24605, 81.31322),
      "gate 2" : (21.23965, 81.3201)
}


system_message = SystemMessage(content=system_message_content)

load_dotenv()

os.environ["GROQ_API_KEY"] = os.getenv("groq")
api_key = os.getenv("gemini_key")
genai.configure(api_key=api_key)
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    items: Dict
    items_reported_by_specific_user: Dict
    nearby_items: Dict
    similar_items: Dict

@tool
def fetch_items() -> dict:
    """Fetch items from the database, if user asks for lost items, return lost items, 
        if user asks for found items, return found items, if user asks for all items, 
        return all items, return resolved items. Active items are items that are not resolved.
        Args:
            No Args Required
        Returns:
            A dictionary containing the similar items.
        USE THE TOOL ALWAYS TO KNOW ABOUT ALL THE ITEMS REPORTED FROM THE DATABASE, NEVER HALUCINATE AN ITEM"""
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
    """Fetch items reported by a specific user from the database. Active items are items that are not resolved.
    Args:
        email: The email of the user to fetch items for.
    Returns:
        A dictionary containing the items reported by the specific user."""
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

def find_landmark(location_str: str) -> Optional[str]:
    if not location_str or not isinstance(location_str, str):
        return None
    
    loc = location_str.strip().lower()

    if loc in LANDMARKS:
        return loc
    for key in LANDMARKS:
        if key in loc or loc in key:
            return key
    loc_norm = re.sub(r'[^a-z0-9]', '', loc)
    for key in LANDMARKS:
        key_norm = re.sub(r'[^a-z0-9]', '', key)
        if key_norm == loc_norm or key_norm in loc_norm or loc_norm in key_norm:
            return key
    matches = difflib.get_close_matches(loc, LANDMARKS.keys(), n=1, cutoff=0.5)
    if matches:
        return matches[0]
    return None

@tool
def fetch_items_nearby(location):
    """Fetch items that are nearby to the given location. Return the items in a list.
    Example query : 1. tell me reports in area lhc 500 --> location = lhc 500
                    2. can you find items lost or found nearby Kanhar --> location = kanhar
                    3. lost items near shopping complex --> location = shopping complex
                    4. find lost items near CIF --> location = cif
                    5. find found items near mess --> location = mess
    The location argument must be one of the known landmarks:
    kanhar, shivnath, indravati, gopad, tech cafe, njc, mess, mess parking, 
    kanhar parking, lhc 500, lhc 300, ed 1, ed 2, sd 1, sd 2, cif, health centre, 
    lh 101, lh 102, lh 103, lh 104, lh 105, lh 106, lh 107, lh 108, lh 201, lh 202, 
    lh 203, lh 204, lh 205, lh 206, lh 207, lh 208, ldc, shopping complex, at mart, 
    cpf, basketball, volleyball, football ground, cricket ground, gate 1, gate 2.
    Args:
        location : Reports to been found or lost nearby this location.
    Returns:
        A dictionary containing the items nearby to the given location.
    """
    matched_loc = find_landmark(location)
    if not matched_loc:
        return {"nearby_items": [], "error": f"Could not find a matching landmark for '{location}'."}
        
    lat_user, lon_user = LANDMARKS[matched_loc]
    items = database.get_entries()
    nearby_items = []
    for item in items:
        item_loc_str = item.get("location")
        if item_loc_str:
            matched_item_loc = find_landmark(item_loc_str)
            if matched_item_loc:
                lat_item, lon_item = LANDMARKS[matched_item_loc]
                if abs(lat_user - lat_item) < 0.002 and abs(lon_user - lon_item) < 0.002:
                    nearby_items.append(item)
    return {"nearby_items" : nearby_items}

@tool
def fetch_similar_items(query_text):
    """
    Searches for items similar to the query_text using vector similarity. 
    Args:
        query_text: The text to search for.
    Returns:
        A dictionary containing the similar items.
    """
    try:
        result = genai.embed_content( model="models/gemini-embedding-2", content=query_text, task_type="retrieval_document", output_dimensionality=256)
        query_embedding = result['embedding']
    except Exception as e:
        return {"error": f"Error generating query embedding: {str(e)}"}

    all_items = database.get_entries_with_embeddings()
    if not all_items:
        return {"similar_items": [], "message": "No items found in the database"}

    scores = []
    for item in all_items:
        try:
            item_embedding = eval(item["embeddings"])
            score = cosine_similarity([query_embedding], [item_embedding])[0][0]
            scores.append((score, item))
        except Exception as e:
            print(f"Error processing item {item.get('id')}: {e}")
            continue

    scores.sort(key=lambda x: x[0], reverse=True)
    similar_items = [item[1] for item in scores[:3]]

    return {"similar_items": similar_items}

tools = [fetch_items, fetch_reported_by_user, fetch_items_nearby, fetch_similar_items]
tool_node = ToolNode(tools)

# llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.0)
llm = ChatGroq(model_name = "openai/gpt-oss-20b", temperature = 0.0)
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
