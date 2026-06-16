import os
import argparse
from datetime import datetime
from dotenv import load_dotenv
from database import DatabaseManager
from pageindex import PageIndexClient

load_dotenv()
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")

def ingest_file(file_path: str, description: str = "No description provided"):
    print(f"Starting ingestion process for: {file_path}")
    db_manager = DatabaseManager()
    
    if not PAGEINDEX_API_KEY:
        raise ValueError("PAGEINDEX_API_KEY is not set.")
    pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    
    print("Uploading document to PageIndex...")
    try:
        result = pi_client.submit_document(file_path)
        doc_id = result.get("doc_id")
        if not doc_id:
            raise Exception(f"Failed to retrieve doc_id: {result}")
        print(f"Successfully indexed! Received doc_id: {doc_id}")
    except Exception as e:
        print(f"Error during PageIndex submission: {e}")
        return
        
    document_record = {
        "filename": os.path.basename(file_path),
        "upload_date": datetime.utcnow(),
        "pageindex_doc_id": doc_id,
        "status": "indexed",
        "description": description
    }
    inserted_id = db_manager.insert_node(document_record)
    print(f"Metadata stored in MongoDB with _id: {inserted_id}")
    return doc_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF document into PageIndex and MongoDB.")
    parser.add_argument("file_path", type=str, help="Absolute path to the PDF file you want to ingest.")
    parser.add_argument("--description", type=str, default="No description provided", help="Optional description of the document.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"Error: Could not find file at {args.file_path}")
    else:
        ingest_file(args.file_path, description=args.description)
