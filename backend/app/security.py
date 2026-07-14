import os
import base64
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger("voice-agent")

# Path to local master key file
KEY_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".master.key")

def get_or_create_master_key() -> bytes:
    """
    Retrieves the master key from the environment or a local key file.
    If neither exists, a new key is generated and saved.
    """
    # 1. Check environment variable first
    env_key = os.getenv("DHWANI_MASTER_KEY")
    if env_key:
        try:
            # Verify if it is a valid Fernet key
            Fernet(env_key.encode())
            return env_key.encode()
        except Exception:
            logger.warning("DHWANI_MASTER_KEY environment variable is invalid. Falling back to local file.")

    # 2. Check local key file
    if os.path.exists(KEY_FILE_PATH):
        try:
            with open(KEY_FILE_PATH, "rb") as f:
                key = f.read().strip()
                # Verify key
                Fernet(key)
                return key
        except Exception as e:
            logger.error(f"Failed to read existing master key file: {e}")

    # 3. Generate a new key if not found
    new_key = Fernet.generate_key()
    try:
        with open(KEY_FILE_PATH, "wb") as f:
            f.write(new_key)
        # Set file permissions if on unix-like OS (best practice)
        if hasattr(os, "chmod"):
            os.chmod(KEY_FILE_PATH, 0o600)
        logger.info(f"Generated new master key and saved to {KEY_FILE_PATH}")
    except Exception as e:
        logger.error(f"Failed to save generated master key to file: {e}")
        
    return new_key

# Initialize Fernet cipher
try:
    _master_key = get_or_create_master_key()
    cipher = Fernet(_master_key)
except Exception as err:
    logger.critical(f"Failed to initialize encryption subsystem: {err}")
    cipher = None

def encrypt_key(plain_text: str) -> str:
    """
    Encrypts a plain text API key.
    """
    if not cipher:
        raise RuntimeError("Encryption system is not initialized.")
    if not plain_text:
        return ""
    encrypted_bytes = cipher.encrypt(plain_text.encode())
    return encrypted_bytes.decode()

def decrypt_key(encrypted_text: str) -> str:
    """
    Decrypts an encrypted API key.
    """
    if not cipher:
        raise RuntimeError("Decryption system is not initialized.")
    if not encrypted_text:
        return ""
    decrypted_bytes = cipher.decrypt(encrypted_text.encode())
    return decrypted_bytes.decode()

async def get_api_key_from_db(provider: str) -> str:
    """
    Retrieves and decrypts the API key for a provider from the database.
    """
    try:
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models import APIKey
        async with AsyncSessionLocal() as session:
            stmt = select(APIKey).where(APIKey.provider == provider)
            result = await session.execute(stmt)
            api_key_record = result.scalar_one_or_none()
            if api_key_record:
                return decrypt_key(api_key_record.encrypted_key)
    except Exception as e:
        logger.error(f"Error fetching API key for {provider} from database: {e}")
    return ""

