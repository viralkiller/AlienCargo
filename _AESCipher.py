from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import hashlib
import json
from datetime import datetime, timedelta

class AESCipher:
    def __init__(self, key):
        # Hashes the key to ensure it is 256 bits long
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, text):
        """Encrypts a given text (without timestamp)"""
        iv = get_random_bytes(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        ct_bytes = cipher.encrypt(pad(text.encode(), AES.block_size))
        encrypted_data = base64.b64encode(iv + ct_bytes).decode('utf-8')
        # Replace '/' with '_' to make the output URL-safe
        encrypted_data = encrypted_data.replace('/', '_').replace('+', '-')
        return encrypted_data

    def decrypt(self, encrypted_data):
        """Decrypts the given encrypted text"""
        encrypted_data = encrypted_data.replace('_', '/').replace('-', '+')
        data = base64.b64decode(encrypted_data)
        iv, ct = data[:AES.block_size], data[AES.block_size:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt.decode('utf-8')

    def encrypt_with_timecheck(self, text, expiry_minutes=5):
        """Encrypts the given text along with the current timestamp."""
        timestamp = datetime.utcnow().isoformat()  # Use UTC time
        payload = {'status': text, 'timestamp': timestamp}
        payload_str = json.dumps(payload)
        return self.encrypt(payload_str)

    def decrypt_with_timecheck(self, encrypted_data, expiry_minutes=5):
        """Decrypts the data and checks if the timestamp is still valid."""
        decrypted_data = self.decrypt(encrypted_data)

        try:
            payload = json.loads(decrypted_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid data format after decryption.")

        status = payload.get('status')
        timestamp = payload.get('timestamp')

        if not status or not timestamp:
            raise ValueError("Missing status or timestamp in the decrypted data.")

        timestamp_dt = datetime.fromisoformat(timestamp)  # Ensure it’s parsed correctly in UTC

        # Ensure both the timestamp and current time are in UTC
        if datetime.utcnow() - timestamp_dt > timedelta(minutes=expiry_minutes):
            raise ValueError("Token has expired.")

        return status

if __name__ == "__main__":
    secret_key = 'test_key'
    a = AESCipher(secret_key)

    # Encrypt and decrypt a simple status without timestamp validation
    enc = a.encrypt('SUCCESS')
    print(f"Encrypted: {enc}")
    dec = a.decrypt(enc)
    print(f"Decrypted: {dec}")

    # Encrypt with timestamp and validate expiry
    enc_with_timecheck = a.encrypt_with_timecheck('SUCCESS')
    print(f"Encrypted with timecheck: {enc_with_timecheck}")

    # Decrypt with timecheck and validate timestamp
    try:
        dec_with_timecheck = a.decrypt_with_timecheck(enc_with_timecheck)
        print(f"Decrypted with timecheck: {dec_with_timecheck}")
    except ValueError as e:
        print(f"Error: {e}")