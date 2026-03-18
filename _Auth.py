# _Auth.py
import os
import re
import jwt
import time
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
    """Basic email format validator."""
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
    """WTForm for user registration."""
    email = StringField('Email', validators=[DataRequired(), SimpleEmail()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    """WTForm for user login."""
    email = StringField('Email', validators=[DataRequired(), SimpleEmail()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/heartbeat', methods=['GET'])
def heartbeat():
    """Client polling endpoint for session status."""
    token = session.get('token')

    # Fail if missing token.
    if not token or not session.get('email'):
        return jsonify({"status": "expired"}), 401

    try:
        # Decode token safely.
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get('exp')

        # Check token expiration.
        if exp and time.time() > exp:
            current_app.logger.info(f"[Heartbeat] Token expired. Clearing session.")
            session.clear()
            response = jsonify({"status": "expired"})
            status_code = 401
        else:
            response = jsonify({"status": "active", "user": session.get('username')})
            status_code = 200

    except jwt.DecodeError:
        current_app.logger.warning("[Heartbeat] Invalid token. Clearing session.")
        session.clear()
        response = jsonify({"status": "invalid"})
        status_code = 401
    except Exception as e:
        current_app.logger.error(f"[Heartbeat] Token error: {e}")
        response = jsonify({"status": "active", "user": session.get('username')})
        status_code = 200

    # Prevent caching responses.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response, status_code

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Redirects to LoginManager registration."""
    current_domain = request.host.split(':')[0]

    # Check maintenance mode.
    maintenance_mode = os.getenv("MAINTENANCE_MODE", "False").lower() in ("true", "1", "yes")
    if maintenance_mode:
        current_app.logger.info("[auth.register] Maintenance mode active.")
        return render_template("maintenance.html")

    redirect_uri = url_for('auth.handle_register', _external=True)
    lm_url = f"{LOGINMANAGER_MICROSERVICE_URL}/register-page"
    register_url = f"{lm_url}?redirect_uri={redirect_uri}&domain={current_domain}"

    current_app.logger.info(f"[auth.register] Redirecting: {register_url}")
    return redirect(register_url)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Redirects to LoginManager authentication."""
    form = LoginForm()
    current_domain = request.host.split(':')[0]

    # Forward GET requests.
    if request.method == 'GET':
        redirect_uri = url_for('auth.handle_login', _external=True)
        lm_login_url = (
            f"{LOGINMANAGER_MICROSERVICE_URL}/login-page"
            f"?redirect_uri={redirect_uri}&domain={current_domain}"
        )
        current_app.logger.info(f"[auth.login] Redirecting: {lm_login_url}")
        return redirect(lm_login_url)

    # Handle direct POST.
    if form.validate_on_submit():
        data = {
            "email": form.email.data,
            "password": form.password.data,
            "domain": current_domain,
        }
        try:
            resp = requests.post(
                f"{LOGINMANAGER_MICROSERVICE_URL}/login",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if resp.status_code == 200:
                payload = resp.json()
                token = payload.get("token")
                user_info = payload.get("user", {})
                username = user_info.get("username")
                email = user_info.get("email")

                if not token or not username:
                    flash("Login failed: Incomplete data.", "danger")
                    redirect_uri_fail = url_for('auth.handle_login', _external=True)
                    return redirect(f"{LOGINMANAGER_MICROSERVICE_URL}/login-page?redirect_uri={redirect_uri_fail}&domain={current_domain}")

                # FIX: Force fetch the domain-specific credits from the microservice.
                real_credits = user_info.get("credits_remaining", session.get("credits_remaining", 0))
                try:
                    cred_req = requests.post(
                        f"{LOGINMANAGER_MICROSERVICE_URL}/get_credits",
                        json={"domain": current_domain, "fingerprint": session.get("fingerprint"), "email": email},
                        timeout=5
                    )
                    if cred_req.status_code == 200:
                        real_credits = cred_req.json().get("credits_remaining", real_credits)
                except Exception as e:
                    current_app.logger.error(f"[auth.login] Failed to fetch true credits: {e}")

                session.update(
                    token=token,
                    user_id=username,
                    username=username,
                    email=email,
                    last_login=user_info.get("last_login"),
                    domain=current_domain,
                    free_credits=user_info.get("free_credits", 0),
                    purchased_credits=user_info.get("purchased_credits", 0),
                    credits_remaining=int(float(real_credits))
                )
                session.permanent = True
                flash("Login successful!", "success")
                return redirect(url_for('game.index'))
            else:
                try:
                    msg = resp.json().get("message", "Login failed.")
                except ValueError:
                    msg = "Login failed: Invalid response."
                flash(msg, "danger")
                redirect_uri_fail = url_for('auth.handle_login', _external=True)
                return redirect(f"{LOGINMANAGER_MICROSERVICE_URL}/login-page?redirect_uri={redirect_uri_fail}&domain={current_domain}")

        except requests.RequestException as e:
            current_app.logger.exception(f"[auth.login] Connection error: {e}")
            flash("Could not connect auth service.", "danger")
            redirect_uri_fail = url_for('auth.handle_login', _external=True)
            return redirect(f"{LOGINMANAGER_MICROSERVICE_URL}/login-page?redirect_uri={redirect_uri_fail}&domain={current_domain}")
    else:
        flash("Invalid email or password.", "danger")
        redirect_uri_fail = url_for('auth.handle_login', _external=True)
        return redirect(f"{LOGINMANAGER_MICROSERVICE_URL}/login-page?redirect_uri={redirect_uri_fail}&domain={current_domain}")

@auth_bp.route('/handle_login', methods=['GET'])
def handle_login():
    """Callback for successful authentication."""
    token = request.args.get('token')

    if not token:
        flash("Authentication failed: No token.", "danger")
        return redirect(url_for('game.index'))

    try:
        resp = requests.get(
            f"{LOGINMANAGER_MICROSERVICE_URL}/protected",
            headers={"Authorization": token},
            timeout=10,
        )
        if resp.status_code != 200:
            flash("Authentication failed: Invalid token.", "danger")
            return redirect(url_for('game.index'))

        user_data = resp.json()
        username = user_data.get("username")
        email = user_data.get("email")
        current_domain = request.host.split(":")[0]

        if not username:
            flash("Failed to retrieve profile.", "danger")
            return redirect(url_for('game.index'))

        # FIX: Force fetch the domain-specific credits from the microservice.
        real_credits = user_data.get("credits_remaining", session.get("credits_remaining", 0))
        try:
            cred_req = requests.post(
                f"{LOGINMANAGER_MICROSERVICE_URL}/get_credits",
                json={"domain": current_domain, "fingerprint": session.get("fingerprint"), "email": email},
                timeout=5
            )
            if cred_req.status_code == 200:
                real_credits = cred_req.json().get("credits_remaining", real_credits)
        except Exception as e:
            current_app.logger.error(f"[auth.handle_login] Failed to fetch true credits: {e}")

        session.update(
            token=token,
            user_id=username,
            username=username,
            email=email,
            last_login=user_data.get("last_login"),
            domain=current_domain,
            free_credits=user_data.get("free_credits", 0),
            purchased_credits=user_data.get("purchased_credits", 0),
            credits_remaining=int(float(real_credits))
        )
        session.permanent = True
        flash("Login successful!", "success")
        return redirect(url_for('game.index'))

    except requests.RequestException as e:
        current_app.logger.exception(f"[auth.handle_login] Verification error: {e}")
        flash("Could not verify login.", "danger")
        return redirect(url_for('game.index'))

@auth_bp.route('/handle_register', methods=['GET'])
def handle_register():
    """Callback endpoint after registration."""
    success = request.args.get("success", "false").lower() == "true"
    message = request.args.get("message", "")

    if success:
        flash(message or "Registration successful!", "success")
        return redirect(url_for('auth.login'))
    else:
        flash(message or "Registration failed.", "danger")
        return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    """Logs user out cleanly."""
    keys_to_clear = [
        "token", "user_id", "username", "email",
        "last_login", "credits_remaining",
        "free_credits", "purchased_credits",
        "current_sid", "fingerprint", "extras",
        "pending_transactions"
    ]
    for key in keys_to_clear:
        session.pop(key, None)

    flash("Successfully logged out.", "success")
    resp = make_response(redirect(url_for('game.index')))
    resp.delete_cookie("progress_done", path="/")
    return resp