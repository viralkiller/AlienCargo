# flask_app.py
import logging
from pathlib import Path

from flask import Flask, render_template

# -----------------------------
# Config
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

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
# Routes
# -----------------------------
@app.get("/")
def index():
    logger.info("UI: render index")
    return render_template("index.html")

# -----------------------------
# Local dev entrypoint
# -----------------------------
if __name__ == "__main__":
    logger.info("Starting dev server at http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
