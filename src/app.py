import streamlit as st
import os
from chatbot import chat_with_document
from database import DatabaseManager

st.set_page_config(page_title="PageIndex Chatbot", page_icon="🤖")

st.title("📄 PageIndex + MongoDB Chatbot")
st.markdown("This chatbot uses vectorless reasoning to answer questions based on the document stored in your local MongoDB instance.")

# Initialize the Database Manager to fetch available documents
@st.experimental_singleton
def get_db():
    try:
        return DatabaseManager()
    except Exception as e:
        return None

db = get_db()

if not db:
    st.error("Failed to connect to MongoDB. Is your Docker container running?")
    st.stop()

try:
    docs = db.get_all_nodes()
    doc_options = [doc['filename'] for doc in docs if 'filename' in doc]
except Exception as e:
    doc_options = []
    st.error(f"Error fetching documents: {e}")

if not doc_options:
    st.info("No documents found in MongoDB. Please run `ingest_document.py` first.")
    st.stop()

selected_doc = st.sidebar.selectbox("Select a Document to Chat With:", doc_options)

st.sidebar.markdown("---")
st.sidebar.markdown("**Chat History** is maintained across questions!")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_doc" not in st.session_state:
    st.session_state.current_doc = selected_doc

if st.session_state.current_doc != selected_doc:
    st.session_state.messages = []
    st.session_state.current_doc = selected_doc

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    if message["role"] == "user":
        st.info(f"👤 **You:** {message['content']}")
    else:
        st.success(f"🤖 **Assistant:** {message['content']}")

# Accept user input
prompt = st.text_input("Ask a question about the document...")
if st.button("Send") and prompt:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    st.info(f"👤 **You:** {prompt}")

    with st.spinner("Reasoning over document tree..."):
        # Call our modified chatbot logic
        response = chat_with_document(st.session_state.messages, selected_doc)
        st.success(f"🤖 **Assistant:** {response}")
            
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
