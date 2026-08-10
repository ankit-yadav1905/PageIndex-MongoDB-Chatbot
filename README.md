# 📚 PageIndex + MongoDB + Agno Agent Chatbot

## Kya hai ye project?

Ye ek **NCERT Book Chatbot** hai jo **Agno Agent Framework** use karta hai with **Gemini LLM** aur **MongoDB Full-Text Search**. Matlab aap ek PDF book upload karte ho, uske sub-topic level chunks MongoDB mein store hote hain, aur fir ek AI agent aapke questions ka answer deta hai by actually searching those chunks using tool calling.

---

## 🔄 Purana Code vs Naya Code — Kya Changes Kiye

### Pehle kya tha (Old Architecture):
- Direct Gemini/OpenAI API call hoti thi — koi agent framework nahi tha
- `sync.py` ek separate utility script tha jo manually run karna padta tha text nodes download karne ke liye
- MongoDB sirf metadata store karta tha (filename, doc_id, date)
- UI mein koi tool call visibility nahi thi — bas spinner ghoomta tha aur answer aa jaata tha

### Ab kya hai (New Architecture):
- **Agno Agent Framework** integrate kiya hai — proper `Agent` with `tools` aur `instructions`
- **Sub-topic chunks ab automatically ingest hote hain** — jaise hi PDF upload hoti hai, PageIndex se tree fetch hota hai aur MongoDB mein store hota hai
- **MongoDB Full-Text Search** — `$text` index lagaya hai `text` aur `content` fields pe for fast search
- **Tool Calling** — Agent ke paas `search_book_content` tool hai jo MongoDB mein search karta hai
- **Frontend mein Tool Calls dikhte hain** — UI mein expander mein tool name, arguments, aur results sab visible hain

---

## 📁 Project Structure — Kaun si file kya karti hai

```
src/
├── database.py          # MongoDB connection + text search
├── ingest_document.py   # PDF upload + sub-topic chunking
├── chatbot.py           # Agno Agent + Gemini + Tool setup
└── app.py               # Streamlit Frontend UI
```

### 1. `database.py` — Database Layer

**Kya change kiya:**
- Ek naya collection add kiya: `extracted_nodes` — ye sub-topic chunks store karta hai
- MongoDB `$text` index banaya `text` aur `content` fields pe (name: `subtopic_text_index`)
- `search_nodes()` method add kiya jo full-text search karta hai with `textScore` sorting

**Kaise kaam karta hai:**
```
User question → MongoDB $text search → Top 5 relevant chunks return
```

### 2. `ingest_document.py` — Ingestion Script

**Kya change kiya:**
- Pehle sirf PDF upload hoti thi aur metadata save hota tha
- Ab upload ke turant baad `pi_client.get_tree(doc_id)` call hota hai
- Tree se saare nodes nikal ke `extracted_nodes` collection mein `insert_many()` se daal diye jaate hain
- Har node ke saath `pageindex_doc_id` attach hota hai taaki baad mein search scope specific rahe

**Run kaise karein:**
```bash
.\venv\Scripts\python.exe src/ingest_document.py "C:\path\to\ncert_book.pdf"
```

### 3. `chatbot.py` — Agno Agent + Tool Calling (MAIN CHANGE)

**Kya change kiya:**
- **Pehle:** Direct `openai.ChatCompletion.create()` ya Gemini API call
- **Ab:** `agno.agent.Agent` use hota hai with proper tool registration

**Technical Details:**
- `OpenAIChat` model use kiya hai jo Google ke **OpenAI-compatible endpoint** pe point karta hai
  - URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
  - Ye isliye kiya kyunki `agno.models.google.Gemini` Python 3.9 pe compatible nahi hai (google-genai SDK version issues)
- `search_book_content` ek Python function hai jo `@tool` ki tarah kaam karta hai
  - Ye MongoDB mein `$text` search karta hai
  - Top 5 results ko formatted string mein return karta hai
- Agent ko instruction diya hai ki **"ALWAYS use the tool before answering"**

