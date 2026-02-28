# Per-Ontology Neo4j Connection: Python Worker Guide

This document describes how a **Python worker** should decrypt per-ontology Neo4j credentials and open a Neo4j connection so behavior matches the .NET API. The API stores Neo4j URI and username in plain text and the password **encrypted** in the database; the same encryption key must be used to decrypt in the worker.

---

## 1. Where the data is

- **Database:** PostgreSQL (same app DB as the API).
- **Table:** `app.ontologies`
- **Columns:**
  - `neo4j_uri` (text, nullable)
  - `neo4j_username` (text, nullable)
  - `neo4j_encrypted_password` (text, nullable)

Use **per-ontology Neo4j** only when, for that ontology row, **all three** of these are non-null and non-empty. Otherwise use the app default Neo4j (from config/env).

---

## 2. Encryption key (must match the API)

- **Config key:** `Neo4j:EncryptionKeyBase64`
- **Environment variable:** `NEO4J__ENCRYPTIONKEYBASE64` (double underscore; many Python configs map `Neo4j:EncryptionKeyBase64` from this)
- **Value:** Base64-encoded 32-byte key. Decode to bytes for AES:
  - `key = base64.b64decode(os.environ["NEO4J__ENCRYPTIONKEYBASE64"])` → must be 32 bytes.

The API encrypts with this key; the worker decrypts with the same key. If the key is missing or invalid when per-ontology Neo4j is needed, raise a clear error or fall back to the default Neo4j connection.

---

## 3. Cipher format (must match the .NET API)

- **Algorithm:** AES-256-CBC
- **Key:** 32 bytes (from base64-decoding the config value above)
- **Stored value:** Base64 string. After base64-decode:
  - **Bytes 0–15:** IV (16 bytes)
  - **Bytes 16–end:** AES-256-CBC ciphertext
- **Plaintext:** UTF-8 string (the Neo4j password). .NET uses PKCS7 padding.

---

## 4. Decryption in Python

Use the `cryptography` library (e.g. `from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes`) or `pycryptodome` so AES-256-CBC and padding match .NET.

**Steps:**

1. `combined = base64.b64decode(ontology_neo4j_encrypted_password)`
2. If `len(combined) < 16`: invalid → error or fall back to default Neo4j
3. `iv = combined[:16]`, `ciphertext = combined[16:]`
4. Decrypt with AES-256-CBC, key = 32-byte key, IV = `iv`. Remove PKCS7 padding (e.g. `PKCS7(128).unpad(...)` or equivalent)
5. `password = decrypted_bytes.decode("utf-8")`

**Example with `cryptography`:**

```python
from base64 import b64decode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

def decrypt_ontology_neo4j_password(encrypted_b64: str, key_b64: str) -> str:
    key = b64decode(key_b64)
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes (base64 decoded)")
    combined = b64decode(encrypted_b64)
    if len(combined) < 16:
        raise ValueError("Invalid encrypted value: too short")
    iv, ciphertext = combined[:16], combined[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return plain.decode("utf-8")
```

The worker must use the **same** key (from config/env) and the **same** layout (base64, first 16 bytes = IV, rest = ciphertext) as the .NET API.

---

## 5. Building the Neo4j connection in Python

- **Driver:** Official `neo4j` package: `neo4j.GraphDatabase.driver(uri, auth=(username, password))`
- **Parameters:** `uri` and `username` from the ontology row; `password` from the decryption step above
- For per-ontology Aura (one DB per instance), use the default database when creating sessions; no need to pass a database name unless you have a specific one

---

## 6. Flow in the Python worker

1. When the worker needs Neo4j for a given ontology (e.g. from a job/message):
   - Load that ontology from `app.ontologies` (e.g. by `ontology_id`).

2. If `neo4j_uri`, `neo4j_username`, and `neo4j_encrypted_password` are all set and non-empty:
   - Read the encryption key from config/env (`Neo4j:EncryptionKeyBase64` / `NEO4J__ENCRYPTIONKEYBASE64`).
   - Decrypt `neo4j_encrypted_password` as in section 4.
   - Create the Neo4j driver with `uri`, `username`, and the decrypted `password` as in section 5; use that driver for all Neo4j work for this ontology.

3. Otherwise:
   - Use the app default Neo4j (same env vars or config the rest of the app uses: e.g. `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`).

---

## 7. Summary for the Python agent

- **Key:** 32-byte key from base64 `Neo4j:EncryptionKeyBase64` (or `NEO4J__ENCRYPTIONKEYBASE64`).
- **Ciphertext:** Base64 string; decoded = IV (16 bytes) + AES-256-CBC ciphertext; decrypt with PKCS7 unpadding; result is UTF-8 Neo4j password.
- **Connection:** `neo4j.GraphDatabase.driver(uri, auth=(username, password))` with the decrypted password.
- **When:** Use this only when the ontology row has all three Neo4j fields set; otherwise use default Neo4j config.

---

## Reference (API implementation)

- **Encryption/decryption:** `src/Geodesic.App.Api/Services/OntologySecretProtection.cs`
- **Ontology entity:** `src/Geodesic.App.DataLayer/Entities/Ontology.cs` (Neo4jUri, Neo4jUsername, Neo4jEncryptedPassword)
- **Driver creation:** `src/Geodesic.App.Api/Graph/Neo4jGraphServiceFactory.cs` (CreateDriver, GetGraphServiceForOntologyAsync)
