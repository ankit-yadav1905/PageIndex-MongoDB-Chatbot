import os
import glob
import json
from datetime import datetime

# Force the application to use a new, clean MongoDB database for this batch
os.environ["MONGO_DB_NAME"] = "pageindex_db_v2"
os.environ["QDRANT_COLLECTION"] = "textbook_knowledge_v2"

# Now we can safely import our backend modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.ingest_document import ingest_file
from src.logger import logger

def batch_ingest(folder_path: str, log_file: str):
    logger.info(f"Starting batch ingestion from folder: {folder_path}")
    logger.info(f"Using clean database: {os.environ['MONGO_DB_NAME']}")
    
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    if not pdf_files:
        logger.error(f"No PDF files found in {folder_path}")
        return

    # Sort files to maintain logical chapter order
    pdf_files.sort()
    
    successful_files = set()
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                old_logs = json.load(f)
                for s in old_logs.get("successful", []):
                    successful_files.add(s["filename"])
        except Exception:
            pass
            
    ingest_logs = {
        "start_time": datetime.utcnow().isoformat(),
        "total_files": len(pdf_files),
        "successful": old_logs.get("successful", []) if 'old_logs' in locals() else [],
        "failed": [],
        "end_time": None
    }
    
    for idx, pdf_path in enumerate(pdf_files, start=1):
        filename = os.path.basename(pdf_path)
        if filename in successful_files:
            logger.info(f"[{idx}/{len(pdf_files)}] Skipping {filename} (already successful)")
            continue
            
        logger.info(f"[{idx}/{len(pdf_files)}] Processing {filename}...")
        
        # Derive some default metadata for these chapters
        # e.g., 'jesc101.pdf' -> Class 10, Chapter 1
        class_name = "Class 10 Science" 
        chapter_name = f"Chapter {idx}: {filename.replace('.pdf', '')}"
        
        try:
            # We call the existing ingest function
            doc_id = ingest_file(
                file_path=pdf_path,
                description="Batch Ingested Document",
                class_name=class_name,
                chapter=chapter_name
            )
            
            if doc_id:
                logger.info(f"Success! {filename} -> doc_id: {doc_id}")
                ingest_logs["successful"].append({
                    "filename": filename,
                    "doc_id": doc_id,
                    "chapter": chapter_name
                })
            else:
                raise Exception("ingest_file returned None (likely a PageIndex error).")
                
        except Exception as e:
            logger.error(f"Failed to ingest {filename}. Error: {e}")
            ingest_logs["failed"].append({
                "filename": filename,
                "error": str(e)
            })
            
        # Continuously write to the log file so progress isn't lost if it crashes
        with open(log_file, "w") as f:
            json.dump(ingest_logs, f, indent=4)
            
    ingest_logs["end_time"] = datetime.utcnow().isoformat()
    with open(log_file, "w") as f:
        json.dump(ingest_logs, f, indent=4)
        
    logger.info(f"Batch ingestion completed! Log saved to {log_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch Ingest a folder of PDFs.")
    parser.add_argument("folder_path", type=str, help="Absolute path to the folder containing PDFs")
    parser.add_argument("--log", type=str, default="batch_ingest_log.json", help="Path to save the JSON log")
    args = parser.parse_args()
    
    batch_ingest(args.folder_path, args.log)
