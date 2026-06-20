import pyrebase
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

load_dotenv()

super_secret = os.getenv("SECRET_KEY", os.urandom(24))

sec = os.getenv("admin_email")

class loginInput(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")

    @field_validator('email')
    @classmethod
    def email_validator(cls, v):
        if '@iitbhilai.ac.in' not in v and v not in sec:
            raise ValueError("Email must be an IITBhilai associated email")
        return v

    @field_validator('password')
    @classmethod
    def password_validator(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

class signupInput(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    confirm_password: str = Field(..., description="Confirm password")

    @field_validator('email')
    @classmethod
    def email_validator(cls, v):
        if '@iitbhilai.ac.in' not in v:
            raise ValueError("Email must be an IITBhilai associated email")
        return v

    @field_validator('password')
    @classmethod
    def password_validator(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one alphabet")
        return v

    @model_validator(mode='after')
    def verify_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

class forgetPasswordInput(BaseModel):
    email: str = Field(..., description="Email address")

    @field_validator('email')
    @classmethod
    def email_validator(cls, v):
        if '@iitbhilai.ac.in' not in v:
            raise ValueError("Email must be an IITBhilai associated email")
        return v

def get_env_clean(key):
    val = os.getenv(key)
    if val:
        # Strip whitespaces, commas, and quotes
        return val.strip().strip("'\"").strip(",")
    return val

firebaseConfig = {
    "apiKey": get_env_clean("apiKey"),
    "authDomain": get_env_clean("authDomain"),
    "projectId": get_env_clean("projectId"),
    "storageBucket": get_env_clean("storageBucket"),
    "messagingSenderId": get_env_clean("messagingSenderId"),
    "appId": get_env_clean("appId"),
    "measurementId": get_env_clean("measurementId"),
    "databaseURL": get_env_clean("databaseURL")
}

firebase_app = pyrebase.initialize_app(firebaseConfig)
auth = firebase_app.auth()

def display_error(e):
    try:
        error_json = json.loads(e.args[1])
        error_message = error_json['error']['message']
    except Exception:
        error_message = str(e)
    return {"success": False, "error": error_message}

def signup(email, pwd):
    try:
        user = auth.create_user_with_email_and_password(email, pwd)
        return {"success": True, "user": user}
    except Exception as e:
        return display_error(e)

def login(email, pwd):
    try:
        user = auth.sign_in_with_email_and_password(email, pwd)
        return {"success": True, "user": user}
    except Exception as e:
        return display_error(e)

def forget_password(email):
    try:
        auth.send_password_reset_email(email)
        return {"success": True}
    except Exception as e:
        return display_error(e)

def logout():
    try:
        auth.current_user = None
    except Exception:
        pass
    return {"success": True}

def send_verification_email(id_token):
    try:
        auth.send_email_verification(id_token)
        return {"success": True}
    except Exception as e:
        return display_error(e)

def is_email_verified(id_token):
    try:
        info = auth.get_account_info(id_token)
        users = info.get("users", [])
        if users:
            return {"success": True, "verified": users[0].get("emailVerified", False)}
        return {"success": False, "error": "User profile not found."}
    except Exception as e:
        return display_error(e)

def delete_account(id_token):
    try:
        auth.delete_user_account(id_token)
        return {"success": True}
    except Exception as e:
        return display_error(e)


 
