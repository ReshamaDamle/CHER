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
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of dicts: {"role": "user"/"assistant", "text": str, "image_bytes": bytes|None}

if "file_index" not in st.session_state:
    # name -> {"file_id": str, "filename": str}
    st.session_state.file_index = {}

if "query_map" not in st.session_state:
    # structure: {"rules": [{"match":"cat photo","file":"cat.png"}]} or {"rules":[{"match":"diagram","file_id":"file_..."}]}
    st.session_state.query_map = {"rules": []}

# ----------------------------
# Helpers
# ----------------------------
def upload_image_to_openai(file_name: str, file_bytes: bytes) -> str:
    """Upload an image to OpenAI Files with purpose='assistants' and return file_id."""
    up = client.files.create(file=(file_name, io.BytesIO(file_bytes)), purpose="assistants")
    return up.id

def download_openai_file_bytes(file_id: str) -> bytes:
    """Download bytes for a stored OpenAI file_id."""
    content = client.files.content(file_id)
    return content.read()

def best_match_file_id(user_text: str) -> str | None:
    """
    Match user_text to a rule in st.session_state.query_map.
    Rule can specify either 'file_id' directly or a 'file' (name) resolved via st.session_state.file_index.
    Matching strategy: first rule whose 'match' substring appears (case-insensitive) in the user_text.
    """
    text = (user_text or "").lower()
    for rule in st.session_state.query_map.get("rules", []):
        match = (rule.get("match") or "").lower()
        if match and match in text:
            if "file_id" in rule and rule["file_id"]:
                return rule["file_id"]
            if "file" in rule and rule["file"]:
                name = rule["file"]
                entry = st.session_state.file_index.get(name)
                if entry:
                    return entry["file_id"]
    return None

def run_assistant(thread_id: str, prompt: str):
    """Send a message to the thread and run the assistant until completion. Return last assistant text (if any)."""
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=[{"type": "input_text", "text": prompt}],
    )
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)

    # Poll until done
    while True:
        r = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        if r.status in ("completed", "failed", "cancelled", "expired"):
            break
        time.sleep(0.7)

    # Collect assistant text (latest)
    msgs = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=10)
    for m in msgs.data:
        if m.role == "assistant":
            # Concatenate any text parts
            texts = []
            for p in m.content:
                if p.type == "output_text":  # newer SDKs use output_text
                    texts.append(p.text)
                elif p.type == "text":      # fallback
                    texts.append(p.text.get("value") if isinstance(p.text, dict) else str(p.text))
            if texts:
                return "\n".join(texts)
    return ""

# ----------------------------
# Sidebar: Uploads & Mapping
# ----------------------------
st.sidebar.header("📤 Uploads & Mapping")

img_files = st.sidebar.file_uploader("Upload images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
if img_files:
    for f in img_files:
        data = f.read()
        file_id = upload_image_to_openai(f.name, data)
        st.session_state.file_index[f.name] = {"file_id": file_id, "filename": f.name}
    st.sidebar.success("Uploaded to OpenAI storage.")
    st.sidebar.json({k: v["file_id"] for k, v in st.session_state.file_index.items()})

mapping_file = st.sidebar.file_uploader("Upload JSON mapping", type=["json"])
if mapping_file:
    try:
        mapping = json.loads(mapping_file.read().decode("utf-8"))
        if isinstance(mapping, dict) and "rules" in mapping and isinstance(mapping["rules"], list):
            st.session_state.query_map = mapping
            st.sidebar.success("Mapping loaded.")
        else:
            st.sidebar.error("JSON must be like: {\"rules\": [{\"match\": \"sunset\", \"file\": \"beach.png\"}]}")
    except Exception as e:
        st.sidebar.error(f"Invalid JSON: {e}")

st.sidebar.markdown("**Mapping examples:**")
st.sidebar.code(
    '''{
  "rules": [
    {"match": "cat", "file": "cat.png"},
    {"match": "flow chart", "file_id": "file_abc123"}
  ]
}''',
    language="json",
)

# ----------------------------
# Thread management
# ----------------------------
if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

# ----------------------------
# Chat UI
# ----------------------------
with st.container(border=True):
    for m in st.session_state.messages:
        if m["role"] == "user":
            with st.chat_message("user"):
                st.write(m["text"])
        else:
            with st.chat_message("assistant"):
                st.write(m["text"])
                if m.get("image_bytes"):
                    st.image(m["image_bytes"], caption="Assistant image")

user_input = st.chat_input("Ask your question (e.g., 'show me the cat photo')")
if user_input:
    # 1) Show user message
    st.session_state.messages.append({"role": "user", "text": user_input})

    # 2) Run the assistant for text response
    assistant_text = run_assistant(st.session_state.thread_id, user_input) or "(no text reply)"

    # 3) Resolve image via mapping
    file_id = best_match_file_id(user_input)
    image_bytes = None
    if file_id:
        try:
            image_bytes = download_openai_file_bytes(file_id)
        except Exception as e:
            assistant_text += f"\n\n(Note: Failed to fetch image {file_id}: {e})"

    # 4) Show assistant message + image
    st.session_state.messages.append(
        {"role": "assistant", "text": assistant_text, "image_bytes": image_bytes}
    )
    st.rerun()
