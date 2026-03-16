import os
import re
import time
import json
import logging
import requests
import progress_tracker
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash

# Import auth and billing blueprints.
from _Auth import auth_bp
from _Billing_Routes import billing_bp

# Setup basic logging.
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SEC', 'fallback_secret_key_for_dev')

# Register app blueprints.
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(billing_bp, url_prefix='/billing')

# Set microservice URLs.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com/process_request"
LOGINMANAGER_UPDATE_CREDITS_URL = os.environ.get('LOGINMANAGER_UPDATE_CREDITS_URL', 'https://loginmanager.pythonanywhere.com/update-user-credits')

# Map categories to JSONs.
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
    # Load instruction JSONs from static.
    path = os.path.join(app.root_path, 'static', 'json', filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        app.logger.error(f"Error loading {filename}: {e}")
        return {}

@app.route('/favicon.ico')
def favicon():
    # Log favicon hit.
    app.logger.info("Route hit: /favicon.ico")
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'icons'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/')
def index():
    # Log index hit.
    app.logger.info("Route hit: /")
    return render_template('index.html')

@app.route('/generate_game', methods=['POST'])
def generate_game():
    # Verify fingerprint identity.
    fingerprint = session.get('fingerprint')
    if not fingerprint:
        app.logger.warning("No fingerprint found.")
        return jsonify({"error": "Identity missing. Refresh page."}), 400

    try:
        # Check live balance.
        cred_req = requests.post(
            f"{LOGINMANAGER_UPDATE_CREDITS_URL.replace('/update-user-credits', '')}/get_credits",
            json={"domain": request.host.split(":")[0], "fingerprint": fingerprint, "email": session.get("email", "")},
            timeout=5
        )
        credits_remaining = cred_req.json().get('credits_remaining', 0)
    except Exception as e:
        app.logger.error(f"Credit fetch failed: {e}")
        return jsonify({"error": "Failed to verify balance."}), 502

    # Block generation on zero credits.
    if credits_remaining < 1:
        app.logger.warning(f"User {fingerprint} attempted generation.")
        return jsonify({"error": "Insufficient credits. Please purchase more."}), 403

    data = request.json
    description = data.get('description', '').strip()
    app.logger.info(f"Desc length: {len(description)}")

    if not description:
        app.logger.warning("Missing description.")
        return jsonify({"error": "Description required."}), 400

    try:
        # Deduct credit via LoginManager.
        cred_payload = {
            "domain": request.host.split(":")[0],
            "fingerprint": fingerprint,
            "email": session.get("email"),
            "credits_used": 1,
            "details": "Game Generation"
        }
        app.logger.debug("Deducting via record_usage.")
        cred_resp = requests.post(
            f"{LOGINMANAGER_UPDATE_CREDITS_URL.replace('/update-user-credits', '')}/record_usage",
            json=cred_payload, timeout=10
        )

        if cred_resp.status_code == 200:
            session['credits_remaining'] = credits_remaining - 1
            session.modified = True
            app.logger.info(f"Credit deducted. Remaining: {session['credits_remaining']}")
        else:
            app.logger.error(f"Credit deduction failed: {cred_resp.text}")
            return jsonify({"error": "Failed processing credits."}), 500

        # Classify the game type.
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

        app.logger.debug("Dispatching classification request.")
        class_response = requests.post(AI_MANAGER_URL, json=class_payload, timeout=30)
        class_response.raise_for_status()

        class_data = class_response.json()
        class_outputs = class_data.get('outputs', [])
        detected_class = class_outputs[0].strip() if class_outputs else "Other"

        if detected_class not in EXPERT_FILES:
            app.logger.warning(f"Invalid class '{detected_class}'. Using Other.")
            detected_class = "Other"

        app.logger.info(f"Classified category: {detected_class}")

        # Build final generation prompt.
        expert_rule_data = load_json_instruction(EXPERT_FILES[detected_class])
        expert_rules = expert_rule_data.get('rules', '')
        general_inst_data = load_json_instruction('general_game_instructions.json')
        base_instructions = general_inst_data.get('instructions', '')
        system_instructions = f"{base_instructions}\n\nEXPERT RULES FOR [{detected_class}]:\n{expert_rules}"

        payload = {
            "provider": "anthropic",
            "model_key": "claude-sonnet-4-5-20250929",
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 4000
            }
        }

        app.logger.debug("Dispatching main generation request.")
        start_time = time.time()

        response = requests.post(AI_MANAGER_URL, json=payload, timeout=120)
        response.raise_for_status()

        manager_data = response.json()
        duration_ms = (time.time() - start_time) * 1000

        app.logger.info(f"Generation: {duration_ms:.2f}ms.")
        progress_tracker.save_time(duration_ms)

        outputs = manager_data.get('outputs', [])
        if not outputs:
            app.logger.error("Empty AI outputs.")
            raise ValueError("Empty response returned.")

        generated_code = outputs[0]

        # Strip markdown syntax.
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)

        app.logger.info("Cleaned generated game.")

        return jsonify({
            "game_html": generated_code.strip(),
            "duration_ms": duration_ms,
            "credits_remaining": session['credits_remaining']
        })

    except (requests.exceptions.RequestException, ValueError) as e:
        app.logger.error(f"Generation failed: {e}. Rollback initiated.")
        try:
            refund_payload = {
                "domain": request.host.split(":")[0],
                "fingerprint": fingerprint,
                "email": session.get("email"),
                "credits_used": -1,
                "details": "Generation Failed Refund"
            }
            requests.post(
                f"{LOGINMANAGER_UPDATE_CREDITS_URL.replace('/update-user-credits', '')}/record_usage",
                json=refund_payload, timeout=10
            )
            session['credits_remaining'] += 1
            session.modified = True
            app.logger.info("Credit successfully refunded.")
        except Exception as rollback_err:
            app.logger.error(f"Credit rollback failed: {rollback_err}")
        return jsonify({"error": f"Generation failed: {str(e)}"}), 502

    except Exception as e:
        app.logger.error(f"Internal error: {e}. Rollback initiated.")
        try:
            refund_payload = {
                "domain": request.host.split(":")[0],
                "fingerprint": fingerprint,
                "email": session.get("email"),
                "credits_used": -1,
                "details": "Internal Error Refund"
            }
            requests.post(
                f"{LOGINMANAGER_UPDATE_CREDITS_URL.replace('/update-user-credits', '')}/record_usage",
                json=refund_payload, timeout=10
            )
            session['credits_remaining'] += 1
            session.modified = True
            app.logger.info("Credit successfully refunded.")
        except Exception as rollback_err:
            app.logger.error(f"Credit rollback failed: {rollback_err}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

if __name__ == '__main__':
    # Run Flask app.
    app.run(debug=True)