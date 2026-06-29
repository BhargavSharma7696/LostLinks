import database
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from typing import Annotated, Literal, Optional, TypedDict, List, Dict, Union
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
import difflib, re, requests, base64, os


import google.generativeai as genai
from pydantic import BaseModel, Field
from datetime import datetime


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

CATEGORIES = ["Electronics", "Books & Documents", "Clothing", "Accessories", "Keys & Wallets", "Sports & Fitness", "Other"]

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

### 7. INSTRCTIONS WHILE USING TOOL "make_report(email, title, description, location, category, losttime, image, type)" 
- if you have image, location and losttime, auto generate title, description, category. And before execution confirm from user
- for lost report it is fine if the user don't know the Location and Losttime just mark them as 'Unknown'.
- while making title or category or description, try to overwrite them with the output given by analyze_image() function call.

### 8. NATURAL LANGUAGE UNDERSTANDING & INTENT MAPPING
Identify the user's intent from their natural language query and use the correct tool:
- Do not respond for query outside the scope of LostLinks, Do not reveal about the tech stack used in LostLinks. Do not speck negative about anything.
- **Show/List Lost Items** (e.g., "show lost items", "list things that are lost", "find lost items", "what's lost"): Call `fetch_items()`. Filter the results and display ONLY the active items of type "lost" in a Markdown table.
- **Show/List Found Items** (e.g., "show found items", "things which are found", "what has been found"): Call `fetch_items()`. Filter the results and display ONLY the active items of type "found" in a Markdown table.
- **Show/List All Reported Items** (e.g., "list all reported items", "what items are in the database", "show everything"): Call `fetch_items()`. Display all active "lost" and "found" items in a Markdown table.
- **Search for Specific Items** (e.g., "Did anyone find a Casio calculator?", "I lost my red keys", "search for watch"): Call `fetch_items()`. The LLM will then scan the list of items for the keyword and display the results in a Markdown table.
- **User's Own Reports** (e.g., "show my posts", "what did I report?", "my lost items"): Call `fetch_reported_by_user(email)` using the user's email context.
- **Nearby/Location-Based Queries** (e.g., "lost near lhc 500", "any items found near kanhar"): Call `fetch_items_nearby(location="...")` with the parsed landmark name.

