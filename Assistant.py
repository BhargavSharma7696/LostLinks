import database
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from typing import Annotated, Literal, Optional, TypedDict, List, Dict, Union
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from sklearn.metrics.pairwise import cosine_similarity
import difflib, re, requests, base64, os
import google.generativeai as genai
from pydantic import BaseModel, Field


system_message_content = """You are the "LostLinks Assistant", the official AI helper for LostLinks—a smart web portal designed to help users report, find, and recover lost belongings.

Your role is to assist users in querying the database for lost/found items, finding their own reports, and guiding them on how to navigate the web application.
Remember if a user says "I lost", "I lost my" or "I lost my watch" or "lost watch" or "my lost watch", it means the user has lost an item. So if user wants to create a report of it type should be lost,
while if the users wants to search/get details/know about a lost item, It means the item if exists in database can bre found under the type "found".
Similarly if the user wants to report an item as found, it means the user has found an item. So if user wants to create a report of it type should be found.

### 1. CORE CAPABILITIES & TOOLS
You have access to these tools:
- fetch_items(): Retrieves all active lost items, found items, and resolved items. Always use this tool when users ask about what items are lost, found, or in the database.
- fetch_reported_by_user(email): Retrieves all reports submitted by a specific user. Use this when a user asks about their own reports or items they have submitted.
- fetch_items_nearby(location): Retrieves active items that are nearby a specific campus landmark. Always use this tool when a user asks about items lost, found, or reported near a particular location (e.g., a hostel, Mess, ground, parking, etc.).
- fetch_similar_items(query_text): Retrieves items similar to the query_text using vector similarity. Always use this tool when a user asks about items similar to a given text.
- make_report(email, title, description, location, category, losttime, image, type): Makes a report for a lost or found item. Always use this tool when a user asks to make a report for a lost or found item.

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
- Read-Only Agent (Except a TOOL CALL called `make_report`): You cannot create, update, or delete items directly. If a user asks you to "report a lost wallet" or "report a bag found", use the tool `make_report()` to make the report.
  - For reporting a FOUND item, uploading/attaching an image is MANDATORY. If the user has not uploaded/attached an image, you MUST ask them to attach or upload an image using the attachment button (📎) next to the chat input before you can submit the report.
  - Do not hallucinate. You can only edit the database when this tool call is made.

### 5. RESPONSE GENERATION RULES
- Keep responses concise and to the point. Do not repeat information that is already known. 
- Do not use any special characters or formatting that may not render properly in markdown. 
- Do not use any emojis or emoticons.
- Do not use any HTML tags or attributes.
- Do not use any JavaScript code.
- Do not use any CSS code.

### 6. EXTRA KNOWLEDGE
- For your knowledge about locations, use this dictionary: LANDMARKS. 
- For your knowledge on categories of item lost, use this list: CATEGORIES. 

### 7. INSTRCTIONS WHILE USING TOOL "make_report(email, title, description, location, category, losttime, image, type)" 
- if you have image, location and losttime, auto generate title, description, category. And before execution confirm from user

"""

CATEGORIES = ["Electronics", "Book & Documents", "Clothing", "Accessories", "Keys & Wallets", "Sports & Fitness", "Other"]

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

# Robust casing fallbacks for API Keys
groq_key = os.getenv("groq") or os.getenv("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = groq_key if groq_key else ""
api_key = os.getenv("gemini_key") or os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    items: Dict
    items_reported_by_specific_user: Dict
    nearby_items: Dict
    similar_items: Dict
    report_tool : Union[Dict, str]

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
        query_embedding = database.embedding_model.encode(query_text).tolist()
    except Exception as e:
        return {"error": f"Error generating query embedding: {str(e)}"}

    all_items = database.get_entries_with_embeddings()
    if not all_items:
        return {"similar_items": [], "message": "No items found in the database"}

    scores = []
    for item in all_items:
        try:
            item_embedding = eval(item["embeddings"])
            if not item_embedding or len(item_embedding) != len(query_embedding):
                item_embedding = database.get_embeddings(item)
            
            if item_embedding:
                score = cosine_similarity([query_embedding], [item_embedding])[0][0]
                scores.append((score, item))
        except Exception as e:
            print(f"Error processing item {item.get('id')}: {e}")
            continue

    scores.sort(key=lambda x: x[0], reverse=True)
    similar_items = []
    for score, item in scores[:3]:
        clean_item = {k: v for k, v in item.items() if k != "embeddings"}
        similar_items.append(clean_item)

    return {"similar_items": similar_items}

class ImageAnalysis(BaseModel):
    """
    Schema for analyzing an item image.
    """
    title: str = Field(description="A title for the item.")
    category: Literal["Electronics", "Books & Documents", "Clothing", "Accessories", "Keys & Wallets", "Sports & Fitness", "Other"]
    description: str = Field(description="A brief description of the item.")

def analyze_item_image(image_url: str) -> dict:
    """
    Downloads and analyzes an item image using Gemini model to extract title, category, and description.
    """
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_bytes = response.content
        mime_type = response.headers.get("Content-Type", "image/jpeg")
    except Exception as e:
        return {"error": f"Error downloading image: {str(e)}"}
    
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        prompt = "Analyze this image of a lost or found item and extract its title, category, and a brief description."
        
        image_part = {
            "mime_type": mime_type,
            "data": image_bytes
        }
        
        response = model.generate_content(
            [prompt, image_part],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ImageAnalysis
            )
        )
        return {"analysis" : ImageAnalysis.model_validate_json(response.text)}
    except Exception as e:
        return {"error": f"Gemini API error: {str(e)}"}

