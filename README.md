# 📄 PageIndex + MongoDB Vectorless RAG Chatbot

This project is an end-to-end Chatbot application that demonstrates **Vectorless Retrieval-Augmented Generation (RAG)**. It uses **PageIndex** to act as the heavy-duty "brain" for document reasoning, while keeping a highly optimized, lightweight local **MongoDB** database to manage document metadata and user state.

## 🏗️ Architecture
Unlike traditional RAG systems that require you to chunk documents, calculate embeddings, and host expensive Vector Databases (like Pinecone), this architecture is entirely **Vectorless**:

1. **MongoDB (The Librarian):** Stores lightweight references (`doc_id`), upload dates, filenames, and custom descriptions. It populates the application UI instantly without making expensive internet calls.
2. **PageIndex (The Brain):** The raw PDF is sent directly to the PageIndex API. PageIndex handles the complex text chunking and builds a searchable tree on their remote servers. 
3. **Streamlit (The UI):** A beautiful frontend that allows users to select their uploaded books and chat with them using Google's Gemini LLM.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+
- Docker (to run the local MongoDB container)
- A [PageIndex API Key](https://dash.pageindex.ai/)
- A [Google Gemini API Key](https://aistudio.google.com/)

### 2. Installation
Clone the repository and install the dependencies:
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory and add your keys:
```env
PAGEINDEX_API_KEY=your_pageindex_key_here
GEMINI_API_KEY=your_gemini_key_here
MONGO_URI=mongodb://admin:password@localhost:27017/
```

### 4. Start the Database
Spin up the local MongoDB container using Docker Compose:
```bash
docker-compose up -d
```

---

## 📚 Usage

### Ingesting a Book
You can upload any PDF on your computer using the command-line ingestion script. This securely sends the file to PageIndex and saves the metadata to your local MongoDB:

```bash
python src\ingest_document.py "C:\Path\To\Your_Book.pdf" --description "My custom description"
```

### Running the Chatbot
Once you have ingested at least one document, start the Streamlit web app:

```bash
streamlit run src\app.py
```
Open `http://localhost:8501` in your browser. Select your book from the sidebar and start chatting!

---

## 🧰 Utility Scripts (Educational Purposes)

This repository contains a few extra files in the root directory that are **not required** for the core chatbot to run, but are included as helpful tools:

* **`sync.py`**
  * **Purpose:** The core architecture is "Vectorless," meaning your local database holds no text. However, if you want to visually see exactly how PageIndex chunked your book under the hood, running this script will download all the raw text nodes from PageIndex and save them into a new `extracted_nodes` collection in MongoDB. You can then view them using MongoDB Compass.
* **`shorten_pdf.py`**
  * **Purpose:** A helper script to quickly truncate a massive PDF down to a specific number of pages. Highly useful if you are using a free-tier PageIndex API key with strict page limits and just want to test the architecture.
