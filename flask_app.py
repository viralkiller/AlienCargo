# flask_app.py
import logging
import json
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify

# -----------------------------
# Config
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UNIVERSE_FILE = DATA_DIR / "universe.json"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("blackhole")

# -----------------------------
# App setup
# -----------------------------
app = Flask(__name__)

# -----------------------------
# Data Persistence Helpers
# -----------------------------
def load_universe_data():
    """Loads the entire universe dictionary from JSON."""
    if not UNIVERSE_FILE.exists():
        return {}
    try:
        with open(UNIVERSE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load universe data: {e}")
        return {}

def save_universe_data(new_data):
    """Merges new sector data into the existing JSON file."""
    try:
        # Load existing first to merge
        current = load_universe_data()
        current.update(new_data)
        with open(UNIVERSE_FILE, "w") as f:
            json.dump(current, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save universe data: {e}")

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def index():
    logger.info("UI: render index")
    return render_template("index.html")

@app.get("/api/universe/load")
def load_sectors():
    """
    Returns specific sectors requested via query param ?keys=1:2,1:3
    """
    keys = request.args.get("keys")
    all_data = load_universe_data()

    if not keys:
        # If no keys specified, return everything (useful for debug, risky if huge)
        return jsonify(all_data)

    requested_keys = keys.split(",")
    result = {k: all_data[k] for k in requested_keys if k in all_data}
    return jsonify(result)

@app.post("/api/universe/save")
def save_sector():
    """Receives a dictionary of sectors -> planet data and saves them."""
    data = request.json
    save_universe_data(data)
    return jsonify({"status": "ok"})

# -----------------------------
# Local dev entrypoint
# -----------------------------
if __name__ == "__main__":
    logger.info("Starting dev server at http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)