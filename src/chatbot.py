import os
import json
from typing import List
from dotenv import load_dotenv
import streamlit as st
from database import DatabaseManager
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.vectordb.qdrant import Qdrant, SearchType
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.db.mongo import MongoDb
from qdrant_client.http import models
from logger import logger

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq provides a fast OpenAI-compatible endpoint.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Maximum characters per chunk sent to the LLM to keep context lean
MAX_CHUNK_CHARS = 600


def get_agent(doc_ids, doc_names: str, id_to_filename_map: dict, db_manager: DatabaseManager = None) -> Agent:
    """Creates a single optimized Agno Agent wired to Gemini and MongoDB.

    Architecture note: We use a SINGLE agent with direct tool access instead of
    a multi-agent delegation chain. This reduces LLM calls from 4 to 1-2 per
    user query, dramatically improving speed and reducing token usage.
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    filename_to_id_map = {v: k for k, v in id_to_filename_map.items()}

    # Pre-fetch all document metadata once at init so the agent never needs to query for it
    summaries = db_manager.get_document_summaries(doc_ids)
    if doc_ids == "ALL":
        selected_filenames = [s.get("filename") for s in summaries if s.get("filename")]
    else:
        selected_filenames = [id_to_filename_map.get(did, "unknown") for did in doc_ids]

    # Build rich context string with descriptions baked in
    doc_context_lines = []
    for s in summaries:
        fname = s.get("filename")
        desc = s.get("description", "No description")
        if fname:
            doc_context_lines.append(f"  - {fname}: {desc}")
    doc_context_str = "\n".join(doc_context_lines)

    # --- Qdrant DB Setup ---
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "textbook_knowledge")
    
    # Custom Qdrant class to support list matching in filters (MatchAny)
    class FilterableQdrant(Qdrant):
        def _format_filters(self, filters: dict) -> models.Filter:
            if not filters:
                return None
            conditions = []
            for key, value in filters.items():
                if "." not in key and not key.startswith("meta_data."):
                    key = f"meta_data.{key}"
                
                if isinstance(value, list):
                    conditions.append(models.FieldCondition(key=key, match=models.MatchAny(any=value)))
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, list):
                            conditions.append(models.FieldCondition(key=f"{key}.{sub_key}", match=models.MatchAny(any=sub_value)))
                        else:
                            conditions.append(models.FieldCondition(key=f"{key}.{sub_key}", match=models.MatchValue(value=sub_value)))
                else:
                    conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
            return models.Filter(must=conditions)

    vector_db = FilterableQdrant(
        collection=qdrant_collection,
        url=qdrant_url,
        search_type=SearchType.hybrid,
        embedder=FastEmbedEmbedder(id="jinaai/jina-embeddings-v2-small-en", dimensions=512),
    )

    # --- Tool Definitions (direct, no delegation layer) ---

    def search_book_content(query: str, target_filename: str = None) -> str:
        """Search the book's sub-topic chunks stored in Qdrant using hybrid search (semantic + keyword).
        Use this for factual questions about specific topics, concepts, or details.
        Args:
            query: The search query to find relevant content.
            target_filename: Optional. The exact filename to search within (e.g., 'jesc101.pdf').
        Returns:
            A formatted string of the top matching sub-topic chunks.
        """
        logger.info(f"Tool 'search_book_content' called | query: {query}, target: {target_filename}")

        search_docs = doc_ids
        if target_filename:
            if target_filename in filename_to_id_map:
                search_docs = [filename_to_id_map[target_filename]]
            else:
                return f"Error: '{target_filename}' is not in the selected documents."

        filters = {}
        if search_docs != "ALL":
            if isinstance(search_docs, list):
                filters["pageindex_doc_id"] = search_docs
            else:
                filters["pageindex_doc_id"] = search_docs

        try:
            results = vector_db.search(query, limit=5, filters=filters)
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return f"Error searching vector database: {e}"

        if not results:
            logger.warning("Tool found no matching content.")
            return "No matching content found in the document(s)."

        formatted = []
        for res in results:
            text = res.content
            meta = res.meta_data or {}
            topic = meta.get("topic") or "Untitled Topic"
            subtopic = meta.get("subtopic")
            title = f"{topic} > {subtopic}" if subtopic else topic
            source_id = meta.get("pageindex_doc_id", "")
            source_name = id_to_filename_map.get(source_id, meta.get("filename", "Unknown Book"))

            # Truncate long chunks to keep context lean and fast
            if len(text) > MAX_CHUNK_CHARS:
                text = text[:MAX_CHUNK_CHARS] + "..."
            formatted.append(f"### {title}\n[Source: {source_name}]\n{text}")

        return "\n\n---\n\n".join(formatted)

    def get_topics(target_filename: str = None) -> str:
        """Fetch all available topics for a specific chapter (document).
        Use this as the first step when you need to know what a chapter is about or need to select a topic for a quiz.
        Args:
            target_filename: Optional. The exact filename of the chapter (e.g., 'jesc101.pdf').
        Returns:
            A formatted JSON string list of topics.
        """
        logger.info(f"Tool 'get_topics' called for: {target_filename}")
        search_docs = doc_ids
        if target_filename:
            if target_filename in filename_to_id_map:
                search_docs = [filename_to_id_map[target_filename]]
            else:
                return f"Error: '{target_filename}' is not in the selected documents."

        topics = db_manager.get_topics(search_docs)
        if not topics:
            return "No topics found."
        return json.dumps(topics)

    def get_subtopics(topic_name: str, target_filename: str = None) -> str:
        """Fetch all subtopics that fall under a specific topic within a chapter.
        Use this as the second step after get_topics to discover subtopics to read or quiz on.
        Args:
            topic_name: The exact name of the topic.
            target_filename: Optional. The exact filename of the chapter.
        Returns:
            A formatted JSON string list of subtopics.
        """
        logger.info(f"Tool 'get_subtopics' called for topic: {topic_name}, doc: {target_filename}")
        search_docs = doc_ids
        if target_filename:
            if target_filename in filename_to_id_map:
                search_docs = [filename_to_id_map[target_filename]]
            else:
                return f"Error: '{target_filename}' is not in the selected documents."

        subtopics = db_manager.get_subtopics(topic_name, search_docs)
        if not subtopics:
            return "No subtopics found for this topic."
        return json.dumps(subtopics)

    def get_subtopic_context(topic_name: str, subtopic_name: str, target_filename: str = None) -> str:
        """Retrieve the exact text content of a specific subtopic.
        Use this to fetch the text required to generate questions, create a summary, or read a section.
        This ensures you do not exceed your token limit.
        Args:
            topic_name: The exact name of the topic.
            subtopic_name: The exact name of the subtopic.
            target_filename: Optional. The exact filename of the chapter.
        Returns:
            A formatted string of the subtopic's content.
        """
        logger.info(f"Tool 'get_subtopic_context' called for topic: {topic_name}, subtopic: {subtopic_name}")
        search_docs = doc_ids
        if target_filename:
            if target_filename in filename_to_id_map:
                search_docs = [filename_to_id_map[target_filename]]
            else:
                return f"Error: '{target_filename}' is not in the selected documents."

        results = db_manager.get_subtopic_context(topic_name, subtopic_name, search_docs, limit=10)
        if not results:
            return "No content found for this subtopic."

        formatted = []
        for res in results:
            text = res.get("text") or res.get("content") or res.get("data", "")
            if text:
                if len(text) > MAX_CHUNK_CHARS:
                    text = text[:MAX_CHUNK_CHARS] + "..."
                formatted.append(f"### {topic_name} > {subtopic_name}\n{text}")

        return "\n\n---\n\n".join(formatted)

    # --- Model ---
    model = OpenAIChat(
        id="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
    )

    # --- MongoDB session/memory storage for the Agent ---
    mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
    mongo_db = MongoDb(
        db_url=mongo_uri,
        db_name=os.getenv("MONGO_DB_NAME", "pageindex_db_v2"),
        session_collection="agent_sessions",
        memory_collection="agent_memory",
    )

    # --- Single Unified Agent ---
    agent = Agent(
        name="BookAssistant",
        role="An intelligent assistant that answers questions about books and documents using MongoDB search.",
        model=model,
        db=mongo_db,
        add_history_to_context=True,
        tools=[search_book_content, get_topics, get_subtopics, get_subtopic_context],
        tool_call_limit=20,
        retries=2,
        delay_between_retries=5,
        exponential_backoff=False,
        telemetry=False,
        description=(
            f"You are a knowledgeable book assistant. The user has explicitly selected these documents (these are the EXACT filenames you must use when calling tools):\n"
            f"{doc_context_str}\n\n"
            f"You have direct access to search tools to find content in these specific books."
        ),
        instructions=[
            "IMPORTANT RULES — follow these strictly:",
            f"1. You already know the selected documents and their descriptions (listed above). For simple questions about genre, topic, or what a book is about, answer DIRECTLY from this context. Do NOT call any tools.",
            f"2. The ONLY valid chapter filenames you can pass to your tools are: {', '.join(selected_filenames)}. NEVER invent or hallucinate filenames (e.g. do not use 'chapter1.pdf' unless it is in the valid list).",
            "3. For factual questions requiring specific content, use the search_book_content tool.",
            "4. TOKEN LIMIT WARNING: You have a strict 8000 token limit. DO NOT attempt to read full chapters. If asked to generate a quiz or questions from a chapter, use the hierarchical discovery tools:",
            "   - First, call get_topics(target_filename) to see what topics exist.",
            "   - Next, pick a topic (randomly or sequentially) and call get_subtopics(topic_name, target_filename).",
            "   - Pick a subtopic and call get_subtopic_context(topic_name, subtopic_name, target_filename).",
            "   - Generate your questions based ONLY on the retrieved subtopic context. This ensures you do not exhaust your token limit.",
            "5. Keep your answers concise and well-formatted in markdown.",
            "6. When referencing information, mention the exact source document filename.",
            "7. If no tool results are found, say so honestly — do not make up content.",
        ],
        markdown=True,
    )

    logger.info(f"Agent initialized for context: '{doc_names}' with {len(selected_filenames)} chapters")
    return agent
