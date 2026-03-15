import os
import re
import time
import json
import logging
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory

# Setup basic logging.
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# Point to AI microservice.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com/process_request"

@app.route('/favicon.ico')
def favicon():
    # Log favicon route hit.
    app.logger.info("Route hit: /favicon.ico")
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'icons'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/')
def index():
    # Log index route hit.
    app.logger.info("Route hit: /")
    return render_template('index.html')

@app.route('/generate_game', methods=['POST'])
def generate_game():
    # Parse JSON payload.
    data = request.json
    description = data.get('description', '').strip()

    # Log description length.
    app.logger.info(f"Desc length: {len(description)}")

    # Block empty description.
    if not description:
        app.logger.warning("Missing game description.")
        return jsonify({"error": "Description required."}), 400

    try:
        # Define generation instructions.
        system_instructions = (
            "You are an expert game developer. "
            "Create a single-page HTML/JS game. "
            "CRITICAL REQUIREMENTS: "
            "1. Arrow keys to move if applicable. "
            "2. WASD for second player if applicable. "
            "3. Enter to start game. Space to shoot. "
            "4. MUST feature Restart/Go again button. "
            "5. Keep code around 1000 lines max (~4000 tokens). "
            "6. FOR MOBILE: Generate a virtual gamepad. "
            "7. Split mobile screen: 2 rows, 3 columns. "
            "8. Arrow pad in section 4 (bottom-left). "
            "9. A,B,C buttons in section 6 (bottom-right). "
            "10. Use CSS flex and JS enforcement. "
            "11. Output EXCLUSIVELY valid HTML containing CSS/JS. "
            "12. Do NOT load external images or audio. "
            "13. STRICTLY FORBIDDEN: Do NOT use localStorage. "
            "14. Do not include markdown formatting like ```html."
        )

        # Build AIManager payload.
        payload = {
            "provider": "anthropic",
            "model_key": "claude-sonnet-4-5-20250929",
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 4000
            }
        }

        # Dispatch API request.
        app.logger.debug("Dispatching API request.")
        start_time = time.time()

        response = requests.post(AI_MANAGER_URL, json=payload, timeout=120)
        response.raise_for_status()
        manager_data = response.json()

        # Calculate execution time.
        duration_ms = (time.time() - start_time) * 1000
        app.logger.info(f"Generation: {duration_ms:.2f}ms.")

        # Extract response code.
        outputs = manager_data.get('outputs', [])
        if not outputs:
            app.logger.error("Empty AI outputs.")
            return jsonify({"error": "Empty response returned."}), 502

        generated_code = outputs[0]

        # Clean markdown tags.
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)

        # Return valid payload.
        app.logger.info("Cleaned generated game.")
        return jsonify({
            "game_html": generated_code.strip(),
            "duration_ms": duration_ms
        })

    except requests.exceptions.RequestException as e:
        # Handle connection errors.
        app.logger.error(f"Connection error: {e}")
        return jsonify({"error": f"Connection error: {str(e)}"}), 502
    except Exception as e:
        # Handle general errors.
        app.logger.error(f"Internal error: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

if __name__ == '__main__':
    # Run Flask app.
    app.run(debug=True)