**Agent Flow:**
```
User: "Chemical reactions ke baare mein batao"
   ↓
Agent decides: "Mujhe search_book_content tool call karna chahiye"
   ↓
Tool Call: search_book_content(query="chemical reactions")
   ↓
MongoDB: $text search → returns 5 matching chunks
   ↓
Agent: Chunks padhke answer generate karta hai
   ↓
User ko answer milta hai with tool call details visible in UI
```

### 4. `app.py` — Streamlit Frontend

**Kya change kiya:**
- Chat history maintain hoti hai `st.session_state` mein
- Document select karne pe agent re-initialize hota hai
- Agent ka response aane ke baad **tool calls extract** kiye jaate hain:
  - Konsa tool call hua (`search_book_content`)
  - Kya arguments the (`query: "..."`)
  - Kya result aaya (content preview)
- Ye sab ek **expandable section** mein dikhta hai UI mein
- `asyncio` event loop fix kiya hai Streamlit + Agno compatibility ke liye

---

## 🛠️ Tech Stack

| Component | Technology | Kyun use kiya |
|-----------|-----------|---------------|
| Agent Framework | **Agno** (v2.6.9) | Proper tool calling, agent lifecycle management |
| LLM | **Gemini 2.0 Flash Lite** | Fast, free tier available |
| LLM Access | **OpenAI-compatible endpoint** | Python 3.9 pe google-genai SDK issue avoid karne ke liye |
| Database | **MongoDB** (Docker) | Full-text search with `$text` index |
| Document Processing | **PageIndex API** | PDF se sub-topic level chunks extract karta hai |
| Frontend | **Streamlit** (v1.12.0) | Quick UI, session state management |

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.9+
- Docker (MongoDB ke liye)
- PageIndex API Key
- Gemini API Key

### Installation
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
pip install agno==2.6.9 google-genai openai
```

### Environment Variables (`.env` file)
```env
PAGEINDEX_API_KEY=your_key_here
GEMINI_API_KEY=your_gemini_key_here
MONGO_URI=mongodb://admin:password@localhost:27017/
```

### Start MongoDB
```bash
docker-compose up -d
```

### Ingest a Book
```bash
.\venv\Scripts\python.exe src/ingest_document.py "C:\path\to\book.pdf"
```

### Run the Chatbot
```bash
.\venv\Scripts\python.exe -m streamlit run src/app.py
```
Browser mein `http://localhost:8501` kholo aur chat karo!

---

## 🧠 Mentor ke liye Key Points

1. **Agno Agent Framework** use kiya hai — direct API calls nahi, proper agent with tools
2. **Tool Calling** implement kiya hai — agent khud decide karta hai kab search karna hai
3. **MongoDB Full-Text Search** — `$text` index with `textScore` ranking
4. **Sub-topic level chunking** — PageIndex ka `get_tree()` use karke automatic chunking
5. **Frontend mein tool calls visible** — transparency hai ki agent kya kar raha hai
6. **OpenAI-compatible endpoint** — Google ka official endpoint hai, production-ready approach hai
7. **Error handling** — retries disabled (`max_retries=0`, `retries=0`), fail fast approach

---

## 📊 MongoDB Collections

### `document_nodes` — Document Metadata
```json
{
  "filename": "jesc101.pdf",
  "upload_date": "2026-07-04T...",
  "pageindex_doc_id": "pi-cmr5bi6mj00i601qwqljybo0f",
  "status": "indexed",
  "description": "NCERT Class 10 Science Chapter 1"
}
```

### `extracted_nodes` — Sub-topic Chunks (TEXT INDEXED)
```json
{
  "title": "Chemical Reactions and Equations",
  "node_id": "...",
  "page_index": 1,
  "text": "A chemical reaction is a process in which...",
  "pageindex_doc_id": "pi-cmr5bi6mj00i601qwqljybo0f"
}
```

Text index: `subtopic_text_index` on fields `text` + `content`

---

## ⚠️ Known Issues / Limitations

- **Python 3.9 constraint** — Isse newer Streamlit (chat UI) aur google-genai SDK nahi chal paate, isliye workarounds lagaye hain
- **Gemini Free Tier Quota** — Daily limit hai, agar exceed ho jaaye to "429 RESOURCE_EXHAUSTED" error aata hai, thodi der wait karo
- **Streamlit 1.12** — `st.chat_message` available nahi hai, isliye `st.text_input` + `st.expander` use kiya hai
