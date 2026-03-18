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

# Helpers
from _Utils import (
    get_Subdomain, get_user_ip_and_location, TimeFunctions, detect_Device
)
from _Purchase_Manager import Purchase_Manager
from _AESCipher import AESCipher

# -----------------------------------------------------------------------------
# External service endpoints
# -----------------------------------------------------------------------------
LOGINMANAGER_MICROSERVICE_URL = "https://loginmanager.pythonanywhere.com"

# -----------------------------------------------------------------------------
# Blueprint
# -----------------------------------------------------------------------------
billing_bp = Blueprint("billing", __name__)

# -----------------------------------------------------------------------------
# Fingerprint proxy endpoint (recommended frontend target)
@billing_bp.route("/billing/report_standard", methods=["POST"])
def report_standard():
    """Receives fingerprint metadata. Forwards to LoginManager."""
    current_app.logger.info("[Billing] Invoked report_standard endpoint.")

    try:
        # Parse Request Data.
        data = request.get_json(force=True)
        if not data:
            current_app.logger.warning("[Billing] Missing JSON data.")
            return jsonify(error="No JSON data received"), 400

        fingerprint = data.get("fingerprint")
        email = (data.get("email") or "").strip()
        domain = get_Subdomain()
        email_verified = data.get("email_verified", "NA") if email else "NA"
        created_at = data.get("created_at", time.time())

        # Prepare Extras.
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

        # Server-side IP lookup.
        try:
            ip, loc = get_user_ip_and_location()
            extras["ip"], extras["location"] = ip, loc
        except Exception as e:
            current_app.logger.error(f"[Billing] IP Lookup failed: {e}")
            extras["ip"], extras["location"] = "0.0.0.0", "Lookup Failed"

        # Update Session variables.
        if fingerprint:
            session["fingerprint"] = fingerprint
        if email:
            session["email"] = email
        session["extras"] = extras

        # Send to Microservice.
        payload = {
            "fingerprint": fingerprint,
            "email": email,
            "email_verified": email_verified,
            "created_at": created_at,
            "domain": domain,
            "extras": extras,
        }

        current_app.logger.info(f"[report_standard] Sending payload to {LOGINMANAGER_MICROSERVICE_URL}...")
        r = requests.post(
            f"{LOGINMANAGER_MICROSERVICE_URL}/gather_fingerprint_data",
            json=payload,
            timeout=10,
        )
        r.raise_for_status()

        current_app.logger.info("[Billing] Fingerprint payload sent successfully.")
        return jsonify(remote_response=r.json()), 200

    except requests.exceptions.RequestException as re:
        current_app.logger.error(f"[Billing] External Connection Error: {re}")
        # Return 202 to stop bleeding red errors.
        return jsonify(error=f"Connection to LoginManager failed: {str(re)}"), 202
    except Exception as exc:
        current_app.logger.exception("[Billing] report_standard crashed.")
        return jsonify(error=f"Server Error: {str(exc)}"), 500

