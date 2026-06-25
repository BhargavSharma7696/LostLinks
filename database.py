import os
import secrets
from datetime import datetime
from dotenv import load_dotenv
from fastembed import TextEmbedding
from supabase import create_client, Client

load_dotenv()

# Initialize fastembed locally (uses ONNX Runtime CPU, zero PyTorch/CUDA dependencies, extremely fast and lightweight)
embedding_model_local = TextEmbedding()

class ONNXEmbeddingModel:
    def encode(self, text):
        try:
            embeddings = list(embedding_model_local.embed([text]))
            return embeddings[0].tolist()
        except Exception as e:
            raise Exception(f"Error running ONNX model locally: {str(e)}")

# Compatible wrapper exposed for Assistant.py
embedding_model = ONNXEmbeddingModel()

def get_embeddings(item):
    fields = [
        item.get('title'),
        item.get('description'),
        item.get('location'),
        item.get('category'),
    ]
    text = " ".join([str(f).strip() for f in fields if f is not None])
    
    try:
        return embedding_model.encode(text)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return None

try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if supabase_url and supabase_key:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized successfully in database.py")
    else:
        supabase = None
        print("Supabase credentials not found. Please contact the ADMIN of the page.")
except ImportError:
    supabase = None
    print("supabase library not found. Please contact the ADMIN of the page.")

def init_db():
    if supabase is None:
        raise Exception("Supabase client not initialized. Please contact the ADMIN of the page.")
    print("Using Supabase database (tables managed on Supabase).")

#USER DB
def create_user(firebase_uid, email, display_name, contact_number=None, verified_email=False):
    user_uuid = f"usr_{firebase_uid}"
    now = datetime.now().strftime("%b-%d-%Y %H:%M:%S")

    try:
        user_data = {
            "id": user_uuid,
            "displayName": display_name,
            "email": email,
            "membersSince": now,
            "contactNumber": contact_number if contact_number else None,
            "verified": verified_email
        }
        response = supabase.table("User").insert(user_data).execute()
        print(f"Successfully created user in Supabase: {display_name} ({email})")
        return user_uuid
    except Exception as e:
        print(f"Error creating user in Supabase: {e}")
        raise e

def get_user(email):
    response = supabase.table("User").select("*").eq("email", email).execute()
    if not response.data:
        return None
    return response.data[0]

def update_user(email, display_name=None, contact_number=None):
    user_data = {
        "displayName": display_name,
        "contactNumber": contact_number
    }
    response = supabase.table("User").update(user_data).eq("email", email).execute()
    print(f"Successfully updated user in Supabase: {email}")

def update_user_verification(email, verified=True):
    response = supabase.table("User").update({"verified": verified}).eq("email", email).execute()
    print(f"Successfully updated verification status for {email} to {verified}")
    return response.data


#ENTRY DB      
columnsItem = ["id","title","category", "description", "type", "location", "status", "reporterid", "createdat", "updatedat", "photourl", "losttime", "claimsmade", "resolvedto"]

def create_lost_entry(item_data):
    embedding = get_embeddings(item_data)
    item_data["id"] = f"itm_{secrets.token_urlsafe(8)}"
    if embedding:
        item_data["embeddings"] = str(embedding)
    response = supabase.table("Item").insert(item_data).execute()
    print(f"Successfully created lost item in Supabase: {item_data['title']}")

def update_item_entry(item_id, email, title, category, location, description, losttime, photourl=None):
    update_data = {
        "title": title,
        "category": category,
        "location": location,
        "description": description,
        "losttime": losttime,
        "updatedat" : datetime.now().strftime("%b-%d-%Y %H:%M:%S")
    }
    if photourl:
        update_data["photourl"] = photourl
    embedding = get_embeddings(update_data)
    if embedding:
        update_data["embeddings"] = str(embedding)
    response = supabase.table("Item").update(update_data).eq("id", item_id).eq("reporterid", email).execute()
    print(f"Successfully updated item {item_id} in Supabase: {title}")
    return response.data

