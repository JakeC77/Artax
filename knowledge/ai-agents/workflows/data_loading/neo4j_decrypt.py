"""
neo4j_decrypt.py - Decrypt Neo4j passwords encrypted by the .NET API.

This module decrypts Neo4j passwords that were encrypted using AES-256-CBC
by the .NET API. The encryption format matches the implementation in
src/Geodesic.App.Api/Services/OntologySecretProtection.cs
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding
    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    _CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("cryptography library not available. Neo4j password decryption will not work.")


def decrypt_ontology_neo4j_password(encrypted_b64: str, key_b64: str) -> Optional[str]:
    """
    Decrypt a Neo4j password that was encrypted by the .NET API.
    
    The encrypted value is a base64 string containing:
    - First 16 bytes: IV (Initialization Vector)
    - Remaining bytes: AES-256-CBC ciphertext with PKCS7 padding
    
    Args:
        encrypted_b64: Base64-encoded encrypted password string
        key_b64: Base64-encoded 32-byte encryption key
    
    Returns:
        Decrypted password as UTF-8 string, or None if decryption fails
    
    Raises:
        ValueError: If key or encrypted data format is invalid
    """
    if not _CRYPTOGRAPHY_AVAILABLE:
        logger.error("cryptography library not available. Cannot decrypt password.")
        return None
    
    try:
        # Decode the encryption key
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            raise ValueError(f"Key must be 32 bytes after base64 decode, got {len(key)} bytes")
        
        # Decode the encrypted value
        combined = base64.b64decode(encrypted_b64)
        if len(combined) < 16:
            raise ValueError(f"Invalid encrypted value: too short ({len(combined)} bytes, need at least 16)")
        
        # Extract IV (first 16 bytes) and ciphertext (rest)
        iv = combined[:16]
        ciphertext = combined[16:]
        
        # Create cipher and decrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt (this includes padding)
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove PKCS7 padding
        unpadder = padding.PKCS7(128).unpadder()
        plain = unpadder.update(padded) + unpadder.finalize()
        
        # Decode to UTF-8 string
        password = plain.decode("utf-8")
        
        logger.debug("Successfully decrypted Neo4j password")
        return password
        
    except Exception as e:
        logger.error(f"Failed to decrypt Neo4j password: {e}")
        raise ValueError(f"Password decryption failed: {str(e)}") from e