@tool
def make_report(email = None, title = None, description = None, location = None, category = None, image = None, type = None, losttime = None):
    """
    If the user provides details about any founding or lost item, use this tool to make a report for the user.
    If reporting a found item (type='found'), 'image' is strictly MANDATORY. If reporting a lost item, 'image' is optional.
    If all arguments are provided, use this tool to make a report for the user, else prompt user to provide the details of item.
    If you are provided with an image auto generate the details for it such as a title, description, get category, using the function analyze_item_image.
    Args:
        email: The email of the user
        title: The title of the item
        description: The description of the item
        location: The location of the item
        category: The category of the item
        losttime: The time of the item lost/found
        image: The image of the item
        type: The type of the item (lost or found)
    Returns:
        A dictionary containing the report.
    """
    if type == "found":
        if not image or not image.strip():
            return {"report_tool": "An image of the found item is mandatory. Please ask the user to upload or capture a photo first using the attachment button (📎) next to the chat input."}
        if not email or not losttime or not location:
            return {"report_tool": "Please provide atleast basic details: location, found time"}
        if not title or not category or not description:
            analysis = analyze_item_image(image)
            if "error" in analysis:
                return {"report_tool": f"Error analyzing image: {analysis['error']}. Please provide manual details (title, description, and category) or try again."}
            title = analysis["analysis"].title
            category = analysis["analysis"].category
            description = analysis["analysis"].description
        item = {
            "reporterid": email,
            "type": "found",
            "title": title,
            "description": description,
            "location": location,
            "category": category,
            "losttime": losttime,
            "photourl": image
        }
        try:
            print(item)
            database.create_found_entry(item)
            return {"report_tool": f"Success: Found item '{title}' has been reported successfully."}
        except Exception as e:
            return {"report_tool": f"Error reporting found item: {str(e)}"}
            
    elif type == "lost":
        if not email or not title:
            return {"report_tool": "Please provide at least title."}
            
        if image and image.strip() and (not description or not category):
            analysis = analyze_item_image(image)    
            if "error" in analysis:
                return {"report_tool": f"Error analyzing image: {analysis['error']}. Please provide manual details or try again."}
            title = analysis["analysis"].title
            category = analysis["analysis"].category
            description = analysis["analysis"].description

        item = {
            "reporterid": email,
            "type": "lost",
            "title": title,
            "description": description,
            "location": location,
            "category": category,
            "losttime": losttime,
            "photourl": image
        }
        try:
            database.create_lost_entry(item)
            return {"report_tool": f"Success: Lost item '{title}' has been reported successfully."}
        except Exception as e:
            return {"report_tool": f"Error reporting lost item: {str(e)}"}
    else:
        return {"report_tool": "Please provide all the details about the item."}

tools = [fetch_items, fetch_reported_by_user, fetch_items_nearby, fetch_similar_items, make_report]
tool_node = ToolNode(tools)

def get_assistant_model():
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    primary_llm = ChatGroq(
        model_name="qwen/qwen3.6-27b",
        temperature=0.0,
        max_retries=3,
        groq_api_key=groq_api_key
    )
    
    fallback_llms = [
        ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.0, max_retries=2, groq_api_key=groq_api_key),
        ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.0, max_retries=2, groq_api_key=groq_api_key),
        ChatGroq(model_name="openai/gpt-oss-20b", temperature=0.0, max_retries=2, groq_api_key=groq_api_key)
    ]
    
    primary_with_tools = primary_llm.bind_tools(tools)
    fallbacks_with_tools = [m.bind_tools(tools) for m in fallback_llms]
    
    return primary_with_tools.with_fallbacks(fallbacks_with_tools)

model = get_assistant_model()

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
app = app.compile(checkpointer=MemorySaver())


# if __name__ == "__main__":
#     while True:
#         thread_id = "23"
#         user_input = input("User: ")
#         if user_input.lower() == "exit":
#             break
#         response = app.invoke({"messages": [HumanMessage(content=user_input)]}, config={"configurable": {"thread_id": thread_id}})
#         print("Assistant: ", response["messages"][-1].content)
#         print("="*81)
#         print(response["messages"])