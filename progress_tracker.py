import time
import json
import logging
import requests

# Configure verbose logging.
logging.basicConfig(level=logging.DEBUG)

# Define microservice base URL.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com"

def track_batch_progress(batch_id: str):
    # Log starting poll event.
    logging.debug(f"Starting poll for batch: {batch_id}")

    while True:
        try:
            # Fetch current batch state.
            url = f"{AI_MANAGER_URL}/batch/{batch_id}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            batch = response.json()

            # Extract and log status.
            status = batch.get("processing_status")
            logging.info(f"Current batch status: {status}")

            if status == "ended":
                # Exit loop if ended.
                logging.debug("Batch processing has finished.")
                break

            # Log completion metrics.
            counts = batch.get("request_counts", {})
            logging.debug(f"Progress counts: {counts}")

        except requests.exceptions.RequestException as e:
            # Log connection error.
            logging.error(f"Error fetching batch: {e}")

        # Pause before next poll.
        logging.info("Sleeping 10s before next poll.")
        time.sleep(10)

def stream_request_progress():
    # Log streaming request start.
    logging.debug("Initiating streaming request.")

    # Define microservice payload.
    payload = {
        "provider": "anthropic",
        "model_key": "claude-opus-4-6",
        "query": "Explain quantum computing.",
        "parameters": {
            "stream": True,
            "max_tokens": 1024
        }
    }

    try:
        # Open continuous stream.
        url = f"{AI_MANAGER_URL}/stream"
        with requests.post(url, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            logging.info("Stream connection opened.")

            # Process stream events.
            for line in resp.iter_lines():
                if line:
                    # Log text chunk.
                    logging.debug("Text delta chunk received.")
                    # Decode and print line.
                    print(line.decode('utf-8'), end="", flush=True)

            # Log stream stop.
            logging.info("\nMessage generation stopped.")

    except requests.exceptions.RequestException as e:
        # Log connection error.
        logging.error(f"Streaming connection error: {e}")

if __name__ == "__main__":
    # Start execution.
    logging.debug("Script execution started.")
    # Track stream progress.
    stream_request_progress()
    # Track batch progress.
    # track_batch_progress("msgbatch_123")