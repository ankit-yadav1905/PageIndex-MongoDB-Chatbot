# 📚 PageIndex + MongoDB + Agno Agent Chatbot

## What is this project?

This is an **NCERT Book Chatbot** that uses the **Agno Agent Framework** with **Gemini LLM** and **MongoDB Full-Text Search**.

The basic idea is that you upload a PDF book, its content is broken down into **sub-topic-level chunks** and stored in MongoDB, and then an AI agent answers user questions by actually searching those chunks through **tool calling**.

---

# 🔄 Old Code vs New Code — What Changed?

## Previous Architecture

Previously:

* Direct Gemini/OpenAI API calls were made — there was no agent framework.
* `sync.py` was a separate utility script that had to be run manually to download the text nodes.
* MongoDB was used only for storing metadata such as filename, document ID, and date.
* The UI did not show any tool calls — it only displayed a spinner while the answer was being generated.

## New Architecture

Now:

* **Agno Agent Framework** has been integrated — there is a proper `Agent` with `tools` and `instructions`.
* **Sub-topic chunks are automatically ingested** — as soon as a PDF is uploaded, the PageIndex tree is fetched and stored in MongoDB.
* **MongoDB Full-Text Search** is used — a `$text` index is created on the `text` and `content` fields for fast search.
* **Tool Calling** is implemented — the agent has a `search_book_content` tool that searches MongoDB.
* **Tool Calls are visible in the frontend** — the UI displays the tool name, arguments, and results inside an expandable section.

---

# 📁 Project Structure — What Each File Does

```text
src/
├── database.py          # MongoDB connection + text search
├── ingest_document.py   # PDF upload + sub-topic chunking
├── chatbot.py           # Agno Agent + Gemini + Tool setup
└── app.py               # Streamlit Frontend UI
```

---

# 1. `database.py` — Database Layer

### What was changed?

* Added a new collection: `extracted_nodes` — this stores the sub-topic chunks.
* Created a MongoDB `$text` index on the `text` and `content` fields.
* The index is named `subtopic_text_index`.
* Added a `search_nodes()` method that performs full-text search with `textScore` sorting.

### How it works

```text
User question
      ↓
MongoDB $text search
      ↓
Top 5 relevant chunks
```

MongoDB searches the indexed content and ranks the matching documents using MongoDB's text relevance score.

---

# 2. `ingest_document.py` — Ingestion Script

### What was changed?

Previously, the script only uploaded the PDF and saved its metadata.

Now:

* After uploading the PDF, `pi_client.get_tree(doc_id)` is called.
* The PageIndex tree is retrieved.
* All nodes are extracted from the tree.
* The extracted nodes are inserted into the `extracted_nodes` collection using `insert_many()`.
* Each node also stores the `pageindex_doc_id`, which allows the search to remain specific to the selected document.

### How to run it

```bash
.\venv\Scripts\python.exe src/ingest_document.py "C:\path\to\ncert_book.pdf"
```

---

# 3. `chatbot.py` — Agno Agent + Tool Calling

This is the **main architectural change** in the project.

### What was changed?

Previously:

```text
Direct OpenAI/Gemini API call
```

Now:

```text
Agno Agent
     ↓
Registered Tools
     ↓
MongoDB Search
     ↓
Gemini
```

The application now uses `agno.agent.Agent` with proper tool registration and agent instructions.

---

## Technical Details

### LLM Integration

The project uses `OpenAIChat`, but it is configured to communicate with Google's **OpenAI-compatible Gemini endpoint**:

```text
https://generativelanguage.googleapis.com/v1beta/openai/
```

This approach was used because the `agno.models.google.Gemini` integration had compatibility issues with **Python 3.9**, particularly due to `google-genai` SDK version compatibility.

Therefore, instead of directly using the Agno Gemini model integration, the application uses Google's official OpenAI-compatible endpoint through `OpenAIChat`.

---

## `search_book_content` Tool

A Python function called `search_book_content` acts as the agent's search tool.

The tool:

1. Receives the search query.
2. Searches MongoDB using `$text`.
3. Retrieves the most relevant chunks.
4. Returns the top 5 results in a formatted string.
5. The agent reads those results and uses them to generate the final answer.

The agent is explicitly instructed:

```text
ALWAYS use the tool before answering
```

This ensures that the agent searches the uploaded book before generating an answer.

---

# Agent Flow

Suppose the user asks:

```text
Tell me about chemical reactions
```

The actual flow is:

```text
User:
"Tell me about chemical reactions"
        ↓
Agno Agent
        ↓
Agent decides:
"I need to call search_book_content"
        ↓
Tool Call:
search_book_content(query="chemical reactions")
        ↓
MongoDB
        ↓
$text search
        ↓
Top 5 matching chunks
        ↓
Agent receives the chunks
        ↓
Agent generates the answer
        ↓
User receives the answer
+
Tool call details are visible in the UI
```

This makes the chatbot more transparent because the user can see what the agent searched before producing an answer.

---

# 4. `app.py` — Streamlit Frontend

### What was changed?

The Streamlit frontend now provides:

* Chat history using `st.session_state`.
* Document selection.
* Agent re-initialization whenever a different document is selected.
* Tool-call visibility.
* Expandable sections showing the agent's tool activity.
* An `asyncio` event-loop fix for Streamlit + Agno compatibility.

---

## Tool Call Visibility

After the agent responds, the application extracts information about the tool calls, including:

* Which tool was called:

  ```text
  search_book_content
  ```

* What arguments were passed:

  ```text
  query: "chemical reactions"
  ```

* What result was returned:

  ```text
  Content preview...
  ```

This information is displayed inside an expandable section in the Streamlit UI.

Therefore, instead of simply seeing:

```text
Generating answer...
```

