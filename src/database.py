import os
import re
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from logger import logger

# Load environment variables from .env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "pageindex_db")
COLLECTION_NAME = "document_nodes"

class DatabaseManager:
    def __init__(self):
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Trigger a connection test
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB.")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB. Is the Docker container running? Error: {e}")
            raise
        
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]
        self.nodes_collection = self.db["extracted_nodes"]
        self._setup_indexes()
        
    def _setup_indexes(self):
        # We index both "text" and "content" to safely cover different PageIndex node schema possibilities
        self.nodes_collection.create_index(
            [("text", "text"), ("content", "text")],
            name="subtopic_text_index",
            background=True
        )

    def insert_node(self, node_data: dict):
        """Inserts a single document/node into MongoDB."""
        result = self.collection.insert_one(node_data)
        return result.inserted_id

    def get_all_nodes(self):
        """Retrieves all stored nodes."""
        return list(self.collection.find({}))

    def search_nodes(self, query: str, doc_ids, limit: int = 10):
        """Searches the extracted_nodes for a specific query across one, multiple, or ALL doc_ids."""
        logger.info(f"Searching MongoDB for query: '{query}' in doc_ids: '{doc_ids}'")
        
        search_filter = {"$text": {"$search": query}}
        if doc_ids != "ALL":
            if isinstance(doc_ids, list):
                search_filter["pageindex_doc_id"] = {"$in": doc_ids}
            else:
                search_filter["pageindex_doc_id"] = doc_ids
                
        cursor = self.nodes_collection.find(
            search_filter,
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        results = list(cursor)
        logger.info(f"Found {len(results)} matching chunks.")
        return results

    def get_chapter_content(self, doc_id: str, limit: int = 20):
        """Retrieves chunks of a specific chapter without using full-text search (ordered by page_number)."""
        logger.info(f"Fetching full content for chapter doc_id: '{doc_id}'")
        cursor = self.nodes_collection.find({"pageindex_doc_id": doc_id}).sort("meta_data.page_number", 1).limit(limit)
        return list(cursor)

    def get_topics(self, doc_ids):
        """Returns distinct topics for the given documents."""
        search_filter = {}
        if doc_ids != "ALL":
            if isinstance(doc_ids, list):
                search_filter["pageindex_doc_id"] = {"$in": doc_ids}
            else:
                search_filter["pageindex_doc_id"] = doc_ids
        
        return self.nodes_collection.distinct("meta_data.topic", filter=search_filter)

    def get_subtopics(self, topic: str, doc_ids):
        """Returns distinct subtopics for the given topic and documents."""
        search_filter = {"meta_data.topic": topic}
        if doc_ids != "ALL":
            if isinstance(doc_ids, list):
                search_filter["pageindex_doc_id"] = {"$in": doc_ids}
            else:
                search_filter["pageindex_doc_id"] = doc_ids
        
        return self.nodes_collection.distinct("meta_data.subtopic", filter=search_filter)

    def get_subtopic_context(self, topic: str, subtopic: str, doc_ids, limit: int = 15):
        """Retrieves chunks of a specific topic and subtopic."""
        search_filter = {}
        if topic and str(topic).strip().lower() not in ["none", "unknown"]:
            escaped_topic = re.escape(str(topic).strip())
            search_filter["meta_data.topic"] = {"$regex": escaped_topic, "$options": "i"}
            
        # Some chunks might have subtopic set to None or "None" if they are top-level
        if subtopic and str(subtopic).strip().lower() not in ["none", "unknown"]:
            escaped_subtopic = re.escape(str(subtopic).strip())
            search_filter["meta_data.subtopic"] = {"$regex": escaped_subtopic, "$options": "i"}
            
        if doc_ids != "ALL":
            if isinstance(doc_ids, list):
                search_filter["pageindex_doc_id"] = {"$in": doc_ids}
            else:
                search_filter["pageindex_doc_id"] = doc_ids
                
        cursor = self.nodes_collection.find(search_filter).sort("meta_data.page_number", 1).limit(limit)
        return list(cursor)

    def get_document_summaries(self, doc_ids):
        """Returns metadata (filename and description) for the requested documents."""
        search_filter = {}
        if doc_ids != "ALL":
            if isinstance(doc_ids, list):
                search_filter["pageindex_doc_id"] = {"$in": doc_ids}
            else:
                search_filter["pageindex_doc_id"] = doc_ids
                
        cursor = self.collection.find(search_filter, {"filename": 1, "description": 1, "class": 1, "chapter": 1, "pageindex_doc_id": 1, "_id": 0})
        return list(cursor)
