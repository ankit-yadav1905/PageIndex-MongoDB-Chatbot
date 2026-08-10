import os
import argparse
from datetime import datetime
from dotenv import load_dotenv
from database import DatabaseManager
from pageindex import PageIndexClient
from logger import logger

from agno.vectordb.qdrant import Qdrant, SearchType
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.knowledge.document.base import Document

load_dotenv()
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")

def ingest_file(file_path: str, description: str = "No description provided", class_name: str = "Unknown", chapter: str = "Unknown"):
    logger.info(f"Starting ingestion process for: {file_path}")
    db_manager = DatabaseManager()
    
    if not PAGEINDEX_API_KEY:
        raise ValueError("PAGEINDEX_API_KEY is not set.")
    pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    
    logger.info("Uploading document to PageIndex...")
    try:
        result = pi_client.submit_document(file_path)
        doc_id = result.get("doc_id")
        if not doc_id:
            raise Exception(f"Failed to retrieve doc_id: {result}")
        logger.info(f"Successfully indexed! Received doc_id: {doc_id}")
    except Exception as e:
        logger.error(f"Error during PageIndex submission: {e}")
        return
        
    document_record = {
        "filename": os.path.basename(file_path),
        "upload_date": datetime.utcnow(),
        "pageindex_doc_id": doc_id,
        "status": "indexed",
        "description": description,
        "class": class_name,
        "chapter": chapter
    }
    inserted_id = db_manager.insert_node(document_record)
    logger.info(f"Metadata stored in MongoDB with _id: {inserted_id}")
    
    # Initialize Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "textbook_knowledge")
    
    logger.info(f"Connecting to Qdrant at {qdrant_url}, Collection: {qdrant_collection}")
    vector_db = Qdrant(
        collection=qdrant_collection,
        url=qdrant_url,
        search_type=SearchType.hybrid,
        embedder=FastEmbedEmbedder(id="jinaai/jina-embeddings-v2-small-en", dimensions=512),
    )
    
    if not vector_db.exists():
        logger.info(f"Creating new Qdrant collection: {qdrant_collection}...")
        vector_db.create()
    
    # Fetch tree and store extracted nodes (sub-topic chunks)
    logger.info("Fetching sub-topic chunks from PageIndex...")
    import time
    max_retries = 10
    
    for attempt in range(max_retries):
        try:
            tree_data = pi_client.get_tree(doc_id)
            if tree_data and "result" in tree_data:
                root_nodes = tree_data["result"]
                
                # PageIndex returns a nested tree — flatten it into individual chunks
                def flatten_nodes(nodes, depth=0, current_topic=None, current_subtopic=None):
                    flat = []
                    for node in nodes:
                        node_title = node.get("title", "Untitled")
                        
                        # Determine topic and subtopic based on depth
                        topic = current_topic
                        subtopic = current_subtopic
                        
                        if depth == 0:
                            topic = node_title
                            subtopic = None
                        elif depth == 1:
                            subtopic = node_title
                        else:
                            # For depths > 1, append to subtopic or keep it as the deepest known
                            if subtopic:
                                subtopic = f"{subtopic} > {node_title}"
                            else:
                                subtopic = node_title

                        chunk_text = node.get("text", "")
                        if chunk_text and len(chunk_text.strip()) > 10:
                            # Prepend hierarchical metadata so it's captured strongly by sparse and dense embeddings
                            enhanced_text = f"Class: {class_name}\nChapter: {chapter}\nTopic: {topic or 'None'}\nSubtopic: {subtopic or 'None'}\n\n{chunk_text}"
                            
                            chunk_meta = {
                                "class": class_name,
                                "chapter": chapter,
                                "topic": topic,
                                "subtopic": subtopic,
                                "page_number": node.get("page_index", 0),
                                "node_id": node.get("node_id", ""),
                                "pageindex_doc_id": doc_id,
                                "filename": os.path.basename(file_path)
                            }
                            flat.append({"text": enhanced_text, "meta_data": chunk_meta})
                        
                        if "nodes" in node and node["nodes"]:
                            flat.extend(flatten_nodes(node["nodes"], depth + 1, topic, subtopic))
                    return flat
                
                all_chunks = flatten_nodes(root_nodes)
                
                if all_chunks:
                    # Clean up existing nodes in Mongo
                    db_manager.nodes_collection.delete_many({"pageindex_doc_id": doc_id})
                    
                    # We store just the meta-data or original chunks to mongo for backup if needed
                    mongo_chunks = [
                        {"pageindex_doc_id": doc_id, "node_id": c["meta_data"]["node_id"], "text": c["text"], "meta_data": c["meta_data"]} 
                        for c in all_chunks
                    ]
                    db_manager.nodes_collection.insert_many(mongo_chunks)
                    logger.info(f"Backed up {len(mongo_chunks)} chunks to MongoDB.")
                    
                    # Convert to Agno Documents and upsert into Qdrant
                    agno_docs = []
                    for idx, chunk in enumerate(all_chunks):
                        agno_docs.append(Document(
                            id=f"{doc_id}_{idx}",
                            content=chunk["text"],
                            meta_data=chunk["meta_data"]
                        ))
                        
                    logger.info(f"Upserting {len(agno_docs)} chunks into Qdrant Hybrid Search index...")
                    vector_db.upsert(content_hash=doc_id, documents=agno_docs)
                    
                    logger.info("Successfully upserted into Qdrant!")
                    break
                else:
                    logger.warning(f"Attempt {attempt+1}: No text chunks found yet. Waiting for PageIndex processing...")
                    time.sleep(5)
            else:
                logger.warning(f"Attempt {attempt+1}: Tree data not ready. Waiting...")
                time.sleep(5)
        except Exception as e:
            logger.error(f"Error extracting/storing nodes on attempt {attempt+1}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)
    else:
        logger.error("Failed to extract nodes after maximum retries. PageIndex processing might be delayed.")

    return doc_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF document into PageIndex and Qdrant/MongoDB.")
    parser.add_argument("file_path", type=str, help="Absolute path to the PDF file you want to ingest.")
    parser.add_argument("--description", type=str, default="No description provided", help="Optional description of the document.")
    parser.add_argument("--class_name", type=str, default="Unknown", help="Class (e.g. 'Class 10')")
    parser.add_argument("--chapter", type=str, default="Unknown", help="Chapter Name (e.g. 'Light Reflection')")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        logger.error(f"Could not find file at {args.file_path}")
    else:
        ingest_file(args.file_path, description=args.description, class_name=args.class_name, chapter=args.chapter)
