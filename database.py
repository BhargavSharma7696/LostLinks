import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client, Client
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
    user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, firebase_uid))
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
def create_lost_entry(item_data):
    item_data["id"] = str(uuid.uuid4())
    response = supabase.table("Item").insert(item_data).execute()
    print(f"Successfully created lost item in Supabase: {item_data['title']}")

def update_item_entry(item_id, email, title, category, location, description, losttime):
    update_data = {
        "title": title,
        "category": category,
        "location": location,
        "description": description,
        "losttime": losttime,
        "updatedat" : datetime.now().strftime("%b-%d-%Y %H:%M:%S")
    }
    response = supabase.table("Item").update(update_data).eq("id", item_id).eq("reporterid", email).execute()
    print(f"Successfully updated item {item_id} in Supabase: {title}")
    return response.data

def create_found_entry(item_data):
    item_data["id"] = str(uuid.uuid4())
    response = supabase.table("Item").insert(item_data).execute()
    print(f"Successfully created found item in Supabase: {item_data['title']}")

def get_lost_entries():
    response = supabase.table("Item").select("*").eq("type", "lost").execute()
    return response.data

def get_lost_entries_by_user(email):
    response = supabase.table("Item").select("*").eq("type", "lost").eq("reporterid", email).execute()
    return response.data

def get_found_entries():
    response = supabase.table("Item").select("*").eq("type", "found").execute()
    return response.data

def get_found_entries_by_user(email):
    response = supabase.table("Item").select("*").eq("type", "found").eq("reporterid", email).execute()
    return response.data

def resolve_entry(item_id, email):
    response = supabase.table("Item").update({"status": "resolved"}).eq("id", item_id).eq("reporterid", email).execute()
    return response.data
 
def delete_entry(item_id, email):
    response = supabase.table("Item").delete().eq("id", item_id).eq("reporterid", email).execute()
    return response.data

def get_item_by_id(item_id):
    response = supabase.table("Item").select("*").eq("id", item_id).execute()
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
        "id": str(uuid.uuid4()),
        "itemid": msg_data["itemid"],
        "sender": msg_data["sender"],
        "receiver": msg_data.get("receiver", "public"),
        "message": msg_data["message"],
    }
    response = supabase.table("chat").insert(chat_data).execute()
    print(f"Successfully saved chat in Supabase: {chat_data['message']}")

    