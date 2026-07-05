import os
import re
import time
import json
import requests
import progress_tracker
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, current_app, redirect, url_for
# Initialize game blueprint.
game_bp = Blueprint('game', __name__)
# Define microservice endpoints.
AI_MANAGER_URL = "https://aimanager.pythonanywhere.com/process_request"
LOGINMANAGER_BASE_URL = os.environ.get('LOGINMANAGER_BASE_URL', 'https://loginmanager.pythonanywhere.com')
# Model keys. MUST match keys registered in AIManager's
# static/json/model_registry.json (currently: claude-sonnet-5, claude-fable-5).
# An unregistered key makes AIManager 500 on every call.
# FAST: cheap/quick utility calls (classification, sprite assets).
# GAME: the main game code generation (Fable 5 - highest quality, higher cost).
AI_MODEL_KEY_FAST = os.environ.get('AIMANAGER_MODEL_KEY_FAST', 'claude-sonnet-5')
AI_MODEL_KEY_GAME = os.environ.get('AIMANAGER_MODEL_KEY_GAME', 'claude-fable-5')
# Timeouts (seconds) for each AIManager call. These are MAXED OUT against
# PythonAnywhere's HARD 5-minute (300s) per-request kill ("harakiri"), which
# cannot be raised or disabled. The three calls run sequentially inside one
# /generate_game request, so their SUM + LoginManager calls (~15s) + overhead
# must stay under 300s: 15 + 45 + 220 + 15 = 295. Do NOT raise these further;
# past this the platform kills the worker mid-request instead of returning a
# clean error (and AIManager's own 300s harakiri caps the upstream call anyway).
AI_CLASSIFY_TIMEOUT = int(os.environ.get('AI_CLASSIFY_TIMEOUT', 15))
AI_ASSET_TIMEOUT = int(os.environ.get('AI_ASSET_TIMEOUT', 45))
AI_GAME_TIMEOUT = int(os.environ.get('AI_GAME_TIMEOUT', 220))
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
# -----------------------------------------------------------------------------
# Sprite asset constants and validation
# -----------------------------------------------------------------------------
SPRITE_SIZE = 16
SPRITE_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,40}$')
HEX_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
FUNC_COLOR_RE = re.compile(r'^(?:rgb|rgba|hsl|hsla)\([0-9,.%\s]+\)$')


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


def extract_ai_text(outputs, default=""):
    """Safely extracts text from AIManager outputs (string or Anthropic dict block)."""
    if not outputs:
        return default
    raw = outputs[0]
    if isinstance(raw, dict):
        return raw.get('text', raw.get('content', default))
    return str(raw)


# -----------------------------------------------------------------------------
# Sprite asset pipeline
# -----------------------------------------------------------------------------
def _clean_color(value):
    """Returns a safe CSS color string or None (transparent) for anything invalid."""
    if value is None or not isinstance(value, str):
        return None
    v = value.strip()
    if v == '' or v.lower() in ('transparent', 'none', 'null'):
        return None
    if len(v) > 32:
        return None
    if HEX_COLOR_RE.match(v) or FUNC_COLOR_RE.match(v):
        return v
    return None


