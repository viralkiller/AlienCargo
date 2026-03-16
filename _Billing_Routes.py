#_Billing_Routes.py
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

# Import utilities.
from _Utils import (
    get_Subdomain, get_user_ip_and_location, TimeFunctions, detect_Device
)

# Payment-specific modules.
from _Purchase_Manager import Purchase_Manager
from _AESCipher import AESCipher

LOGINMANAGER_MICROSERVICE_URL = "[https://loginmanager.pythonanywhere.com](https://loginmanager.pythonanywhere.com)"

billing_bp = Blueprint("billing", __name__)

@billing_bp.route("/report_standard", methods=["POST"])
def report_standard():
    """Receives and proxies client fingerprint data."""
    try:
        # Parse data securely.
        data = request.get_json(force=True)
        if not data:
            return jsonify(error="No JSON data."), 400

        fingerprint = data.get("fingerprint")
        email = (data.get("email") or "").strip()
        domain = get_Subdomain()
        email_verified = data.get("email_verified", "NA") if email else "NA"
        created_at = data.get("created_at", time.time())

        # Prepare hardware extras.
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

        # Determine actual network location.
        try:
            ip, loc = get_user_ip_and_location()
            extras["ip"], extras["location"] = ip, loc
        except Exception as e:
            current_app.logger.error(f"IP Lookup failed: {e}")
            extras["ip"], extras["location"] = "0.0.0.0", "Lookup Failed"

        # Update local session.
        if fingerprint:
            session["fingerprint"] = fingerprint
        if email:
            session["email"] = email
        session["extras"] = extras

        # Dispatch to Identity service.
        payload = {
            "fingerprint": fingerprint,
            "email": email,
            "email_verified": email_verified,
            "created_at": created_at,
            "domain": domain,
            "extras": extras,
        }

        current_app.logger.info(f"Proxying fingerprint payload.")
        r = requests.post(
            f"{LOGINMANAGER_MICROSERVICE_URL}/gather_fingerprint_data",
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        return jsonify(remote_response=r.json()), 200

    except requests.exceptions.RequestException as re:
        current_app.logger.error(f"Proxy Connection Error: {re}")
        return jsonify(error=f"LoginManager failed: {str(re)}"), 502
    except Exception as exc:
        current_app.logger.exception("Proxy logic crashed.")
        return jsonify(error=f"Server Error: {str(exc)}"), 500

@billing_bp.route("/report_credit_usage", methods=["POST"])
def report_credit_usage():
    """Logs client credit usage."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        amount = data.get('amount', 0)
        user_id = session.get("email") or "Unknown"

        # Log basic usage tracking.
        current_app.logger.info(f"[BILLING] Usage Reported: {user_id} - {amount}")
        return jsonify({"status": "success", "message": "Usage logged"}), 200
    except Exception as e:
        current_app.logger.error(f"[BILLING] Failed logging usage: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@billing_bp.route("/get_credits", methods=["POST"])
def get_credits():
    """Retrieves authoritative credit balance."""
    data = request.get_json(force=True, silent=True) or {}

    # Priority check for fingerprint.
    fingerprint = session.get("fingerprint") or data.get("fingerprint")
    email = session.get("email") or data.get("email", "")

    if not fingerprint:
        return jsonify(error="Missing fingerprint."), 400

    # Store missing fingerprint.
    if not session.get("fingerprint"):
        session["fingerprint"] = fingerprint

    payload = {"domain": get_Subdomain(), "fingerprint": fingerprint, "email": email}

    try:
        r = requests.post(
            f"{LOGINMANAGER_MICROSERVICE_URL}/get_credits", json=payload, timeout=5
        )
        r.raise_for_status()
        credits = r.json().get("credits_remaining", 0)
        # Ensure integer output.
        return jsonify(credits_remaining=int(float(credits))), 200
    except Exception as exc:
        current_app.logger.error("Credit fetch failed: %s", exc)
        return jsonify(error="Unable to fetch credits."), 502

def handle_standard_payment(tid, price, email):
    # Formats Stripe link.
    subdomain = get_Subdomain()
    encoded_email = quote(email, safe="")
    return f"[https://stripegateway.pythonanywhere.com/process/](https://stripegateway.pythonanywhere.com/process/){subdomain}/{tid}/{price}/{encoded_email}"

def handle_eth_payment(tid, price, email):
    # Formats Ethereum link.
    subdomain = get_Subdomain()
    encoded_email = quote(email, safe="")
    return f"[https://cryptgateway.pythonanywhere.com/process/](https://cryptgateway.pythonanywhere.com/process/){subdomain}/{tid}/{price}/{encoded_email}"

def clean_stale_transactions(pending_txs, timeout_seconds=1800):
    """Purges expired transactions from dictionary."""
    if not pending_txs:
        return pending_txs
    now = time.time()
    to_remove = [k for k, v in pending_txs.items() if now - v.get("created_at", 0) > timeout_seconds]
    for k in to_remove:
        del pending_txs[k]
    if to_remove:
        current_app.logger.info(f"Garbage Collection: Purged {len(to_remove)} stales.")
    return pending_txs

@billing_bp.route("/tiers", methods=["GET", "POST"])
def tiers():
    # Process user tiers.
    email = session.get("email", "").strip()
    device = detect_Device(request.headers.get("User-Agent"))

    sa, ma, la = 10, 50, 100
    sp, mp, lp = "2.00", "5.00", "9.00"

    if request.method == "POST":
        # Block unauthorized transactions.
        if not email:
            current_app.logger.warning("Blocked purchase: missing email.")
            flash("Session expired. Log in.", "danger")
            return redirect(url_for('auth.login'))

        pm = request.form.get("payment_method")
        pk = request.form["package"]
        cr = float(request.form["credits"])
        pr = request.form["price"]
        tid = str(uuid.uuid4())

        # Retrieve pending states.
        pending_txs = session.get("pending_transactions", {})
        pending_txs = clean_stale_transactions(pending_txs)

        pending_txs[tid] = {
            "credits": cr,
            "price": pr,
            "payment_method": pm,
            "created_at": time.time()
        }
        session["pending_transactions"] = pending_txs

        current_app.logger.info(f"Init {tid} for {cr} credits via {pm}")

        if pm == "standard":
            payment_url = handle_standard_payment(tid, pr, email)
        elif pm == "eth":
            payment_url = handle_eth_payment(tid, pr, email)
        else:
            flash("Invalid method selected.")
            return redirect(url_for("billing.tiers"))

        # Admin sandbox accounts.
        if email in ["jules3313@gmail.com", "tmnt2017@gmail.com", "secrino7@yahoo.com"]:
            payment_url += "&test_mode=true" if "?" in payment_url else "?test_mode=true"

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

@billing_bp.route("/final/<transaction_id>/<status>", methods=["GET", "POST"])
def final(transaction_id, status):
    # Verify returning payment callbacks.
    purchase_manager = Purchase_Manager()
    email = session.get("email")
    domain = get_Subdomain()

    try:
        shop_key = current_app.config["SHOP_KEY"]
        cipher = AESCipher(shop_key)
        decrypted_status = cipher.decrypt_with_timecheck(status)
        current_app.logger.info(f"Decrypted status: {decrypted_status}")
    except Exception as e:
        current_app.logger.exception(f"Decryption failed: {e}")
        return redirect(url_for("game.index"))

    if not session.get("token"):
        current_app.logger.warning("Unauthenticated callback aborted.")
        return redirect(url_for("game.index"))

    try:
        if decrypted_status == "COMPLETED":
            pending_txs = session.get("pending_transactions", {})
            tx_data = pending_txs.get(transaction_id)

            if not tx_data:
                current_app.logger.error(f"Transaction {transaction_id} not found.")
                flash("Transaction details missing.", "error")
                return redirect(url_for("game.index"))

            purchased_credits = tx_data.get("credits")
            amount_paid = tx_data.get("price")
            payment_method = tx_data.get("payment_method", "Stripe")
            username = session.get("username")

            success, _ = purchase_manager.process_payment(
                username=username,
                transaction_id=transaction_id,
                status=decrypted_status,
                email=email,
                domain=domain,
                credits_bought=purchased_credits,
                amount=amount_paid,
                method=payment_method,
            )

            if not success:
                current_app.logger.error("Credit update failed post-payment.")
                flash("Purchase succeeded, but credit allocation failed.", "error")
                return redirect(url_for("game.index"))

            # Pop transaction.
            pending_txs.pop(transaction_id, None)
            session["pending_transactions"] = pending_txs
            flash("Credits added successfully!", "success")
        else:
            current_app.logger.info(f"Incomplete status: {decrypted_status}")
            return render_template("billing_issue.html")

    except Exception as e:
        current_app.logger.exception(f"Unexpected processing error: {e}")
        flash("Unexpected error occurred.", "error")
        return redirect(url_for("game.index"))

    return redirect(url_for("game.index"))