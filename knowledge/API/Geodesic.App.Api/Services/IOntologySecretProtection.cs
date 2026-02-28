namespace Geodesic.App.Api.Services;

/// <summary>
/// Encrypts/decrypts ontology-scoped secrets (e.g. Neo4j password) using an app-level key.
/// Key is from configuration (e.g. Neo4j:EncryptionKey) or Key Vault; never stored per ontology.
/// </summary>
public interface IOntologySecretProtection
{
    /// <summary>Encrypts plaintext; returns base64-encoded ciphertext (IV + payload).</summary>
    string Encrypt(string plaintext);

    /// <summary>Decrypts base64-encoded ciphertext produced by Encrypt.</summary>
    string Decrypt(string encryptedValue);
}
