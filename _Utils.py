# _Utils.py
from flask import request, session, current_app
from user_agents import parse
import geocoder
import time
import os
import uuid

# --- Added Lock Functions ---
STALE_LOCK_TIMEOUT = 20 # seconds

def acquire_lock(lock_path, timeout=5):
    """
    Acquires a simple, cross-process file lock.
    Includes a mechanism to detect and remove stale locks.
    """
    print(f"[LOCK] Attempting to acquire lock for '{lock_path}'...")
    try:
        if os.path.exists(lock_path):
            lock_age = time.time() - os.path.getmtime(lock_path)
            if lock_age > STALE_LOCK_TIMEOUT:
                current_app.logger.warning(
                    f"[LOCK] Found stale lock file '{lock_path}' (age: {lock_age:.2f}s). "
                    f"Assuming previous process crashed. Removing lock."
                )
                release_lock(lock_path) # Attempt to release the stale lock
    except OSError as e:
        current_app.logger.error(f"[LOCK] Error checking stale lock file '{lock_path}': {e}")
        # Proceed cautiously, might still be able to acquire if the check failed due to transient issue

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to create the lock file exclusively
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd) # Close the file descriptor immediately after creation
            current_app.logger.debug(f"[LOCK] Lock acquired successfully for '{lock_path}'.")
            return True
        except FileExistsError:
            # File already exists, wait a bit and try again
            current_app.logger.debug(f"[LOCK] Lock file '{lock_path}' exists, waiting...")
            time.sleep(0.1)
        except OSError as e:
            # Handle other potential OS errors during lock acquisition
            current_app.logger.error(f"[LOCK] OSError while trying to acquire lock for '{lock_path}': {e}")
            return False # Fail fast on unexpected OS errors

    current_app.logger.error(f"[LOCK] Failed to acquire lock for '{lock_path}' after timeout ({timeout}s).")
    return False

def release_lock(lock_path):
    """Releases the file lock."""
    print(f"[LOCK] Attempting to release lock for '{lock_path}'...")
    try:
        os.remove(lock_path)
        current_app.logger.debug(f"[LOCK] Lock released successfully for '{lock_path}'.")
    except FileNotFoundError:
        # If the file doesn't exist, the lock is already released or wasn't acquired.
        current_app.logger.warning(f"[LOCK] Attempted to release lock '{lock_path}', but it was not found (already released or never acquired?).")
        pass # It's okay if the lock file isn't there.
    except OSError as e:
        # Handle potential errors during file removal (e.g., permissions)
        current_app.logger.error(f"[LOCK] Error releasing lock file '{lock_path}': {e}")
# --- End Added Lock Functions ---


def detect_Device(ua):
    """Determines if the user agent is for a mobile device or PC."""
    print(f"[detect_Device] Parsing User-Agent: {ua}")
    parsed_ua = parse(ua)
    is_mobile_device = parsed_ua.is_mobile or parsed_ua.is_tablet
    device_type = 'Mobile' if is_mobile_device else 'PC'
    print(f"[detect_Device] Result: is_mobile={parsed_ua.is_mobile}, is_tablet={parsed_ua.is_tablet} -> {device_type}")
    return device_type

class TimeFunctions:
    """Utility class for time-related conversions."""
    @staticmethod
    def convert_unixtime(ts: int) -> str:
        """Converts a Unix timestamp to a human-readable string."""
        print(f"[TimeFunctions] Converting Unix time: {ts}")
        return time.ctime(ts)

def get_Subdomain() -> str:
    """Extracts the subdomain from the request host."""
    host = (request.host or "").split(':')[0]
    print(f"[get_Subdomain] Extracted host: {host}")
    subdomain = host.split('.')[0] if '.' in host else host
    print(f"[get_Subdomain] Determined subdomain: {subdomain}")
    return subdomain

def get_user_ip_and_location() -> tuple[str, str]:
    """Gets the user's IP address and approximate location."""
    print("[get_user_ip_and_location] Attempting to determine IP and location.")
    try:
        # Prioritize X-Forwarded-For if behind a proxy
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # Take the first IP in the list (client's IP)
            ip = forwarded.split(",")[0].strip()
            print(f"[get_user_ip_and_location] Found IP in X-Forwarded-For: {ip}")
        else:
            # Fallback to remote_addr
            ip = request.remote_addr or ""
            print(f"[get_user_ip_and_location] Using remote_addr: {ip}")

        # Use a public IP for local testing if needed
        if ip == "127.0.0.1":
            ip = "8.8.8.8" # Google's public DNS IP for testing purposes
            print(f"[get_user_ip_and_location] Local IP detected, using fallback test IP: {ip}")

        if not ip:
            print("[get_user_ip_and_location] No IP address found.")
            return "0.0.0.0", "Unknown"

        # Use geocoder to get location
        g = geocoder.ip(ip)
        if g.ok:
            loc = f"{g.city}, {g.state}, {g.country}"
            print(f"[get_user_ip_and_location] Geocoder OK. Location for {ip}: {loc}")
        else:
            loc = "Unknown"
            print(f"[get_user_ip_and_location] Geocoder failed for IP {ip}.")

        return ip, loc
    except Exception as exc:
        current_app.logger.error("[get_user_ip_and_location] IP/location lookup error: %s", exc)
        return "0.0.0.0", "Unknown"

def get_user_dir() -> str:
    """Determines the data directory for the current user/session."""
    print("[get_user_dir] Determining user data directory.")
    base = 'temp_data'
    # Generate a UUID if fingerprint is not in session, ensure consistent length
    uid = str(session.get("fingerprint", uuid.uuid4().hex))[:24]
    user_email = session.get("email", "")
    username = session.get("username", "")

    if user_email and username:
        # Use username for logged-in users for better identification
        base = 'user_data'
        uid = username # Assuming username is filesystem-safe or sanitized elsewhere
        print(f"[get_user_dir] Logged-in user '{username}'. Using base: {base}, uid: {uid}")
    else:
        print(f"[get_user_dir] Anonymous user. Using base: {base}, uid: {uid}")

    user_directory = os.path.join(base, uid)
    print(f"[get_user_dir] Final user directory path: {user_directory}")
    return user_directory