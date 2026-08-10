import logging
import os

def setup_logger():
    log_file = "chatbot.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("PageIndex-Chatbot")

logger = setup_logger()
