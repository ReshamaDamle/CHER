import io
import json
import time
import streamlit as st
from openai import OpenAI

# ----------------------------
# Streamlit Setup
# ----------------------------
st.set_page_config(page_title="Assistant: Ask & Return Image", page_icon="🖼️", layout="centered")
st.title("🖼️ Chat with Assistant & Retrieve Images")

# Secrets
api_key = st.secrets["OPENAI_API_KEY"]
assistant_id = st.secrets["ASSISTANT_ID"]

# OpenAI client
client = OpenAI(api_key=api_key)

# Session state
if "messages" not in st.
