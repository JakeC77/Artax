using System.Security.Cryptography;
using Microsoft.Extensions.Options;

namespace Geodesic.App.Api.Services;

public sealed class OntologySecretProtection : IOntologySecretProtection
{
    private readonly byte[]? _key;
    private const int AesBlockBytes = 16;
    private const int KeySizeBytes = 32;

    public OntologySecretProtection(IOptions<OntologySecretProtectionOptions> options)
    {
        var keyB64 = options.Value.EncryptionKeyBase64;
        if (string.IsNullOrWhiteSpace(keyB64))
        {
            _key = null;
            return;
        }
        try
        {
            var key = Convert.FromBase64String(keyB64.Trim());
            if (key.Length != KeySizeBytes)
                throw new InvalidOperationException($"Neo4j:EncryptionKeyBase64 must be a 32-byte key (base64). Got {key.Length} bytes.");
            _key = key;
        }
        catch (FormatException ex)
        {
            throw new InvalidOperationException("Neo4j:EncryptionKeyBase64 must be valid base64.", ex);
        }
    }

    private static void ThrowKeyRequired() =>
        throw new InvalidOperationException(
            "Neo4j:EncryptionKeyBase64 is required when using per-ontology Neo4j credentials. " +
            "Add to config and generate with: Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))");

    public string Encrypt(string plaintext)
    {
        if (string.IsNullOrEmpty(plaintext)) return string.Empty;
        if (_key is null) ThrowKeyRequired();
        var iv = RandomNumberGenerator.GetBytes(AesBlockBytes);
        var plain = System.Text.Encoding.UTF8.GetBytes(plaintext);
        using var aes = Aes.Create();
        aes.Key = _key;
        aes.IV = iv;
        using var enc = aes.CreateEncryptor();
        var cipher = enc.TransformFinalBlock(plain, 0, plain.Length);
        var combined = new byte[iv.Length + cipher.Length];
        Buffer.BlockCopy(iv, 0, combined, 0, iv.Length);
        Buffer.BlockCopy(cipher, 0, combined, iv.Length, cipher.Length);
        return Convert.ToBase64String(combined);
    }

    public string Decrypt(string encryptedValue)
    {
        if (string.IsNullOrEmpty(encryptedValue)) return string.Empty;
        var combined = Convert.FromBase64String(encryptedValue);
        if (combined.Length < AesBlockBytes)
            throw new InvalidOperationException("Invalid encrypted value: too short.");
        var iv = new byte[AesBlockBytes];
        var cipher = new byte[combined.Length - AesBlockBytes];
        Buffer.BlockCopy(combined, 0, iv, 0, AesBlockBytes);
        Buffer.BlockCopy(combined, AesBlockBytes, cipher, 0, cipher.Length);
        using var aes = Aes.Create();
        aes.Key = _key;
        aes.IV = iv;
        using var dec = aes.CreateDecryptor();
        var plain = dec.TransformFinalBlock(cipher, 0, cipher.Length);
        return System.Text.Encoding.UTF8.GetString(plain);
    }
}
