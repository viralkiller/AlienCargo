import os
import re
import time
import json
import requests
import progress_tracker
from flask import Blueprint, render_template, request, jsonify, session, current_app

# Initialize game blueprint.
game_bp = Blueprint('game', __name__)

# Define microservice endpoints.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com/process_request"
LOGINMANAGER_BASE_URL = os.environ.get('LOGINMANAGER_BASE_URL', 'https://loginmanager.pythonanywhere.com')

# Define expert rule mappings.
EXPERT_FILES = {
    "Platform Game": "platformer.json",
    "Racing game": "racing.json",
    "R-type style space shooter": "shooter_rtype.json",
    "1v1 beat em up like street fighter": "fighting_streetfighter.json",
    "Final Fight style beat em up": "fighting_finalfight.json",
    "Starfox style 3d shooter": "shooter_starfox.json",
    "Doom style fake 3d shooter": "shooter_doom.json",
    "Chrono Trigger style RPG Game": "rpg_chrono.json",
    "Silent Hill style game": "horror_silenthill.json",
    "Other": "other.json"
}

def load_json_instruction(filename):
    # Load JSON safely.
    path = os.path.join(current_app.root_path, 'static', 'json', filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        current_app.logger.error(f"Error loading {filename}: {e}")
        return {}

@game_bp.route('/')
def index():
    # Log homepage access.
    current_app.logger.info("Route hit: /")
    # Fetch progress tracking data.
    avg_time = progress_tracker.get_average_time()
    return render_template('index.html', avg_time=avg_time)

@game_bp.route('/generate_game', methods=['POST'])
def generate_game():
    # Validate session fingerprint.
    fingerprint = session.get('fingerprint')
    if not fingerprint:
        current_app.logger.warning("No fingerprint found.")
        return jsonify({"error": "Identity missing. Refresh page."}), 400

    data = request.json
    description = data.get('description', '').strip()

    # Log description metrics.
    current_app.logger.info(f"Desc length: {len(description)}")

    if not description:
        current_app.logger.warning("Missing description.")
        return jsonify({"error": "Description required."}), 400

    # Enforce description limit.
    if len(description) > 2000:
        current_app.logger.warning("Description exceeded length limit.")
        return jsonify({"error": "Description too long (max 2000 chars)."}), 400

    try:
        # Check current balance.
        cred_req = requests.post(
            f"{LOGINMANAGER_BASE_URL}/get_credits",
            json={"domain": request.host.split(":")[0], "fingerprint": fingerprint, "email": session.get("email", "")},
            timeout=5
        )
        credits_remaining = cred_req.json().get('credits_remaining', 0)
    except Exception as e:
        current_app.logger.error(f"Credit fetch failed: {e}")
        return jsonify({"error": "Failed to verify balance."}), 502

    # Block empty accounts.
    if credits_remaining < 1:
        current_app.logger.warning(f"User {fingerprint} attempted generation.")
        return jsonify({"error": "Insufficient credits. Please purchase more."}), 403

    try:
        # Load classification data.
        classifier_inst = load_json_instruction('determine_game_type.json')
        categories_str = "\n".join(EXPERT_FILES.keys())
        class_prompt = classifier_inst.get('prompt_template', '').replace('{categories}', categories_str).replace('{description}', description)

        class_payload = {
            "provider": "anthropic",
            "model_key": "claude-sonnet-4-5-20250929",
            "query": class_prompt,
            "parameters": {
                "instructions": classifier_inst.get('system_instruction', 'Output ONLY ONE matching category name.'),
                "max_tokens": 50
            }
        }

        # Dispatch classification.
        current_app.logger.debug("Dispatching classification request.")
        class_response = requests.post(AI_MANAGER_URL, json=class_payload, timeout=30)
        class_response.raise_for_status()
        class_data = class_response.json()
        class_outputs = class_data.get('outputs', [])
        detected_class = class_outputs[0].strip() if class_outputs else "Other"

        if detected_class not in EXPERT_FILES:
            current_app.logger.warning(f"Invalid class '{detected_class}'. Using Other.")
            detected_class = "Other"

        current_app.logger.info(f"Classified category: {detected_class}")

        # Build generation prompt.
        expert_rule_data = load_json_instruction(EXPERT_FILES[detected_class])
        expert_rules = expert_rule_data.get('rules', '')
        general_inst_data = load_json_instruction('general_game_instructions.json')
        base_instructions = general_inst_data.get('instructions', '')

        # Enforce UI constraints explicitly to prevent Z-Index bugs.
        ui_rules = """UI RULES:
        1. DO NOT CREATE A START MENU, START SCREEN, OR 'START GAME' BUTTON.
        2. The game MUST auto-start immediately.
        3. CRITICAL: Do NOT use window.onload or DOMContentLoaded to start the game. Because the code is injected dynamically, those events will fail to fire. You MUST call your main initialization/loop function (e.g., init(), startGame()) directly at the very bottom of your <script> tag."""

        system_instructions = f"{base_instructions}\n\n{ui_rules}\n\nEXPERT RULES FOR [{detected_class}]:\n{expert_rules}"

        payload = {
            "provider": "anthropic",
            "model_key": "claude-sonnet-4-5-20250929",
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 16000
            }
        }

        # Dispatch main generation.
        current_app.logger.debug("Dispatching main generation request.")
        start_time = time.time()
        response = requests.post(AI_MANAGER_URL, json=payload, timeout=120)
        response.raise_for_status()
        manager_data = response.json()

        duration_ms = (time.time() - start_time) * 1000
        current_app.logger.info(f"Generation: {duration_ms:.2f}ms.")
        progress_tracker.save_time(duration_ms)

        outputs = manager_data.get('outputs', [])
        if not outputs:
            current_app.logger.error("Empty AI outputs.")
            raise ValueError("Empty response returned.")

        generated_code = outputs[0]

        # Strip markdown syntax.
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)

        current_app.logger.info("Cleaned generated game.")

        # --- AI OUTPUT LOGGING TO DISK ---
        try:
            username = session.get("username")

            # Determine directory based on auth status
            if username:
                # Basic sanitation for username directory
                safe_username = "".join([c for c in username if c.isalnum() or c in ('_', '-')])
                save_dir = os.path.join(current_app.root_path, 'user_data', safe_username)
            else:
                save_dir = os.path.join(current_app.root_path, 'temp_data', fingerprint)

            os.makedirs(save_dir, exist_ok=True)

            # Generate unique filename with Unix timestamp
            unix_timestamp = int(time.time())
            filename = f"{unix_timestamp}.json"
            filepath = os.path.join(save_dir, filename)

            # Prepare JSON payload
            log_data = {
                "timestamp": unix_timestamp,
                "class": detected_class,
                "prompt": description,
                "code": generated_code.strip()
            }

            # Save the raw output
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=4)

            current_app.logger.info(f"Successfully logged AI output to: {filepath}")
        except Exception as log_err:
            current_app.logger.error(f"Failed to save AI output log: {log_err}")
        # ---------------------------------

        # Deduct credit via microservice.
        cred_payload = {
            "domain": request.host.split(":")[0],
            "fingerprint": fingerprint,
            "email": session.get("email"),
            "credits_used": 1,
            "details": "Game Generation"
        }

        current_app.logger.debug("Deducting via record_usage.")
        cred_resp = requests.post(
            f"{LOGINMANAGER_BASE_URL}/record_usage",
            json=cred_payload, timeout=10
        )

        if cred_resp.status_code == 200:
            # Sync local session.
            session['credits_remaining'] = cred_resp.json().get('credits_remaining', credits_remaining - 1)
            session.modified = True
            current_app.logger.info(f"Credit deducted. Remaining: {session['credits_remaining']}")
        else:
            current_app.logger.error(f"Credit deduction failed: {cred_resp.text}")

        return jsonify({
            "game_html": generated_code.strip(),
            "duration_ms": duration_ms,
            "credits_remaining": session.get('credits_remaining', credits_remaining - 1)
        })

    except (requests.exceptions.RequestException, ValueError) as e:
        current_app.logger.error(f"Generation failed: {e}.")
        return jsonify({"error": f"Generation failed: {str(e)}"}), 502
    except Exception as e:
        current_app.logger.error(f"Internal error: {e}.")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500