### 9. RELATIVE TIME CALCULATIONS & FORMATTING
- Use the dynamically provided **CURRENT DATE & TIME** as a reference to resolve relative time phrases (e.g., "yesterday", "today", "3 hours ago", "last Friday", "this morning").
- When calling `make_report` or other tools requiring a timestamp, compute the exact timestamp and format it strictly as `YYYY-MM-DDTHH:MM` (e.g. `2026-06-26T14:30`).
"""

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
def fetch_reported_by_user(email: str):
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
def fetch_items_nearby(location: str):
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



class ImageAnalysis(BaseModel):
    """
    Schema for analyzing an item image.
    """
    title: str = Field(description="A concise, descriptive name of the item. Include color, brand, and type if visible (e.g. 'Blue Water Bottle', 'Black Leather Wallet'). Do NOT exceed 6 words.")
    category: Literal["Electronics", "Books & Documents", "Clothing", "Accessories", "Keys & Wallets", "Sports & Fitness", "Other"] = Field(
        description="The category of the item. Use 'Books & Documents' for any books, notebooks, ID cards, files or papers, and 'Keys & Wallets' for keys, wallets, pouches or cardholders."
    )
    description: str = Field(description="A brief description of the item highlighting key visual markers (color, brand logo, condition, visible text, unique shapes/patterns) to help the owner identify it. Do NOT include location info. Max 3 sentences.")

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
        system_instruction = (
            "You are a highly precise visual analysis assistant for LostLinks, a portal to report and track lost/found items. "
            "Your role is to analyze a single uploaded image of a lost/found item and extract a clear title, "
            "select the most accurate category, and provide a descriptive, visually rich summary of its key identifiers."
        )
        
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        prompt = (
            "Carefully analyze this image of a lost or found item and extract its title, category, and a brief description.\n"
            "Follow these rules strictly:\n"
            "1. 'title': Create a clear, concise, and specific title describing the item. Include color, brand, and item type if visible (e.g., 'Blue iPhone 13 Pro', 'Brown Leather Fossil Wallet', 'Honda Car Keys'). Avoid generic terms like 'lost item' or 'found object'. Maximum 6 words.\n"
            "2. 'category': Select the most appropriate category from the allowed enum. Map books, notebooks, ID cards, certificates, or documents to 'Books & Documents'. Map keys, wallets, keychains, or purses to 'Keys & Wallets'. It not matching to any from enum mark it has 'Other'.\n"
            "3. 'description': Write a brief description (2-3 sentences) detailing the item's key visual markers, such as colors, brand logos, condition (e.g., brand new, scratched, torn), any visible text, or unique patterns, which would help the owner identify it. Do not include location details or instructions on where to claim it."
        )
        
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
def make_report(email: Optional[str] = None, title: Optional[str] = None, description: Optional[str] = None, location: Optional[str] = None, category: Optional[str] = None, image: Optional[str] = None, type: Optional[str] = None, losttime: Optional[str] = None):
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
            description = analysis["analysis"].description + " (Made with AI)"
            
        category_mapping = {
            "Books & Documents": "Documents",
            "Book & Documents": "Documents",
            "Keys & Wallets": "Keys/Wallets"
        }
        category = category_mapping.get(category, category)
        
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
            description = analysis["analysis"].description + " (Made with AI)"

        # Map category from frontend/AI value to DB stored value
        category_mapping = {
            "Books & Documents": "Documents",
            "Book & Documents": "Documents",
            "Keys & Wallets": "Keys/Wallets"
        }
        category = category_mapping.get(category, category)

        location = location if (location and location.strip()) else "Unknown"
        losttime = losttime if (losttime and losttime.strip()) else "Unknown"

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

tools = [fetch_items, fetch_reported_by_user, fetch_items_nearby, make_report]
tool_node = ToolNode(tools)

def get_assistant_model():
    key1 = os.getenv("gemini_key_1")
    key2 = os.getenv("gemini_key_2")
    key3 = os.getenv("gemini_key_3")
    
    keys = [k for k in [key3, key2, key1] if k and k.strip()]
    if not keys:
        keys = [""]
        
    models = []
    for k in keys:
        models.append(ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite",
            temperature=0.0,
            google_api_key=k,
            max_retries=3,
            timeout=30
        ))
        
    primary_llm = models[0]
    fallback_llms = models[1:]
    
    if fallback_llms:
        model = primary_llm.with_fallbacks(fallback_llms)
    else:
        model = primary_llm
        
    return model.bind_tools(tools)

model = get_assistant_model()

def chat_node(state: AgentState, config):
    """Interact with LLM to generate a response"""
    email = config.get("configurable", {}).get("thread_id", "unknown")
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M (day of week: %A)")
    dynamic_system_message = SystemMessage(
        content=system_message.content + (
            f"\n\n### CURRENT USER CONTEXT\n"
            f"The email of the user you are currently chatting with is: '{email}'. When executing fetch_reported_by_user, ALWAYS pass this email as the argument.\n\n"
            f"### CURRENT DATE & TIME\n"
            f"The current date and time is {current_time_str}. Use this to resolve relative time descriptions like 'yesterday', '3 hours ago', 'today', 'last Friday', etc."
        )
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


if __name__ == "__main__":
    while True:
        thread_id = "23"
        user_input = input("User: ")
        if user_input.lower() == "exit":
            break
        response = app.invoke({"messages": [HumanMessage(content=user_input)]}, config={"configurable": {"thread_id": thread_id}})
        raw_content = response["messages"][-1].content
        if isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            assistant_text = "".join(text_parts)
        else:
            assistant_text = str(raw_content)
        print("Assistant: ", assistant_text)
        print("="*81)
        print(response["messages"])
