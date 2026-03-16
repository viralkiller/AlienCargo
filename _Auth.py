# _Auth.py
import os
import re
import jwt  # Decode token securely.
import time # Required for time checking.
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app, make_response, jsonify
)
import requests
from _Shared import LOGINMANAGER_MICROSERVICE_URL
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, ValidationError

class SimpleEmail:
    # Basic email validator.
    def __init__(self, message=None):
        if not message:
            message = 'Invalid email address.'
        self.message = message
        self.regex = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

    def __call__(self, form, field):
        email = field.data or ""
        if not self.regex.match(email):
            raise ValidationError(self.message)

class RegistrationForm(FlaskForm):
    # Registration form setup.
    email = StringField('Email', validators=[DataRequired(), SimpleEmail()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    # Login form setup.
    email = StringField('Email', validators=[DataRequired(), SimpleEmail()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

auth_bp = Blueprint('auth', __name__)

@auth_bp.before_app_request
def check_global_token_expiry():
    # Purge expired user sessions.
    token = session.get('token')
    if token:
        try:
            # Decode token securely.
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get('exp')
            if exp and time.time() > exp:
                current_app.logger.info("[Auth] Token expired globally. Purging.")
                session.clear()
        except Exception:
            current_app.logger.warning("[Auth] Invalid token. Purging.")
            session.clear()

@auth_bp.route('/heartbeat', methods=['GET'])
def heartbeat():
    # Validate current session.
    token = session.get('token')
    if not token or not session.get('email'):
        # Prevent infinite loop.
        session.clear()
        current_app.logger.debug("[Auth] Heartbeat: Missing token or email. Cleared.")
        return jsonify({"status": "expired"}), 401
    try:
        # Decode token securely.
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get('exp')
        if exp and time.time() > exp:
            current_app.logger.info("[Auth] Token expired. Clearing session.")
            session.clear()
            response = jsonify({"status": "expired"})
            status_code = 401
        else:
            response = jsonify({"status": "active", "user": session.get('username')})
            status_code = 200
    except jwt.DecodeError:
        current_app.logger.warning("[Auth] Invalid token format. Clearing.")
        session.clear()
        response = jsonify({"status": "invalid"})
        status_code = 401
    except Exception as e:
        current_app.logger.error(f"[Auth] Error checking token: {e}")
        response = jsonify({"status": "active", "user": session.get('username')})
        status_code = 200

    # Prevent response caching.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response, status_code

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Redirect to registration page.
    current_app.logger.debug("Entering /register route.")
    current_domain = request.host.split(':')[0]
    maintenance_mode = os.getenv("MAINTENANCE_MODE", "False").lower() in ("true", "1", "yes")

    if maintenance_mode:
        current_app.logger.info("[Auth] Maintenance mode active.")
        return render_template("maintenance.html")

    redirect_uri = url_for('auth.handle_register', _external=True)
    lm_url = f"{LOGINMANAGER_MICROSERVICE_URL}/register-page"
    register_url = f"{lm_url}?redirect_uri={redirect_uri}&domain={current_domain}"

    current_app.logger.info(f"[Auth] Redirecting to: {register_url}")
    return redirect(register_url)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect to login page.
    current_app.logger.debug("Entering /login route.")
    current_domain = request.host.split(':')[0]
    redirect_uri = url_for('auth.handle_login', _external=True)
    lm_login_url = (
        f"{LOGINMANAGER_MICROSERVICE_URL}/login-page"
        f"?redirect_uri={redirect_uri}&domain={current_domain}"
    )
    current_app.logger.info(f"[Auth] Redirecting to: {lm_login_url}")
    return redirect(lm_login_url)

@auth_bp.route('/handle_login', methods=['GET'])
def handle_login():
    # Handle authentication callback.
    current_app.logger.debug("Entering /handle_login route.")
    token = request.args.get('token')
    if not token:
        current_app.logger.error("Authentication failed: No token received.")
        flash("Authentication failed: No token received.", "danger")
        return redirect(url_for('index'))
    try:
        # Verify user token.
        current_app.logger.debug("Verifying token with LoginManager.")
        resp = requests.get(
            f"{LOGINMANAGER_MICROSERVICE_URL}/protected",
            headers={"Authorization": token},
            timeout=10,
        )
        if resp.status_code != 200:
            current_app.logger.error("Authentication failed: Invalid or expired token.")
            flash("Authentication failed: Invalid or expired token.", "danger")
            return redirect(url_for('index'))

        user_data = resp.json()
        username = user_data.get("username")
        if not username:
            current_app.logger.error("Failed to retrieve username from user data.")
            flash("Failed to retrieve user data.", "danger")
            return redirect(url_for('index'))

        # Fetch actual credit balance.
        credits_rem = user_data.get("credits_remaining", 0)
        try:
            current_app.logger.debug("Fetching up-to-date credits.")
            payload = {
                "domain": request.host.split(":")[0],
                "email": user_data.get("email"),
                "fingerprint": session.get("fingerprint", "backend_auth")
            }
            c_resp = requests.post(
                f"{LOGINMANAGER_MICROSERVICE_URL}/get_credits",
                json=payload,
                timeout=5
            )
            if c_resp.status_code == 200:
                credits_rem = c_resp.json().get("credits_remaining", credits_rem)
        except Exception as e:
            current_app.logger.error(f"[Auth] Credit fetch failed: {e}")

        # Update user session data.
        session.update(
            token=token,
            user_id=username,
            username=username,
            email=user_data.get("email"),
            last_login=user_data.get("last_login"),
            domain=request.host.split(":")[0],
            credits_remaining=credits_rem,
            free_credits=user_data.get("free_credits", 0),
            purchased_credits=user_data.get("purchased_credits", 0),
        )
        session.permanent = True
        current_app.logger.info(f"User {username} logged in successfully.")
        flash("Login successful!", "success")
        return redirect(url_for('index'))

    except requests.RequestException as e:
        current_app.logger.exception(f"[Auth] Verification failed: {e}")
        flash("Could not verify login. Please try again.", "danger")
        return redirect(url_for('index'))

@auth_bp.route('/handle_register', methods=['GET'])
def handle_register():
    # Handle registration callback.
    current_app.logger.debug("Entering /handle_register route.")
    success = request.args.get("success", "false").lower() == "true"
    message = request.args.get("message", "")

    if success:
        current_app.logger.info("Registration successful callback hit.")
        flash(message or "Registration successful! Check email.", "success")
        return redirect(url_for('auth.login'))
    else:
        current_app.logger.warning("Registration failed callback hit.")
        flash(message or "Registration failed.", "danger")
        return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    # Logout and clear session.
    current_app.logger.debug("Entering /logout route.")
    keys_to_clear = [
        "token", "user_id", "username", "email",
        "last_login", "credits_remaining",
        "free_credits", "purchased_credits",
        "current_sid", "fingerprint", "extras",
        "pending_transactions"
    ]
    for key in keys_to_clear:
        session.pop(key, None)

    current_app.logger.info("Session keys cleared. User logged out.")
    flash("You have been successfully logged out.", "success")
    resp = make_response(redirect(url_for('index')))
    resp.delete_cookie("progress_done", path="/")
    return resp