the user can inspect what the agent actually did.

---

# 🛠️ Tech Stack

| Component           | Technology                     | Why it is used                                               |
| ------------------- | ------------------------------ | ------------------------------------------------------------ |
| Agent Framework     | **Agno** (v2.6.9)              | Proper tool calling and agent lifecycle management           |
| LLM                 | **Gemini 2.0 Flash Lite**      | Fast and available through the free tier                     |
| LLM Access          | **OpenAI-compatible endpoint** | Avoids the Python 3.9 `google-genai` SDK compatibility issue |
| Database            | **MongoDB** (Docker)           | Full-text search using a `$text` index                       |
| Document Processing | **PageIndex API**              | Extracts sub-topic-level content from PDFs                   |
| Frontend            | **Streamlit** (v1.12.0)        | Quick UI development and session-state management            |

---

# 🚀 Setup & Run

## Prerequisites

The project requires:

* Python 3.9+
* Docker for MongoDB
* PageIndex API Key
* Gemini API Key

---

## Installation

Create the virtual environment:

```bash
python -m venv venv
```

Activate it:

```bash
.\venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Install the required additional packages:

```bash
pip install agno==2.6.9 google-genai openai
```

---

# Environment Variables

Create a `.env` file:

```env
PAGEINDEX_API_KEY=your_key_here
GEMINI_API_KEY=your_gemini_key_here
MONGO_URI=mongodb://admin:password@localhost:27017/
```

---

# Start MongoDB

Run:

```bash
docker-compose up -d
```

This starts the MongoDB container in the background.

---

# Ingest a Book

Run:

```bash
.\venv\Scripts\python.exe src/ingest_document.py "C:\path\to\book.pdf"
```

The ingestion process will:

```text
PDF
 ↓
PageIndex
 ↓
Document Tree
 ↓
Sub-topic Nodes
 ↓
MongoDB extracted_nodes
```

---

# Run the Chatbot

Run:

```bash
.\venv\Scripts\python.exe -m streamlit run src/app.py
```

Then open:

```text
http://localhost:8501
```

in your browser and start chatting with the uploaded book.

---

# 📊 MongoDB Collections

The application uses two main collections.

---

## `document_nodes` — Document Metadata

Example:

```json
{
  "filename": "jesc101.pdf",
  "upload_date": "2026-07-04T...",
  "pageindex_doc_id": "pi-cmr5bi6mj00i601qwqljybo0f",
  "status": "indexed",
  "description": "NCERT Class 10 Science Chapter 1"
}
```

This collection stores information about the uploaded documents.

---

## `extracted_nodes` — Sub-topic Chunks

Example:

```json
{
  "title": "Chemical Reactions and Equations",
  "node_id": "...",
  "page_index": 1,
  "text": "A chemical reaction is a process in which...",
  "pageindex_doc_id": "pi-cmr5bi6mj00i601qwqljybo0f"
}
```

These are the actual searchable content chunks extracted from the PageIndex document tree.

---

## Text Index

The collection has a MongoDB text index:

```text
subtopic_text_index
```

The index is created over:

```text
text
content
```

This allows MongoDB to perform full-text searches over the extracted sub-topic content.

---

# ⚠️ Known Issues / Limitations

## 1. Python 3.9 Constraint

The project currently has a Python 3.9 compatibility constraint.

Because of this:

* Newer versions of Streamlit cannot be used freely.
* The `google-genai` SDK has compatibility/version issues.
* The Agno Gemini integration cannot be used directly in the current setup.

Workarounds have therefore been implemented.

---

## 2. Gemini Free-Tier Quota

Gemini's free tier has usage limits.

If the quota is exceeded, the application may return:

```text
429 RESOURCE_EXHAUSTED
```

In that situation, the user needs to wait until the quota becomes available again.

---

## 3. Streamlit 1.12

The project uses:

```text
Streamlit 1.12.0
```

Because `st.chat_message` is not available in this version, the UI uses:

```text
st.text_input
```

along with:

```text
st.expander
```

to implement the chat interaction and tool-call visibility.

---

# 🔄 Complete End-to-End Architecture

The complete system can be summarized as:

```text
                    ┌─────────────────────┐
                    │     PDF Book        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   PageIndex API     │
                    │   Document Tree     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Sub-topic Extraction│
                    └──────────┬──────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │          MongoDB                │
              │                                │
              │  document_nodes                │
              │  extracted_nodes               │
              │       +                        │
              │  $text Index                   │
              └──────────────┬─────────────────┘
                             │
                             │ Search Tool
                             ▼
                    ┌─────────────────────┐
                    │    Agno Agent       │
                    │                     │
                    │ Gemini 2.0 Flash    │
                    │ Lite                │
                    │                     │
                    │ Tools + Instructions│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Streamlit UI       │
                    │                     │
                    │ Answer              │
                    │ +                   │
                    │ Tool Calls          │
                    │ +                   │
                    │ Tool Results        │
                    └─────────────────────┘
```

## Query-Time Flow

```text
User Question
      ↓
Streamlit
      ↓
Agno Agent
      ↓
search_book_content()
      ↓
MongoDB $text Search
      ↓
Top 5 Relevant Chunks
      ↓
Agno Agent
      ↓
Gemini
      ↓
Final Answer
      ↓
Streamlit
      ↓
Answer + Tool Call Details
```

This architecture separates the system into clear layers:

```text
Document Processing
        ↓
Data Storage
        ↓
Retrieval
        ↓
Agent Reasoning
        ↓
User Interface
```

The main architectural improvement is that the chatbot has moved from a **direct LLM-call architecture** to an **agent-based retrieval architecture**, where the Agno agent can use a registered MongoDB search tool to retrieve relevant information from the uploaded book before generating its response.
