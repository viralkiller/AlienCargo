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
    "Platform Game": "expert_platformer_2d.json",
    "Racing game": "expert_racing_pseudo3d.json",
    "R-type style space shooter": "expert_shooter_scrolling.json",
    "1v1 beat em up like street fighter": "expert_fighting_versus.json",
    "Final Fight style beat em up": "expert_fighting_brawler.json",
    "Starfox style 3d shooter": "expert_shooter_rail3d.json",
    "Doom style fake 3d shooter": "expert_shooter_fps.json",
    "Chrono Trigger style RPG Game": "expert_rpg_topdown.json",
    "Silent Hill style game": "expert_horror_survival.json",
    "Other": "expert_fallback.json"
}

def load_json_instruction(filename):
    # Load JSON safely.
    path = os.path.join(current_app.root_path, 'static', 'json', filename)
    try:
        current_app.logger.debug(f"Attempting to load JSON instruction from: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        current_app.logger.error(f"Error loading {filename}: {e}")
        return {}

def load_md_example(filename):
    # Load markdown code example safely if it exists.
    path = os.path.join(current_app.root_path, 'static', 'md', filename)
    if os.path.exists(path):
        current_app.logger.debug(f"Code example found for {filename}, loading...")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            current_app.logger.error(f"Error loading {filename}: {e}")
    else:
        current_app.logger.debug(f"No MD code example found at {path}. Proceeding with JSON description only.")
    return ""

@game_bp.route('/')
def index():
    # Log homepage access.
    current_app.logger.info("Route hit: /")

    # Fetch progress tracking data.
    avg_time = progress_tracker.get_average_time()
    current_app.logger.debug(f"Retrieved average generation time: {avg_time}ms")
    return render_template('index.html', avg_time=avg_time)

@game_bp.route('/generate_game', methods=['POST'])
def generate_game():
    current_app.logger.info("Route hit: /generate_game")

    # Validate session fingerprint.
    fingerprint = session.get('fingerprint')
    if not fingerprint:
        current_app.logger.warning("No fingerprint found in session.")
        return jsonify({"error": "Identity missing. Refresh page."}), 400

    data = request.json
    description = data.get('description', '').strip()

    # Log description metrics.
    current_app.logger.info(f"User fingerprint: {fingerprint} | Desc length: {len(description)}")

    if not description:
        current_app.logger.warning("Generation aborted: Missing description.")
        return jsonify({"error": "Description required."}), 400

    # Enforce description limit.
    if len(description) > 2000:
        current_app.logger.warning(f"Generation aborted: Description exceeded length limit ({len(description)} chars).")
        return jsonify({"error": "Description too long (max 2000 chars)."}), 400

    try:
        # Check current balance.
        current_app.logger.debug(f"Verifying credit balance for {fingerprint} via LoginManager...")
        cred_req = requests.post(
            f"{LOGINMANAGER_BASE_URL}/get_credits",
            json={"domain": request.host.split(":")[0], "fingerprint": fingerprint, "email": session.get("email", "")},
            timeout=5
        )
        credits_remaining = cred_req.json().get('credits_remaining', 0)
        current_app.logger.debug(f"Credits remaining: {credits_remaining}")
    except Exception as e:
        current_app.logger.error(f"Credit fetch failed for {fingerprint}: {e}")
        return jsonify({"error": "Failed to verify balance."}), 502

    # Block empty accounts.
    if credits_remaining < 1:
        current_app.logger.warning(f"User {fingerprint} attempted generation with insufficient credits ({credits_remaining}).")
        return jsonify({"error": "Insufficient credits. Please purchase more."}), 403

    try:
        # Load classification data.
        current_app.logger.debug("Loading classifier instructions...")
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
        current_app.logger.debug("Dispatching classification request to AIManager.")
        class_response = requests.post(AI_MANAGER_URL, json=class_payload, timeout=30)
        class_response.raise_for_status()

        class_data = class_response.json()
        class_outputs = class_data.get('outputs', [])
        detected_class = class_outputs[0].strip() if class_outputs else "Other"

        if detected_class not in EXPERT_FILES:
            current_app.logger.warning(f"Invalid class '{detected_class}' returned by AI. Defaulting to 'Other'.")
            detected_class = "Other"

        current_app.logger.info(f"Successfully classified category: {detected_class}")

        # Build generation prompt.
        current_app.logger.debug(f"Loading expert rules and code examples for {detected_class}...")
        expert_json_filename = EXPERT_FILES[detected_class]
        expert_rule_data = load_json_instruction(expert_json_filename)
        expert_rules = expert_rule_data.get('rules', '')

        # Load associated code example if it exists
        expert_md_filename = expert_json_filename.replace('.json', '.md')
        expert_code_example = load_md_example(expert_md_filename)

        general_inst_data = load_json_instruction('general_game_instructions.json')
        base_instructions = general_inst_data.get('instructions', '')

        # Enforce UI constraints explicitly to prevent Z-Index bugs.
        ui_rules = """UI RULES:
        1. DO NOT CREATE A START MENU, START SCREEN, OR 'START GAME' BUTTON.
        2. The game MUST auto-start immediately.
        3. CRITICAL: Do NOT use window.onload or DOMContentLoaded to start the game. Because the code is injected dynamically, those events will fail to fire. You MUST call your main initialization/loop function (e.g., init(), startGame()) directly at the very bottom of your <script> tag."""

        system_instructions = f"{base_instructions}\n\n{ui_rules}\n\nEXPERT RULES FOR [{detected_class}]:\n{expert_rules}"

        if expert_code_example:
            current_app.logger.info(f"Injecting markdown code example for {detected_class} into system instructions.")
            system_instructions += f"\n\nCODE EXAMPLE FOR [{detected_class}]:\n```html\n{expert_code_example}\n```"
        else:
            current_app.logger.debug(f"No markdown code example injected for {detected_class}.")

        payload = {
            "provider": "anthropic",
            "model_key": "claude-opus-4-6",
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 8000
            }
        }

        # Dispatch main generation.
        current_app.logger.debug("Dispatching main game generation request to AIManager.")
        start_time = time.time()

        response = requests.post(AI_MANAGER_URL, json=payload, timeout=120)
        response.raise_for_status()

        manager_data = response.json()
        duration_ms = (time.time() - start_time) * 1000
        current_app.logger.info(f"Generation completed successfully. Duration: {duration_ms:.2f}ms.")

        progress_tracker.save_time(duration_ms)
        outputs = manager_data.get('outputs', [])

        if not outputs:
            current_app.logger.error("Empty AI outputs received from AIManager.")
            raise ValueError("Empty response returned.")

        generated_code = outputs[0]

        # Strip markdown syntax.
        current_app.logger.debug("Cleaning markdown syntax from generated code.")
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)

        # --- AI OUTPUT LOGGING TO DISK ---
        try:
            username = session.get("username")
            # Determine directory based on auth status
            if username:
                # Basic sanitation for username directory
                safe_username = "".join([c for c in username if c.isalnum() or c in ('_', '-')])
                save_dir = os.path.join(current_app.root_path, 'user_data', safe_username)
                current_app.logger.debug(f"Saving output for authenticated user: {safe_username}")
            else:
                save_dir = os.path.join(current_app.root_path, 'temp_data', fingerprint)
                current_app.logger.debug(f"Saving output for guest user fingerprint: {fingerprint}")

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
            current_app.logger.info(f"Successfully logged AI output to disk: {filepath}")
        except Exception as log_err:
            current_app.logger.error(f"Failed to save AI output log to disk: {log_err}")
        # ---------------------------------

        # Deduct credit via microservice.
        cred_payload = {
            "domain": request.host.split(":")[0],
            "fingerprint": fingerprint,
            "email": session.get("email"),
            "credits_used": 1,
            "details": "Game Generation"
        }

        current_app.logger.debug(f"Requesting credit deduction via record_usage for {fingerprint}.")
        cred_resp = requests.post(
            f"{LOGINMANAGER_BASE_URL}/record_usage",
            json=cred_payload, timeout=10
        )

        if cred_resp.status_code == 200:
            # Sync local session.
            session['credits_remaining'] = cred_resp.json().get('credits_remaining', credits_remaining - 1)
            session.modified = True
            current_app.logger.info(f"Credit deducted successfully. Remaining local session balance: {session['credits_remaining']}")
        else:
            current_app.logger.error(f"Credit deduction failed on LoginManager side. Status: {cred_resp.status_code}, Text: {cred_resp.text}")

        current_app.logger.debug("Returning successful JSON response to client.")
        return jsonify({
            "game_html": generated_code.strip(),
            "duration_ms": duration_ms,
            "credits_remaining": session.get('credits_remaining', credits_remaining - 1)
        })

    except (requests.exceptions.RequestException, ValueError) as e:
        current_app.logger.error(f"Generation pipeline failed with request/value error: {e}")
        return jsonify({"error": f"Generation failed: {str(e)}"}), 502
    except Exception as e:
        current_app.logger.error(f"Internal server error during generation: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500