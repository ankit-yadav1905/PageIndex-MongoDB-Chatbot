import os
from dotenv import load_dotenv
from database import DatabaseManager
from pageindex import PageIndexClient
from openai import OpenAI

load_dotenv()
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def initialize_clients():
    if not PAGEINDEX_API_KEY:
        raise ValueError("PAGEINDEX_API_KEY not found in .env")
    db_manager = DatabaseManager()
    pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    gemini_client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    return db_manager, pi_client, gemini_client

def chat_with_document(messages_history: list, doc_name: str):
    db_manager, pi_client, gemini_client = initialize_clients()
    record = db_manager.collection.find_one({"filename": doc_name})
    if not record:
        return f"Error: Document '{doc_name}' not found in MongoDB."
        
    doc_id = record.get("pageindex_doc_id")
    try:
        response = pi_client.chat_completions(
            messages=messages_history,
            doc_id=doc_id
        )
        answer = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return answer
    except Exception as e:
        print(f"Error querying PageIndex: {e}. Falling back to Gemini API.")
        if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
            try:
                gemini_messages = [{"role": "system", "content": "You are a helpful assistant."}] + messages_history
                gemini_response = gemini_client.chat.completions.create(
                    model="gemini-1.5-flash",
                    messages=gemini_messages
                )
                return gemini_response.choices[0].message.content
            except Exception as gemini_err:
                return f"Gemini API Error: {gemini_err}"
        else:
            return "Error: PageIndex failed and GEMINI_API_KEY is not set."

if __name__ == "__main__":
    sample_filename = "sample_document.pdf"
    test_messages = [{"role": "user", "content": "What is the main objective of Project Alpha?"}]
    print(chat_with_document(test_messages, sample_filename))
