"""
PageIndex + MongoDB Chatbot - Streamlit Frontend
Compatible with Streamlit 1.12.0 (Python 3.9)
"""
import asyncio

# Agno needs an asyncio event loop in the current thread.
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import streamlit as st
import os
from chatbot import get_agent
from database import DatabaseManager
from logger import logger

# -- Page Config --
st.set_page_config(page_title="PageIndex Chatbot", page_icon="📚")
st.title("PageIndex + MongoDB Chatbot")
st.caption("Agno Agent - Gemini - MongoDB Full-Text Search")

# -- Database Connection --
@st.experimental_singleton
def get_db():
    try:
        return DatabaseManager()
    except Exception:
        return None

db = get_db()

if not db:
    logger.error("Failed to connect to MongoDB.")
    st.error("Failed to connect to MongoDB. Is your Docker container running?")
    st.stop()

# -- Fetch available documents --
try:
    docs = db.get_all_nodes()
    doc_map = {}
    id_to_filename_map = {}
    classes_available = set()
    
    for doc in docs:
        fname = doc.get("filename")
        pid = doc.get("pageindex_doc_id")
        doc_class = doc.get("class", "Unknown")
        
        if fname and pid:
            doc_map[fname] = {"pid": pid, "class": doc_class}
            id_to_filename_map[pid] = fname
            classes_available.add(doc_class)
            
    classes_available = sorted(list(classes_available))
    logger.info(f"Fetched {len(doc_map)} documents from DB across {len(classes_available)} classes.")
except Exception as e:
    doc_map = {}
    classes_available = []
    logger.error(f"Error fetching documents: {e}")
    st.error(f"Error fetching documents: {e}")

if not doc_map:
    st.info("No documents found. Run `python src/ingest_document.py <pdf_path> --class_name <class>` first.")
    st.stop()

# -- Sidebar --
search_mode = st.sidebar.radio("Search Mode:", ["All Documents", "Specific Documents"])

if search_mode == "All Documents":
    selected_docs = "ALL"
    doc_names_str = "All Documents"
else:
    # Hierarchical filter: Class -> Document
    selected_classes = st.sidebar.multiselect("Select Class:", classes_available, default=classes_available)
    
    # Filter documents based on selected classes
    filtered_doc_options = [fname for fname, info in doc_map.items() if info["class"] in selected_classes]
    
    selected_docs_list = st.sidebar.multiselect("Select Documents:", filtered_doc_options, default=filtered_doc_options[:1] if filtered_doc_options else [])
    
    if not selected_docs_list:
        st.warning("Please select at least one document.")
        st.stop()
        
    selected_docs = [doc_map[d]["pid"] for d in selected_docs_list]
    doc_names_str = ", ".join(selected_docs_list)

st.sidebar.markdown("---")

if st.sidebar.button("Clear Chat"):
    logger.info("User cleared chat history.")
    st.session_state["messages"] = []
    st.session_state["agent"] = None
    st.experimental_rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**How the Engine Works:**")
st.sidebar.markdown(
    "1. **Extraction**: Documents are processed via **PageIndex API**, which visually extracts hierarchical trees (Class > Chapter > Topic > Subtopic) instead of blind text chunks.\n"
    "2. **Vectorization**: Chunks are embedded using **Jina v2 Small** and stored in **Qdrant** for semantic hybrid search.\n"
    "3. **Token Optimization**: When you ask to generate a quiz, the LLM uses high-speed **MongoDB** queries to discover Topics and Subtopics *before* reading text.\n"
    "4. **Smart Retrieval**: The Agent fetches exactly one subtopic at a time, ensuring it never hits Groq's 8,000 token limit."
)

# -- Session State --
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "current_doc" not in st.session_state:
    st.session_state["current_doc"] = None
if "agent" not in st.session_state:
    st.session_state["agent"] = None

# Re-create agent if document selection changed
if st.session_state["current_doc"] != doc_names_str:
    st.session_state["messages"] = []
    st.session_state["current_doc"] = doc_names_str
    st.session_state["agent"] = None

if st.session_state["agent"] is None:
    try:
        logger.info(f"Initializing agent for context: {doc_names_str}")
        st.session_state["agent"] = get_agent(selected_docs, doc_names_str, id_to_filename_map, db_manager=db)
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        st.error(f"Failed to initialize agent: {e}")

# -- Display chat history --
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**Assistant:** {msg['content']}")
        if msg.get("tool_info"):
            with st.expander("Tool Calls", expanded=False):
                st.markdown(msg["tool_info"])
    st.markdown("---")

# -- User Input via st.form (prevents rerun loop!) --
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask a question about the document:")
    submitted = st.form_submit_button("Ask")

if submitted and user_input and st.session_state["agent"] is not None:
    logger.info(f"User asked: '{user_input}'")
    # Save user message
    st.session_state["messages"].append({"role": "user", "content": user_input})

    # Render the question immediately so it doesn't vanish while loading
    st.markdown(f"**You:** {user_input}")
    st.markdown("---")

    with st.spinner("Agent is planning its workflow..."):
        try:
            agent = st.session_state["agent"]
            logger.info("Sending query to agent...")
            
            # Create a placeholder for streaming response
            stream_placeholder = st.empty()
            full_response = ""
            
            # Stream the response chunks in real-time
            for chunk in agent.run(user_input, stream=True):
                if chunk.content:
                    full_response += chunk.content
                    stream_placeholder.markdown(full_response + "▌")
            
            # Finalize the display by removing the cursor
            stream_placeholder.markdown(full_response)
            logger.info("Received full stream from agent.")
            # In streaming mode, extracting exact tool returns from the generator is complex in Agno 0.x,
            # but we injected st.info() into the tools directly in chatbot.py for real-time visibility!
            tool_info = None
            answer = full_response
            
            # Fallback if the LLM returned nothing
            if not answer or not str(answer).strip():
                answer = "No response generated."

            st.session_state["messages"].append({
                "role": "assistant",
                "content": answer,
                "tool_info": tool_info,
            })

            # Rerun to display the new messages (safe because form clears the input)
            st.experimental_rerun()

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Error during agent execution: {err_msg}")
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                st.warning("Rate limit hit! Free tier = 5 requests/min. Please wait 1 minute and try again.")
            else:
                st.error(f"Error: {err_msg}")

elif submitted and user_input and st.session_state["agent"] is None:
    st.error("Agent not initialized. Please select a valid document.")
