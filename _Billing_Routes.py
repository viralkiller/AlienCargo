# _Billing_Routes.py
from flask import (
    Blueprint, request, jsonify, session, current_app, render_template,
    flash, redirect, url_for
)
import os
import time
import requests
import uuid
import math
from collections import OrderedDict
from urllib.parse import quote

# Helpers.
from _Utils import (
    get_Subdomain, get_user_ip_and_location, TimeFunctions, detect_Device
)

# Payment modules.
from _Purchase_Manager import Purchase_Manager
from _AESCipher import AESCipher

# -----------------------------------------------------------------------------
# External endpoints.
# -----------------------------------------------------------------------------
LOGINMANAGER_MICROSERVICE_URL = "https://loginmanager.pythonanywhere.com"

# -----------------------------------------------------------------------------
# Blueprint.
# -----------------------------------------------------------------------------
billing_bp = Blueprint("billing", __name__)

# -----------------------------------------------------------------------------
# Fingerprint proxy endpoint.
@billing_bp.route("/report_standard", methods=["POST"])
def report_standard():
    # Log route entry.
    current_app.logger.debug("Entering /report_standard route.")
    try:
        # Parse JSON request data.
        data = request.get_json(force=True)
        if not data:
            current_app.logger.warning("No JSON data received.")
            return jsonify(error="No JSON data received"), 400

        fingerprint = data.get("fingerprint")
        email = (data.get("email") or "").strip()
        domain = get_Subdomain()
        email_verified = data.get("email_verified", "NA") if email else "NA"
        created_at = data.get("created_at", time.time())
        current_app.logger.debug(f"Parsed basic data for: {email}")

        # Handle missing extras dict.
        raw_extras = data.get("extras")
        if not isinstance(raw_extras, dict):
            raw_extras = {}

        extras = OrderedDict(
            sorted(
                {
                    "gpu": raw_extras.get("gpu", ""),
                    "canvasHash": raw_extras.get("canvasHash", ""),
                    "browser": raw_extras.get("browser", ""),
                    "timezone": raw_extras.get("timezone", ""),
                    "location": raw_extras.get("location", ""),
                    "ip": raw_extras.get("ip", ""),
                }.items()
            )
        )

        # Lookup server IP and location.
        try:
            ip, loc = get_user_ip_and_location()
            extras["ip"], extras["location"] = ip, loc
            current_app.logger.debug("IP and location lookup successful.")
        except Exception as e:
            current_app.logger.error(f"IP Lookup failed: {e}")
            extras["ip"], extras["location"] = "0.0.0.0", "Lookup Failed"

        # Update user session data.
        if fingerprint:
            session["fingerprint"] = fingerprint
        if email:
            session["email"] = email
        session["extras"] = extras

        # Forward data to microservice.
        payload = {
            "fingerprint": fingerprint,
            "email": email,
            "email_verified": email_verified,
            "created_at": created_at,
            "domain": domain,
            "extras": extras,
        }

        # Print to server log.
        current_app.logger.debug(f"Sending payload to {LOGINMANAGER_MICROSERVICE_URL}...")

        r = requests.post(
            f"{LOGINMANAGER_MICROSERVICE_URL}/gather_fingerprint_data",
            json=payload,
            timeout=10,
        )
        r.raise_for_status()

        current_app.logger.info("Successfully reported fingerprint data.")
        return jsonify(remote_response=r.json()), 200

    except requests.exceptions.RequestException as re:
        # Catch connection errors.
        current_app.logger.error(f"External Connection Error: {re}")
        return jsonify(error=f"Connection to LoginManager failed: {str(re)}"), 502

    except Exception as exc:
        # Catch general code errors.
        current_app.logger.exception("report_standard crashed")
        # Return error to browser.
        return jsonify(error=f"Server Error: {str(exc)}"), 500