def create_found_entry(item_data):
    item_data["id"] = f"itm_{secrets.token_urlsafe(8)}"
    embedding = get_embeddings(item_data)
    if embedding:
        item_data["embeddings"] = str(embedding)
    else :
        item_data["embeddings"] = None
    response = supabase.table("Item").insert(item_data).execute()
    print(f"Successfully created found item in Supabase: {item_data['title']}")

def get_lost_entries():
    response = supabase.table("Item").select(",".join(columnsItem)).eq("type", "lost").execute()
    return response.data

def get_lost_entries_by_user(email):
    response = supabase.table("Item").select(",".join(columnsItem)).eq("type", "lost").eq("reporterid", email).execute()
    return response.data

def get_found_entries():
    response = supabase.table("Item").select(",".join(columnsItem)).eq("type", "found").execute()
    return response.data

def get_found_entries_by_user(email):
    response = supabase.table("Item").select(",".join(columnsItem)).eq("type", "found").eq("reporterid", email).execute()
    return response.data

def resolve_entry(item_id, email):
    response = supabase.table("Item").update({"status": "resolved"}).eq("id", item_id).eq("reporterid", email).execute()
    return response.data
 
def delete_entry(item_id, email):
    response = supabase.table("Item").delete().eq("id", item_id).eq("reporterid", email).execute()
    return response.data

def get_item_by_id(item_id):
    response = supabase.table("Item").select(",".join(columnsItem)).eq("id", item_id).execute()
    if response.data:
        return response.data[0]
    return None

def get_reporter_id(item_id):
    response = supabase.table("Item").select("reporterid").eq("id", item_id).execute()
    if response.data:
        return response.data[0].get("reporterid")
    return None
    
#CHAT DB
def load_chat(id):
    response = supabase.table("chat").select("*").eq("itemid", id).order("time", desc=False).execute()
    return response.data

def save_chat(msg_data):
    chat_data = {
        "id": f"msg_{secrets.token_urlsafe(8)}",
        "itemid": msg_data["itemid"],
        "sender": msg_data["sender"],
        "receiver": msg_data.get("receiver", "public"),
        "message": msg_data["message"],
    }
    response = supabase.table("chat").insert(chat_data).execute()
    print(f"Successfully saved chat in Supabase: {chat_data['message']}")

# ASSISTANT DB
def get_entries():
    response = supabase.table("Item").select(",".join(columnsItem)).execute()
    return response.data

def get_entries_by_user(email):
    response = supabase.table("Item").select(",".join(columnsItem)).eq("reporterid", email).execute()
    return response.data

def get_entries_with_embeddings():
    response = supabase.table("Item").select("*").execute()
    return response.data

def save_assistant_query(user_email, sender, message):
    query_data = {
        "id": f"assist_{secrets.token_urlsafe(8)}",
        "email": user_email,
        "sender": sender,
        "message": message,
    }
    response = supabase.table("AssistantChat").insert(query_data).execute()
    print(f"Successfully saved assistant chat with id in Supabase: {query_data['id']}")
    return response.data

def get_assistant_history(user_email):
    response = supabase.table("AssistantChat").select("*").eq("email", user_email).execute()
    return response.data

#CLAIMS_MADE AND RESOLVED_TO
def make_claim(email, item_id):
    response = supabase.table("Item").select("claimsmade").eq("id", item_id).execute()
    if not response.data:
        raise Exception("Item not found")
    current_claims = response.data[0].get("claimsmade")
    if current_claims is None:
        current_claims = []
    elif isinstance(current_claims, str):
        current_claims = [current_claims]
    elif not isinstance(current_claims, list):
        current_claims = list(current_claims)
    
    if email not in current_claims:
        current_claims.append(email)
        
    update_response = supabase.table("Item").update({"claimsmade": current_claims}).eq("id", item_id).execute()
    print(f"Successfully added claim for {email} to item {item_id}")
    return update_response.data

def resolve_claim(email, item_id, resolved_to_id):
    response = supabase.table("Item").update({"resolvedto": resolved_to_id, "status": "resolved"}).eq("id", item_id).eq("reporterid", email).execute()
    print(f"Successfully resolved claim for {email} to item {item_id}")
    return response.data
