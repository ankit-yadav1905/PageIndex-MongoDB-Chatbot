import os
from pymongo import MongoClient
from pageindex import PageIndexClient
from dotenv import load_dotenv

load_dotenv()
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")

mongo = MongoClient(MONGO_URI)
db = mongo["pageindex_db"]
doc_collection = db["document_nodes"]
nodes_collection = db["extracted_nodes"]

pi_client = PageIndexClient(PAGEINDEX_API_KEY)
documents = list(doc_collection.find())
total_inserted = 0

for doc in documents:
    doc_id = doc.get("pageindex_doc_id")
    if not doc_id:
        continue
    
    try:
        tree_data = pi_client.get_tree(doc_id)
        if tree_data and "result" in tree_data:
            nodes = tree_data["result"]
            nodes_collection.delete_many({"pageindex_doc_id": doc_id})
            
            for node in nodes:
                node["pageindex_doc_id"] = doc_id
            
            if nodes:
                nodes_collection.insert_many(nodes)
                total_inserted += len(nodes)
    except Exception as e:
        pass

print(f"Total inserted: {total_inserted}")