def validate_and_normalize_sprites(raw):
    """
    Validates AI-generated sprite JSON. Bad palettes/rows are normalized where
    possible; unsalvageable sprites are dropped. Returns a clean dict.
    """
    clean = {}
    if not isinstance(raw, dict):
        current_app.logger.warning("[Sprites] Root of asset payload is not a dict. Discarding all.")
        return clean
    for name, sprite in raw.items():
        # Validate sprite name.
        if not isinstance(name, str) or not SPRITE_NAME_RE.match(name):
            current_app.logger.warning(f"[Sprites] Dropping sprite with invalid name: {str(name)[:50]}")
            continue
        if not isinstance(sprite, dict):
            current_app.logger.warning(f"[Sprites] Dropping '{name}': entry is not an object.")
            continue
        palette_raw = sprite.get('palette')
        grid_raw = sprite.get('grid')
        if not isinstance(palette_raw, dict) or not isinstance(grid_raw, list):
            current_app.logger.warning(f"[Sprites] Dropping '{name}': missing palette or grid.")
            continue
        # Normalize palette: single-char keys, safe color values, '.' forced transparent.
        palette = {}
        for key, color in palette_raw.items():
            if isinstance(key, str) and len(key) == 1:
                palette[key] = _clean_color(color)
        palette['.'] = None
        # Normalize grid: exactly 16 rows of exactly 16 chars, unknown chars -> transparent.
        grid = []
        painted_pixels = 0
        for row in grid_raw[:SPRITE_SIZE]:
            row = row if isinstance(row, str) else ''
            row = row[:SPRITE_SIZE].ljust(SPRITE_SIZE, '.')
            fixed_row = []
            for ch in row:
                if ch in palette:
                    fixed_row.append(ch)
                    if palette[ch] is not None:
                        painted_pixels += 1
                else:
                    fixed_row.append('.')
            grid.append(''.join(fixed_row))
        while len(grid) < SPRITE_SIZE:
            grid.append('.' * SPRITE_SIZE)
        # Drop fully-transparent (useless) sprites.
        if painted_pixels == 0:
            current_app.logger.warning(f"[Sprites] Dropping '{name}': grid is entirely transparent.")
            continue
        clean[name] = {'palette': palette, 'grid': grid}
    current_app.logger.info(f"[Sprites] Validation complete. {len(clean)} sprite(s) accepted.")
    return clean


def generate_sprite_assets(description, detected_class):
    """
    Dedicated asset pass: asks the AI for a full 16x16 sprite sheet for the
    detected category, validates it, and returns (sprites_dict, sprite_names).
    Returns ({}, []) on any failure so the game pipeline can proceed without art.
    """
    current_app.logger.info(f"[Sprites] Starting asset generation pass for category '{detected_class}'.")
    asset_cfg = load_json_instruction('generate_game_assets.json')
    if not asset_cfg:
        current_app.logger.warning("[Sprites] Asset config missing. Skipping asset pass.")
        return {}, []
    # Resolve the sprite manifest for this category.
    manifests = asset_cfg.get('manifests', {})
    manifest = manifests.get(detected_class) or asset_cfg.get('default_manifest', [])
    if not manifest:
        current_app.logger.warning("[Sprites] No manifest found. Skipping asset pass.")
        return {}, []
    current_app.logger.debug(f"[Sprites] Manifest resolved ({len(manifest)} sprites): {manifest}")
    # Build the asset prompt.
    prompt = (
        asset_cfg.get('prompt_template', '')
        .replace('{description}', description)
        .replace('{category}', detected_class)
        .replace('{sprite_list}', "\n".join(manifest))
    )
    payload = {
        "provider": "anthropic",
        "model_key": AI_MODEL_KEY_FAST,
        "query": prompt,
        "parameters": {
            "instructions": asset_cfg.get('system_instruction', 'Output ONLY a valid JSON object of sprites.'),
            "max_tokens": asset_cfg.get('max_tokens', 8000)
        }
    }
    # Dispatch asset generation.
    current_app.logger.debug("[Sprites] Dispatching asset generation request to AIManager.")
    start_time = time.time()
    response = requests.post(AI_MANAGER_URL, json=payload, timeout=AI_ASSET_TIMEOUT)
    response.raise_for_status()
    duration_ms = (time.time() - start_time) * 1000
    current_app.logger.info(f"[Sprites] Asset AI call completed in {duration_ms:.2f}ms.")
    raw_text = extract_ai_text(response.json().get('outputs', []))
    if not raw_text.strip():
        current_app.logger.warning("[Sprites] Empty response from asset pass.")
        return {}, []
    # Strip markdown fences and isolate the JSON object.
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw_text.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        current_app.logger.warning("[Sprites] No JSON object found in asset response.")
        return {}, []
    try:
        raw_sprites = json.loads(cleaned[first_brace:last_brace + 1])
    except json.JSONDecodeError as e:
        current_app.logger.warning(f"[Sprites] Failed to parse asset JSON: {e}")
        return {}, []
    sprites = validate_and_normalize_sprites(raw_sprites)
    return sprites, list(sprites.keys())


