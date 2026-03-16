# _Utils.py
from flask import request, current_app
from user_agents import parse
import geocoder
import time
import os
import logging

# Standardized logging for utilities.
logger = logging.getLogger(__name__)
STALE_LOCK_TIMEOUT = 20

def acquire_lock(lock_path, timeout=5):
    """Acquires cross-process file lock with stale cleanup."""
    logger.debug(f"[LOCK] Attempting lock: {lock_path}")
    try:
        if os.path.exists(lock_path):
            if time.time() - os.path.getmtime(lock_path) > STALE_LOCK_TIMEOUT:
                logger.warning(f"[LOCK] Removing stale lock: {lock_path}")
                release_lock(lock_path)
    except OSError:
        pass

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            logger.debug(f"[LOCK] Acquired: {lock_path}")
            return True
        except FileExistsError:
            time.sleep(0.1)
        except OSError:
            return False
    return False

def release_lock(lock_path):
    """Releases the file lock."""
    try:
        os.remove(lock_path)
        logger.debug(f"[LOCK] Released: {lock_path}")
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.error(f"[LOCK] Release error: {e}")

def detect_Device(ua):
    """Detects if device is Mobile or PC."""
    parsed_ua = parse(ua)
    return 'Mobile' if (parsed_ua.is_mobile or parsed_ua.is_tablet) else 'PC'

class TimeFunctions:
    @staticmethod
    def convert_unixtime(ts: int) -> str:
        return time.ctime(ts)

def get_Subdomain() -> str:
    """Extracts valid subdomain, stripping 'www'."""
    host = (request.host or "").split(':')[0]
    if host.startswith("www."):
        host = host[4:]
    subdomain = host.split('.')[0] if '.' in host else host
    logger.debug(f"[get_Subdomain] Result: {subdomain}")
    return subdomain

def get_user_ip_and_location() -> tuple[str, str]:
    """Retrieves IP and Location with proxy awareness."""
    try:
        forwarded = request.headers.get("X-Forwarded-For", "")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "0.0.0.0")

        # Testing fallback.
        if ip == "127.0.0.1":
            ip = "8.8.8.8"

        g = geocoder.ip(ip)
        loc = f"{g.city}, {g.state}, {g.country}" if g.ok else "Unknown"
        return ip, loc
    except Exception as e:
        logger.error(f"IP/Loc lookup error: {e}")
        return "0.0.0.0", "Unknown"