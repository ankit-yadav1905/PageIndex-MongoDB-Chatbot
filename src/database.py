import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
DB_NAME = "pageindex_db"
COLLECTION_NAME = "document_nodes"

class DatabaseManager:
    def __init__(self):
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Trigger a connection test
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB.")
        except ConnectionFailure:
            print("Failed to connect to MongoDB. Is the Docker container running?")
            raise
        
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]

    def insert_node(self, node_data: dict):
        """Inserts a single document/node into MongoDB."""
        result = self.collection.insert_one(node_data)
        return result.inserted_id

    def get_all_nodes(self):
        """Retrieves all stored nodes."""
        return list(self.collection.find({}))
