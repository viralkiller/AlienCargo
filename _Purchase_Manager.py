from datetime import datetime, timezone
import os
import requests
from flask import session, current_app as app
from urllib.parse import urlparse

class Purchase_Manager:
    """Handles payment callbacks and records purchases."""

    def __init__(self) -> None:
        app.logger.info("Initializing Purchase_Manager...")

        # Keep base URL consistent.
        self.login_manager_url = "https://loginmanager.pythonanywhere.com"
        app.logger.info(f"LoginManager URL set to: {self.login_manager_url}")

        # Load shared secret securely.
        self.credit_query_secret = os.environ.get("CRED_SECRET", "UpdateCreds")
        app.logger.warning("Loaded CRED_SECRET from environment.")

    # --------------------------------------------------------------------- #

    def process_payment(
        self,
        *,
        username: str,
        transaction_id: str,
        status: str,
        email: str,
        domain: str,
        credits_bought: float,
        method: str = "Stripe",
        currency: str = "usd",
        amount: float | None = None,
    ) -> tuple[bool, float]:
        """Records successful transactions via POST request."""

        app.logger.info(f"--- Initiating process_payment for user: {username} ---")
        app.logger.info(
            "Received params: transaction_id=%s, status=%s, credits_bought=%s, "
            "method=%s, currency=%s, amount=%s",
            transaction_id, status, credits_bought, method, currency, amount
        )

        # Proceed only on success.
        if status.upper() != "COMPLETED":
            app.logger.warning(
                "Payment status is '%s' (not 'COMPLETED') for transaction %s. Aborting record.",
                status, transaction_id
            )
            return False, 0.0

        app.logger.info("Payment status is COMPLETED for transaction %s.", transaction_id)

        # Normalize crypto payment method.
        payment_method = method
        if currency and currency.upper() == "ETH":
            app.logger.info(
                "Currency is ETH for transaction %s. Overriding payment method from '%s' to 'Crypto'.",
                transaction_id, method
            )
            payment_method = "Crypto"
        else:
            app.logger.info(
                "Using payment method '%s' for currency '%s'.",
                payment_method, currency
            )

        # Use actual amount or fallback.
        final_transaction_amount = amount
        if final_transaction_amount is None:
            app.logger.warning(
                "Transaction %s: 'amount' was not provided. "
                "Falling back to using 'credits_bought' (%s) for transaction_amount.",
                transaction_id, credits_bought
            )
            final_transaction_amount = credits_bought

        app.logger.debug(f"Final transaction amount resolved to: {final_transaction_amount}")

        record_url = f"{self.login_manager_url}/record-transaction"

        # Send secret via headers.
        headers = {"X-Service-Secret": self.credit_query_secret}

        payload = {
            "username": username,
            "email": email,
            "user_fingerprint": session.get("fingerprint"),
            "domain": (urlparse(domain).netloc or domain),
            "transaction_id": transaction_id,
            "transaction_type": "saas_credits",
            "transaction_currency": currency,
            "transaction_amount": float(final_transaction_amount),
            "credits_purchased": float(credits_bought),
            "payment_method": payment_method,
            "details": f"Purchase of {credits_bought} credits via {payment_method}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extras": session.get("extras", {}),
        }

        app.logger.info("Constructed payload for LoginManager: %s", payload)

        try:
            app.logger.info(
                "Sending POST request to %s for transaction %s...",
                record_url, transaction_id
            )
            resp = requests.post(
                record_url,
                json=payload,
                headers=headers,
                timeout=10,
            )
            app.logger.info("Request sent. Received status code: %s", resp.status_code)
        except requests.RequestException as exc:
            app.logger.exception(
                "HTTP request to LoginManager failed for transaction %s: %s",
                transaction_id, exc
            )
            return False, 0.0

        if resp.status_code == 200:
            app.logger.info(
                "[OK] Transaction '%s' recorded successfully for %s",
                transaction_id, username
            )
            return True, credits_bought

        app.logger.error(
            "[ERROR] record-transaction failed for transaction %s. "
            "Status: %s, Response: %s",
            transaction_id, resp.status_code, resp.text[:300]
        )
        return False, 0.0