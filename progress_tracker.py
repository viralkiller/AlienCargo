import os
import json
import logging

# Setup basic logging configuration.
logging.basicConfig(level=logging.DEBUG)

# Define local storage path.
STORAGE_FILE = "generation_times.json"

def load_times():
    # Check if storage file exists.
    logging.debug(f"Checking for file: {STORAGE_FILE}")
    if not os.path.exists(STORAGE_FILE):
        # Log missing file.
        logging.info("Storage file not found.")
        return []

    try:
        # Read and parse JSON file.
        logging.debug("Opening file for reading.")
        with open(STORAGE_FILE, 'r') as f:
            data = json.load(f)
        # Log successful read.
        logging.info(f"Loaded {len(data)} time records.")
        return data
    except Exception as e:
        # Log file read error.
        logging.error(f"Error reading file: {e}")
        return []

def save_time(duration_ms):
    # Log save request.
    logging.debug(f"Saving new duration: {duration_ms}ms")

    # Load existing time records.
    times = load_times()

    # Append new duration.
    times.append(duration_ms)
    logging.debug("Appended duration to list.")

    try:
        # Write list to JSON file.
        logging.debug("Opening file for writing.")
        with open(STORAGE_FILE, 'w') as f:
            json.dump(times, f)
        # Log successful write.
        logging.info("Successfully saved times to disk.")
    except Exception as e:
        # Log write error.
        logging.error(f"Error writing file: {e}")

def get_average_time():
    # Log average calculation request.
    logging.debug("Calculating average generation time.")

    # Load current times.
    times = load_times()

    if not times:
        # Return default if no data.
        logging.info("No data. Returning default 15000ms.")
        return 15000.0

    # Calculate mathematical average.
    avg = sum(times) / len(times)

    # Log calculated average.
    logging.info(f"Calculated average: {avg:.2f}ms")
    return avg

if __name__ == "__main__":
    # Log script start.
    logging.debug("Progress tracker execution started.")

    # Test saving a time.
    logging.info("Testing save function.")
    save_time(14500)

    # Test retrieving average.
    logging.info("Testing average calculation.")
    avg_time = get_average_time()

    # Log script end.
    logging.debug("Progress tracker execution finished.")