def build_sprite_injection(sprites):
    """Builds the <script> block defining window.GAME_SPRITES and window.decodeSprite."""
    # Escape '</' so palette strings can never break out of the script context.
    payload = json.dumps(sprites, separators=(',', ':')).replace('</', '<\\/')
    return (
        "<script>\n"
        "/* Injected by Alien Cargo asset pipeline. */\n"
        "window.GAME_SPRITES = " + payload + ";\n"
        "window.decodeSprite = function(name, scale) {\n"
        "    scale = scale || 4;\n"
        "    var def = window.GAME_SPRITES[name];\n"
        "    if (!def || !def.grid || !def.palette) {\n"
        "        console.warn('[Sprites] Unknown sprite requested: ' + name);\n"
        "        return null;\n"
        "    }\n"
        "    var c = document.createElement('canvas');\n"
        "    c.width = 16 * scale;\n"
        "    c.height = 16 * scale;\n"
        "    var ctx = c.getContext('2d');\n"
        "    ctx.imageSmoothingEnabled = false;\n"
        "    for (var y = 0; y < def.grid.length; y++) {\n"
        "        var row = def.grid[y];\n"
        "        for (var x = 0; x < row.length; x++) {\n"
        "            var col = def.palette[row[x]];\n"
        "            if (col) {\n"
        "                ctx.fillStyle = col;\n"
        "                ctx.fillRect(x * scale, y * scale, scale, scale);\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    return c;\n"
        "};\n"
        "console.log('[Sprites] Injected ' + Object.keys(window.GAME_SPRITES).length + ' sprite(s).');\n"
        "</script>"
    )


def inject_sprites_into_html(game_html, sprite_script):
    """
    Injects the sprite script so it runs BEFORE any game code. Prefers the top
    of <body>, falls back to end of <head>, then to plain prepending.
    """
    body_match = re.search(r'<body[^>]*>', game_html, re.IGNORECASE)
    if body_match:
        idx = body_match.end()
        current_app.logger.debug("[Sprites] Injecting sprite script after <body> tag.")
        return game_html[:idx] + "\n" + sprite_script + "\n" + game_html[idx:]
    head_match = re.search(r'</head>', game_html, re.IGNORECASE)
    if head_match:
        idx = head_match.start()
        current_app.logger.debug("[Sprites] Injecting sprite script before </head> tag.")
        return game_html[:idx] + "\n" + sprite_script + "\n" + game_html[idx:]
    current_app.logger.debug("[Sprites] No body/head tags found. Prepending sprite script.")
    return sprite_script + "\n" + game_html


@game_bp.route('/')
def index():
    # Log homepage access.
    current_app.logger.info("Route hit: /")
    # Fetch progress tracking data.
    avg_time = progress_tracker.get_average_time()
    current_app.logger.debug(f"Retrieved average generation time: {avg_time}ms")
    # Auto-load the most recently generated game
    username = session.get("username")
    fingerprint = session.get("fingerprint")
    initial_game = ""
    if username:
        safe_username = "".join([c for c in username if c.isalnum() or c in ('_', '-')])
        target_dir = os.path.join(current_app.root_path, 'user_data', safe_username)
    elif fingerprint:
        target_dir = os.path.join(current_app.root_path, 'temp_data', fingerprint)
    else:
        target_dir = None
    if target_dir and os.path.exists(target_dir):
        files = [f for f in os.listdir(target_dir) if f.endswith('.json')]
        if files:
            # Sort by filename (Unix timestamp) descending to get the newest
            files.sort(reverse=True)
            latest_file = os.path.join(target_dir, files[0])
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    initial_game = data.get('code', '')
            except Exception as e:
                current_app.logger.error(f"Failed to load initial game: {e}")
    return render_template('index.html', avg_time=avg_time, initial_game_html=initial_game)