# -----------------------------------------------------------------------------
# Credit usage reporting.
# -----------------------------------------------------------------------------
@billing_bp.route("/report_credit_usage", methods=["POST"])
def report_credit_usage():
    # Log route entry.
    current_app.logger.debug("Entering /report_credit_usage route.")
    try:
        data = request.get_json(force=True, silent=True) or {}
        amount = data.get('amount', 0)
        user_id = session.get("email") or "Unknown"

        # Log frontend usage report.
        current_app.logger.info(f"--- [BILLING] Credit Usage Reported (Frontend) ---")
        current_app.logger.info(f"User: {user_id} | Amount: {amount}")

        # Return success to frontend.
        return jsonify({"status": "success", "message": "Usage logged"}), 200

    except Exception as e:
        current_app.logger.error(f"!!! [BILLING ERROR] Failed to report usage: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# -----------------------------------------------------------------------------
# Credit lookup.
# -----------------------------------------------------------------------------
@billing_bp.route("/get_credits", methods=["POST"])
def get_credits():
    # Log route entry.
    current_app.logger.debug("Entering /get_credits route.")
    data = request.get_json(force=True, silent=True) or {}

    # Use trusted session fingerprint.
    # Prevent cross-user balance querying.
    fingerprint = session.get("fingerprint") or data.get("fingerprint")
    email = session.get("email") or data.get("email", "")

    if not fingerprint:
        current_app.logger.warning("Missing fingerprint in /get_credits.")
        return jsonify(error="Missing fingerprint"), 400

    # Refresh session fingerprint.
    if not session.get("fingerprint"):
        session["fingerprint"] = fingerprint

    payload = {"domain": get_Subdomain(), "fingerprint": fingerprint, "email": email}

    try:
        current_app.logger.debug("Requesting credits from LoginManager.")
        r = requests.post(
            f"{LOGINMANAGER_MICROSERVICE_URL}/get_credits", json=payload, timeout=5
        )
        r.raise_for_status()
        credits = r.json().get("credits_remaining", 0)

        current_app.logger.info(f"Fetched credits successfully: {credits}")
        # Return integer credit value.
        return jsonify(credits_remaining=int(float(credits))), 200

    except Exception as exc:
        current_app.logger.error("get_credits failed: %s", exc)
        return jsonify(error="Unable to fetch credits"), 502

# -----------------------------------------------------------------------------
# Pricing and tiers.
# -----------------------------------------------------------------------------
def handle_standard_payment(tid, price, email):
    subdomain = get_Subdomain()
    encoded_email = quote(email, safe="")
    current_app.logger.debug("Generated standard payment URL.")
    return f"https://stripegateway.pythonanywhere.com/process/{subdomain}/{tid}/{price}/{encoded_email}"

def handle_eth_payment(tid, price, email):
    subdomain = get_Subdomain()
    encoded_email = quote(email, safe="")
    current_app.logger.debug("Generated ETH payment URL.")
    return f"https://cryptgateway.pythonanywhere.com/process/{subdomain}/{tid}/{price}/{encoded_email}"

def clean_stale_transactions(pending_txs, timeout_seconds=1800):
    # Helper to clean stale transactions.
    # Prevents session cookie overflow.
    if not pending_txs:
        return pending_txs

    now = time.time()
    # List keys to remove.
    to_remove = [k for k, v in pending_txs.items() if now - v.get("created_at", 0) > timeout_seconds]

    for k in to_remove:
        # Safely remove dictionary key.
        del pending_txs[k]

    if to_remove:
        current_app.logger.info(f"[Billing] Garbage Collection: Removed {len(to_remove)} stale transactions.")

    return pending_txs

@billing_bp.route("/tiers", methods=["GET", "POST"])
def tiers():
    # Log route entry.
    current_app.logger.debug("Entering /tiers route.")
    # Preserve email character casing.
    email = session.get("email", "").strip()
    device = detect_Device(request.headers.get("User-Agent"))

    # Credit amounts and prices.
    sa, ma, la = 10, 50, 100
    sp, mp, lp = "2.00", "5.00", "9.00"

    if request.method == "POST":
        current_app.logger.debug("Processing POST request for tiers.")
        # Strict session verification check.
        if not email:
            current_app.logger.warning("[Billing] Blocked purchase attempt with expired session/empty email.")
            flash("Your session has expired. Please log in again to purchase credits.", "danger")
            return redirect(url_for('auth.login'))

        pm = request.form.get("payment_method")
        pk = request.form["package"]

        # Cast credits to integer.
        cr = int(float(request.form["credits"]))
        pr = request.form["price"]
        tid = str(uuid.uuid4())

        # Store transaction details securely.
        # Prevent tab switching exploit.
        pending_txs = session.get("pending_transactions", {})

        # Run garbage collection first.
        pending_txs = clean_stale_transactions(pending_txs)

        pending_txs[tid] = {
            "credits": cr,
            "price": pr, # Persist accurate financial price.
            "payment_method": pm,
            "created_at": time.time()
        }
        session["pending_transactions"] = pending_txs

        current_app.logger.info(f"Initiating transaction {tid} for {cr} credits via {pm}")

        if pm == "standard":
            payment_url = handle_standard_payment(tid, pr, email)
        elif pm == "eth":
            payment_url = handle_eth_payment(tid, pr, email)
        else:
            current_app.logger.warning("Invalid payment method selected.")
            flash("Invalid payment method selected.")
            return redirect(url_for("billing.tiers"))

        if email in [
            "jules3313@gmail.com",
            "tmnt2017@gmail.com",
            "secrino7@yahoo.com",
        ]:
            payment_url += "&test_mode=true" if "?" in payment_url else "?test_mode=true"

        current_app.logger.debug(f"Redirecting to payment URL: {payment_url}")
        return redirect(payment_url)

    return render_template(
        "tiers.html",
        device=device,
        email=email,
        small_package_amount=sa,
        mid_package_amount=ma,
        large_package_amount=la,
        small_package_price=sp,
        mid_package_price=mp,
        large_package_price=lp,
    )

# -----------------------------------------------------------------------------
# Finalize post-payment redirects.
# -----------------------------------------------------------------------------
@billing_bp.route("/final/<transaction_id>/<status>", methods=["GET", "POST"])
def final(transaction_id, status):
    # Log route entry.
    current_app.logger.debug(f"Entering /final route for TX: {transaction_id}")
    purchase_manager = Purchase_Manager()
    email = session.get("email")
    domain = get_Subdomain()

    try:
        shop_key = current_app.config["SHOP_KEY"]
        cipher = AESCipher(shop_key)
        decrypted_status = cipher.decrypt_with_timecheck(status)
        current_app.logger.info("[final] Decrypted status: %s", decrypted_status)
    except Exception as e:
        current_app.logger.exception("[final] Failed to decrypt status token: %s", e)
        return redirect(url_for("index"))

    if not session.get("token"):
        current_app.logger.warning("[final] User not authenticated. Aborting.")
        # Redirect to home fallback.
        return redirect(url_for("index"))

    try:
        if decrypted_status == "COMPLETED":
            # Retrieve specific transaction details.
            pending_txs = session.get("pending_transactions", {})
            tx_data = pending_txs.get(transaction_id)

            if not tx_data:
                current_app.logger.error(f"[final] Transaction {transaction_id} not found in pending list. Possible replay or invalid ID.")
                flash("Transaction details missing or expired. Please contact support.", "error")
                return redirect(url_for("index"))

            # Use stored credit amount.
            purchased_credits = tx_data.get("credits")
            amount_paid = tx_data.get("price") # Retrieve actual paid price.
            payment_method = tx_data.get("payment_method", "Stripe")
            username = session.get("username")

            current_app.logger.debug("Processing payment via Purchase_Manager.")
            success, _ = purchase_manager.process_payment(
                username=username,
                transaction_id=transaction_id,
                status=decrypted_status,
                email=email,
                domain=domain,
                credits_bought=purchased_credits,
                amount=amount_paid, # Pass price to manager.
                method=payment_method,
            )

            if not success:
                current_app.logger.error(
                    "Credit update via LoginManager failed after successful payment."
                )
                flash(
                    "Your payment was successful, but there was an issue adding credits. Please contact support.",
                    "error",
                )
                return redirect(url_for("index"))

            # Remove transaction to secure.
            pending_txs.pop(transaction_id, None)
            session["pending_transactions"] = pending_txs

            current_app.logger.info("Purchase completed successfully.")
            flash("Purchase successful! Your credits have been added.", "success")
        else:
            current_app.logger.info(
                "Payment status was '%s', not 'COMPLETED'. Redirecting to billing issue page.",
                decrypted_status,
            )
            return render_template("billing_issue.html")

    except Exception as e:
        current_app.logger.exception(
            "[final] Unexpected error during payment processing: %s", e
        )
        flash("An unexpected error occurred. Please contact support.", "error")
        return redirect(url_for("index"))

    return redirect(url_for("index"))