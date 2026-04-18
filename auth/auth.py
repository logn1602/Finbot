import os
import streamlit as st
from supabase import create_client, Client

DEFAULT_BUDGETS = {
    "food": 500, "transport": 200, "entertainment": 150,
    "shopping": 300, "bills": 400, "health": 200,
    "education": 100, "other": 150
}

def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
    return create_client(url, key)

def signup(email: str, password: str):
    try:
        sb = get_supabase()
        res = sb.auth.sign_up({"email": email, "password": password})
        if res.user:
            return res.user, None
        return None, "Signup failed. Try again."
    except Exception as e:
        return None, str(e)

def login(email: str, password: str):
    try:
        sb = get_supabase()
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        if res.session:
            return res.session, None
        return None, "Invalid email or password."
    except Exception as e:
        return None, "Invalid email or password."

def logout():
    try:
        get_supabase().auth.sign_out()
    except:
        pass
    for key in ["user", "user_id", "access_token", "conversation_history"]:
        st.session_state.pop(key, None)

def seed_default_budgets(user_id: str, access_token: str):
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
    sb = create_client(url, key)
    sb.postgrest.auth(access_token)
    existing = sb.table("budgets").select("category").eq("user_id", user_id).execute()
    existing_cats = {r["category"] for r in existing.data}
    rows = [
        {"user_id": user_id, "category": cat, "monthly_limit": limit}
        for cat, limit in DEFAULT_BUDGETS.items()
        if cat not in existing_cats
    ]
    if rows:
        sb.table("budgets").insert(rows).execute()

def get_authenticated_client(access_token: str) -> Client:
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
    sb = create_client(url, key)
    sb.postgrest.auth(access_token)
    return sb