@game_bp.route('/history')
def history():
    current_app.logger.info("Route hit: /history")
    username = session.get("username")
    if not username:
        return redirect(url_for('auth.login'))
    safe_username = "".join([c for c in username if c.isalnum() or c in ('_', '-')])
    target_dir = os.path.join(current_app.root_path, 'user_data', safe_username)
    games = []
    if os.path.exists(target_dir):
        files = [f for f in os.listdir(target_dir) if f.endswith('.json')]
        files.sort(reverse=True)
        for file in files:
            filepath = os.path.join(target_dir, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Fallback to filename if timestamp is missing
                    ts = data.get('timestamp', int(file.split('.')[0]))
                    dt = datetime.fromtimestamp(ts)
                    games.append({
                        'filename': file,
                        'date': dt.strftime('%b %d, %Y - %I:%M %p'),
                        'class': data.get('class', 'Unknown Category'),
                        'prompt': data.get('prompt', 'No description provided')[:80] + '...'
                    })
            except Exception as e:
                current_app.logger.error(f"Error reading history file {file}: {e}")
    return render_template('history.html', games=games)


@game_bp.route('/history/<filename>')
def view_past_game(filename):
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    safe_username = "".join([c for c in username if c.isalnum() or c in ('_', '-')])
    filepath = os.path.join(current_app.root_path, 'user_data', safe_username, filename)
    if not os.path.exists(filepath):
        return "Game not found", 404
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            avg_time = progress_tracker.get_average_time()
            return render_template('index.html', avg_time=avg_time, initial_game_html=data.get('code', ''))
    except Exception as e:
        current_app.logger.error(f"Error loading past game: {e}")
        return "Error loading game", 500


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
        # [FIX] Graceful fallback to local session balance if the microservice is overloaded/rate-limited
        if cred_req.status_code == 200:
            credits_remaining = cred_req.json().get('credits_remaining', 0)
            session['credits_remaining'] = credits_remaining
            session.modified = True
        else:
            current_app.logger.warning(f"LoginManager returned {cred_req.status_code}. Falling back to local session balance.")
            credits_remaining = session.get('credits_remaining', 0)
        current_app.logger.debug(f"Credits remaining: {credits_remaining}")
    except Exception as e:
        current_app.logger.error(f"Credit fetch failed for {fingerprint}: {e}. Falling back to local session balance.")
        credits_remaining = session.get('credits_remaining', 0)
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
            "model_key": AI_MODEL_KEY_FAST,
            "query": class_prompt,
            "parameters": {
                "instructions": classifier_inst.get('system_instruction', 'Output ONLY ONE matching category name.'),
                "max_tokens": 50
            }
        }
        # Dispatch classification.
        current_app.logger.debug("Dispatching classification request to AIManager.")
        class_response = requests.post(AI_MANAGER_URL, json=class_payload, timeout=AI_CLASSIFY_TIMEOUT)
        class_response.raise_for_status()
        class_data = class_response.json()
        detected_class = extract_ai_text(class_data.get('outputs', []), default="Other").strip()
        if detected_class not in EXPERT_FILES:
            current_app.logger.warning(f"Invalid class '{detected_class}' returned by AI. Defaulting to 'Other'.")
            detected_class = "Other"
        current_app.logger.info(f"Successfully classified category: {detected_class}")
        # --- SPRITE ASSET GENERATION PASS ---
        # Runs between classification and main generation. Any failure here
        # degrades gracefully: the game is simply generated without sprites.
        sprites, sprite_names = {}, []
        try:
            sprites, sprite_names = generate_sprite_assets(description, detected_class)
        except Exception as asset_err:
            current_app.logger.error(f"[Sprites] Asset pass failed, continuing without sprites: {asset_err}")
        # ------------------------------------
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
        # Advertise the injected sprites to the game generator.
        if sprite_names:
            sprite_rules = f"""SPRITE ASSETS (PRE-INJECTED):
Custom 16x16 pixel-art sprites for this exact game are ALREADY injected into the page as window.GAME_SPRITES, with a decoder window.decodeSprite(name, scale) that returns an HTMLCanvasElement.
AVAILABLE SPRITES: {', '.join(sprite_names)}
1. You MUST use these sprites for the corresponding game entities. Do NOT draw placeholder rectangles/circles for any entity that has a sprite listed above.
2. Decode each sprite ONCE at startup and cache the canvases. NEVER call decodeSprite inside the game loop.
3. Raw canvas: ctx.drawImage(cachedCanvas, x, y) with ctx.imageSmoothingEnabled = false.
4. Phaser: this.textures.addCanvas('name', window.decodeSprite('name', 4)).
5. ThreeJS: new THREE.CanvasTexture(window.decodeSprite('name', 4)) with magFilter = THREE.NearestFilter on billboard planes.
6. Do NOT define or overwrite window.GAME_SPRITES or window.decodeSprite. Do NOT include any sprite pixel data in your own code.
7. Tiles (names starting with 'tile_') fill the full 16x16 and can be repeated seamlessly."""
            system_instructions += f"\n\n{sprite_rules}"
            current_app.logger.info(f"[Sprites] Advertising {len(sprite_names)} sprites to the game generator.")
        if expert_code_example:
            current_app.logger.info(f"Injecting markdown code example for {detected_class} into system instructions.")
            system_instructions += f"\n\nCODE EXAMPLE FOR [{detected_class}]:\n```html\n{expert_code_example}\n```"
        else:
            current_app.logger.debug(f"No markdown code example injected for {detected_class}.")
        payload = {
            "provider": "anthropic",
            "model_key": AI_MODEL_KEY_GAME,
            "query": description,
            "parameters": {
                "instructions": system_instructions,
                "max_tokens": 16000
            }
        }
        # Dispatch main generation.
        current_app.logger.debug("Dispatching main game generation request to AIManager.")
        start_time = time.time()
        response = requests.post(AI_MANAGER_URL, json=payload, timeout=AI_GAME_TIMEOUT)
        response.raise_for_status()
        manager_data = response.json()
        duration_ms = (time.time() - start_time) * 1000
        current_app.logger.info(f"Generation completed successfully. Duration: {duration_ms:.2f}ms.")
        progress_tracker.save_time(duration_ms)
        outputs = manager_data.get('outputs', [])
        if not outputs:
            current_app.logger.error("Empty AI outputs received from AIManager.")
            raise ValueError("Empty response returned.")
        generated_code = extract_ai_text(outputs)
        # Strip markdown syntax.
        current_app.logger.debug("Cleaning markdown syntax from generated code.")
        generated_code = re.sub(r'^```html\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)
        generated_code = generated_code.strip()
        # --- SPRITE INJECTION ---
        # Prepend the sprite data + decoder so it exists before any game script
        # runs. Done BEFORE disk logging so history replays include the art.
        if sprites:
            try:
                sprite_script = build_sprite_injection(sprites)
                generated_code = inject_sprites_into_html(generated_code, sprite_script)
                current_app.logger.info(f"[Sprites] Injected {len(sprites)} sprite(s) into generated HTML.")
            except Exception as inject_err:
                current_app.logger.error(f"[Sprites] Injection failed, shipping game without sprites: {inject_err}")
        # ------------------------
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
                "sprites": sprite_names,
                "code": generated_code
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
            "game_html": generated_code,
            "duration_ms": duration_ms,
            "credits_remaining": session.get('credits_remaining', credits_remaining - 1)
        })
    except (requests.exceptions.RequestException, ValueError) as e:
        current_app.logger.error(f"Generation pipeline failed with request/value error: {e}")
        return jsonify({"error": f"Generation failed: {str(e)}"}), 502
    except Exception as e:
        current_app.logger.error(f"Internal server error during generation: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500
