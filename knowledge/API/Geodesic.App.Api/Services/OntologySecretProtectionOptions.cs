namespace Geodesic.App.Api.Services;

public sealed class OntologySecretProtectionOptions
{
    public const string SectionName = "Neo4j";

    /// <summary>
    /// Base64-encoded 32-byte key for AES-256. Required when using per-ontology Neo4j credentials.
    /// Generate with: Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
    /// </summary>
    public string? EncryptionKeyBase64 { get; set; }
}
