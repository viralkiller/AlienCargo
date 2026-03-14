import re
import requests
import logging
from flask import Flask, render_template, request, jsonify

# Setup basic logging configuration.
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Point to AI microservice.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com/process_request"

@app.route('/')
def index():
    # Render main index template.
    app.logger.info("Route hit: /")
    return render_template('index.html')

@app.route('/generate_game', methods=['POST'])
def generate_game():
    # Parse incoming JSON data.
    data = request.json
    description = data.get('description', '').strip()

    app.logger.info(f"Generating game. Desc length: {len(description)}")

    # Check for missing description.
    if not description:
        app.logger.warning("Missing game description.")
        return jsonify({"error": "Game description required."}), 400

    try:
        # Define game generation instructions.
        system_instructions = (
            "You are an expert game developer. Create a single-page HTML/Phaser and/or ThreeJS game based on the user's description. "
            "Your output must be EXCLUSIVELY valid HTML containing all necessary CSS and JavaScript within it. "
            "CRITICAL REQUIREMENTS: "
            "1. Standard HTML5 <canvas> centered with 800x450 resolution. "
            "2. Arrow keys to move, Enter to start, Space to shoot (if applicable). "
            "3. MUST feature a Game Over state with Restart option. "
            "4. Do NOT load external images, audio, or libraries. "
            "5. STRICTLY FORBIDDEN: Do NOT use localStorage or sessionStorage. "
            "6. Do not include markdown formatting like ```html. "
            "7. CSS MUST include body { margin: 0; padding: 0; overflow: hidden; background-color: #000; } to prevent scrollbars. "
            "8. MOBILE SUPPORT: Implement touch event listeners natively. Map Swipe Up/Down/Left/Right to Arrow Keys. Map Single Tap to Space (shoot). Map Double Tap to Enter (start/restart). "
            "The game must be fully playable and robust."
            "Essential features include a strict 'lives' system, distinct levels or waves, and retro chiptune audio. "
            "Gameplay design relies on simple mechanics—like shooting, jumping, or dodging—that are easy to grasp but fiercely difficult to master. "
            "The primary player incentives are satisfying power-ups, visual progression, and the thrill of surviving chaotic enemy patterns. "
        )

        # Build payload for AIManager.
        payload = {
            "provider": "anthropic",
            "model_key": "claude-sonnet-4-5-20250929",
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 8000
            }
        }

        # Send request to API.
        app.logger.debug("Dispatching request to AI Manager.")
        response = requests.post(AI_MANAGER_URL, json=payload, timeout=120)
        response.raise_for_status()
        manager_data = response.json()

        # Extract code from response.
        outputs = manager_data.get('outputs', [])
        if not outputs:
            app.logger.error("Empty outputs from AI Manager.")
            return jsonify({"error": "AIManager returned empty response."}), 502

        generated_code = outputs[0]

        # Cleanup markdown code tags.
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)

        app.logger.info("Successfully generated and cleaned game.")
        return jsonify({"game_html": generated_code.strip()})

    except requests.exceptions.RequestException as e:
        # Log and handle connection errors.
        app.logger.error(f"Connection error: {e}")
        return jsonify({"error": f"Failed communicating with AIManager: {str(e)}"}), 502
    except Exception as e:
        # Log and handle general errors.
        app.logger.error(f"Internal error: {e}")
        return jsonify({"error": f"Internal formatting error: {str(e)}"}), 500

if __name__ == '__main__':
    # Run the Flask application.
    app.run(debug=True)