# -----------------------------------------------------------------------------
# Credit usage reporting
# -----------------------------------------------------------------------------
@billing_bp.route("/billing/report_credit_usage", methods=["POST"])
def report_credit_usage():
    """Logs credit usage reports from frontend."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        amount = data.get('amount', 0)
        user_id = session.get("email") or "Unknown"

        current_app.logger.info(f"--- [BILLING] Credit Usage Reported ---")
        current_app.logger.info(f"User: {user_id} | Amount: {amount}")
        return jsonify({"status": "success", "message": "Usage logged"}), 200
    except Exception as e:
        current_app.logger.error(f"!!! [BILLING ERROR] Usage report failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# -----------------------------------------------------------------------------
# Credit lookup
# -----------------------------------------------------------------------------
@billing_bp.route("/billing/get_credits", methods=["POST"])
def get_credits():
    """Retrieves credit balance."""
    data = request.get_json(force=True, silent=True) or {}

    # Prioritize trusted session identity.
    fingerprint = session.get("fingerprint") or data.get("fingerprint")
    email = session.get("email") or data.get("email", "")

    if not fingerprint:
        current_app.logger.warning("[Billing] Missing fingerprint for credit check.")
        return jsonify(error="Missing fingerprint"), 400

    if not session.get("fingerprint"):
        session["fingerprint"] = fingerprint

    payload = {"domain": get_Subdomain(), "fingerprint": fingerprint, "email": email}
    current_app.logger.info(f"[Billing] Fetching credits for {email or fingerprint}.")

    try:
        r = requests.post(
            f"{LOGINMANAGER_MICROSERVICE_URL}/get_credits", json=payload, timeout=5
        )
        r.raise_for_status()
        credits = r.json().get("credits_remaining", 0)

        current_app.logger.info(f"[Billing] Credits retrieved: {credits}.")
        return jsonify(credits_remaining=int(float(credits))), 200
    except Exception as exc:
        current_app.logger.error("[Billing] get_credits failed: %s", exc)
        return jsonify(error="Unable to fetch credits"), 502

# -----------------------------------------------------------------------------
# Pricing / tiers
# -----------------------------------------------------------------------------
def handle_standard_payment(tid, price, email):
    subdomain = get_Subdomain()
    encoded_email = quote(email, safe="")
    base_url = "https://" + "stripegateway.pythonanywhere.com" + "/process"
    return f"{base_url}/{subdomain}/{tid}/{price}/{encoded_email}"

def handle_eth_payment(tid, price, email):
    subdomain = get_Subdomain()
    encoded_email = quote(email, safe="")
    base_url = "https://" + "cryptgateway.pythonanywhere.com" + "/process"
    return f"{base_url}/{subdomain}/{tid}/{price}/{encoded_email}"

def clean_stale_transactions(pending_txs, timeout_seconds=1800):
    """Removes transactions older than 30 mins."""
    if not pending_txs:
        return pending_txs
    now = time.time()
    to_remove = [k for k, v in pending_txs.items() if now - v.get("created_at", 0) > timeout_seconds]
    for k in to_remove:
        del pending_txs[k]
    if to_remove:
        current_app.logger.info(f"[Billing] Garbage Collection: Removed {len(to_remove)} stale transactions.")
    return pending_txs

@billing_bp.route("/billing/tiers", methods=["GET", "POST"])
def tiers():
    email = session.get("email", "").strip()
    device = detect_Device(request.headers.get("User-Agent"))

    # Credit amounts and displayed prices.
    sa, ma, la = 10, 50, 100
    sp, mp, lp = "2.00", "5.00", "9.00"

    if request.method == "POST":
        current_app.logger.info("[Billing] Purchase package requested.")
        if not email:
            current_app.logger.warning("[Billing] Blocked attempt: expired session.")
            flash("Your session has expired. Please log in again to purchase credits.", "danger")
            return redirect(url_for('auth.login'))

        pm = request.form.get("payment_method")
        pk = request.form["package"]
        cr = float(request.form["credits"])
        pr = request.form["price"]
        tid = str(uuid.uuid4())

        pending_txs = session.get("pending_transactions", {})
        pending_txs = clean_stale_transactions(pending_txs)

        pending_txs[tid] = {
            "credits": cr,
            "price": pr,
            "payment_method": pm,
            "created_at": time.time()
        }
        session["pending_transactions"] = pending_txs

        current_app.logger.info(f"[Billing] Initiating transaction {tid} for {cr} credits via {pm}.")

        if pm == "standard":
            payment_url = handle_standard_payment(tid, pr, email)
        elif pm == "eth":
            payment_url = handle_eth_payment(tid, pr, email)
        else:
            current_app.logger.error(f"[Billing] Invalid payment method: {pm}.")
            flash("Invalid payment method selected.")
            return redirect(url_for("billing.tiers"))

        if email in [
            "jules3313@gmail.com",
            "tmnt2017@gmail.com",
            "secrino7@yahoo.com",
        ]:
            current_app.logger.info("[Billing] Test mode activated for transaction.")
            payment_url += "&test_mode=true" if "?" in payment_url else "?test_mode=true"

        current_app.logger.info(f"[Billing] Redirecting user to gateway: {payment_url}")
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
# Finalization after payment (Stripe/ETH gateways redirect here)
# -----------------------------------------------------------------------------
@billing_bp.route("/final/<transaction_id>/<status>", methods=["GET", "POST"])
def final(transaction_id, status):
    current_app.logger.info(f"[final] Resolving payment {transaction_id}.")
    purchase_manager = Purchase_Manager()

    email = session.get("email")
    domain = get_Subdomain()

    try:
        shop_key = current_app.config["SHOP_KEY"]
        cipher = AESCipher(shop_key)
        decrypted_status = cipher.decrypt_with_timecheck(status)
        current_app.logger.info(f"[final] Raw decrypted status: {decrypted_status}")
    except Exception as e:
        current_app.logger.exception(f"[final] Failed to decrypt status token: {e}")
        return redirect(url_for("game.index"))

    if not session.get("token"):
        current_app.logger.warning("[final] User not authenticated. Aborting.")
        return redirect(url_for("game.index"))

    try:
        # Sanitize status to prevent formatting errors bypassing validation.
        clean_status = decrypted_status.strip().upper()
        current_app.logger.info(f"[final] Sanitized status: {clean_status}")

        if clean_status == "COMPLETED":
            pending_txs = session.get("pending_transactions", {})
            tx_data = pending_txs.get(transaction_id)

            if not tx_data:
                current_app.logger.error(f"[final] Transaction {transaction_id} not found in pending list.")
                flash("Transaction details missing or expired. Please contact support.", "error")
                return redirect(url_for("game.index"))

            purchased_credits = tx_data.get("credits", 0)
            amount_paid = tx_data.get("price")
            payment_method = tx_data.get("payment_method", "Stripe")
            username = session.get("username")

            current_app.logger.info(f"[final] Processing {purchased_credits} credits via Purchase Manager.")

            success, _ = purchase_manager.process_payment(
                username=username,
                transaction_id=transaction_id,
                status=clean_status,
                email=email,
                domain=domain,
                credits_bought=purchased_credits,
                amount=amount_paid,
                method=payment_method,
            )

            if not success:
                current_app.logger.error("[final] Credit update via LoginManager failed.")
                flash("Your payment was successful, but there was an issue adding credits. Please contact support.", "error")
                return redirect(url_for("game.index"))

            # Clear pending transaction.
            current_app.logger.info(f"[final] Popping transaction {transaction_id}.")
            pending_txs.pop(transaction_id, None)
            session["pending_transactions"] = pending_txs

            # Sync local session balance immediately.
            current_balance = session.get("credits_remaining", 0)
            session["credits_remaining"] = current_balance + purchased_credits
            session.modified = True

            current_app.logger.info(f"[final] Session balance updated to {session['credits_remaining']}.")
            flash("Purchase successful! Your credits have been added.", "success")

        else:
            current_app.logger.info(f"[final] Payment status was '{clean_status}'. Redirecting to issue page.")
            return render_template("billing_issue.html")

    except Exception as e:
        current_app.logger.exception(f"[final] Unexpected processing error: {e}")
        flash("An unexpected error occurred. Please contact support.", "error")
        return redirect(url_for("game.index"))

    current_app.logger.info("[final] Purchase sequence complete. Redirecting home.")
    return redirect(url_for("game.index"))