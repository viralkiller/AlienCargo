import re
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
# Point to AI manager microservice.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com/process_request"

@app.route('/')
def index():
    # Render main page template.
    return render_template('index.html')

@app.route('/generate_game', methods=['POST'])
def generate_game():
    data = request.json
    description = data.get('description', '').strip()

    if not description:
        return jsonify({"error": "Game description is required"}), 400

    try:
        # System instructions for game generation.
        system_instructions = (
            "You are an expert game developer. Create a single-page HTML game based on the user's description. "
            "Your output must be EXCLUSIVELY valid HTML containing all necessary CSS and JavaScript within it. "
            "CRITICAL REQUIREMENTS: "
            "1. Standard HTML5 <canvas> centered with 1280x720 resolution. "
            "2. Arrow keys to move, Enter to start, Space to shoot. "
            "3. MUST feature a Game Over state with Restart option. "
            "4. Do NOT load external images, audio, or libraries. "
            "5. STRICTLY FORBIDDEN: Do NOT use localStorage or sessionStorage. "
            "6. Do not include markdown formatting like ```html. "
            "The game must be fully playable and robust."
        )

        # Payload for AIManager endpoint.
        payload = {
            "provider": "anthropic",
            "model_key": "claude-sonnet-4-5-20250929",
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 8000
            }
        }

        # Send request to AI manager.
        response = requests.post(AI_MANAGER_URL, json=payload, timeout=120)
        response.raise_for_status()
        manager_data = response.json()

        # Extract code from response.
        outputs = manager_data.get('outputs', [])
        if not outputs:
            return jsonify({"error": "AIManager returned empty response."}), 502

        generated_code = outputs[0]

        # Cleanup markdown tags just in case.
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)

        return jsonify({"game_html": generated_code.strip()})

    except requests.exceptions.RequestException as e:
        # Handle connection errors.
        return jsonify({"error": f"Failed communicating with AIManager: {str(e)}"}), 502
    except Exception as e:
        # Handle general errors.
        return jsonify({"error": f"Internal formatting error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)