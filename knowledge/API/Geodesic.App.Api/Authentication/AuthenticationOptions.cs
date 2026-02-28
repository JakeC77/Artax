namespace Geodesic.App.Api.Authentication;

public class AuthenticationOptions
{
    public const string SectionName = "Authentication";

    /// <summary>
    /// Microsoft Entra External ID tenant ID
    /// </summary>
    public string TenantId { get; set; } = string.Empty;

    /// <summary>
    /// Authority URL (e.g., https://{tenant}.ciamlogin.com/)
    /// </summary>
    public string Authority { get; set; } = string.Empty;

    /// <summary>
    /// API identifier/audience (the App ID URI or Application ID)
    /// </summary>
    public string Audience { get; set; } = string.Empty;

    /// <summary>
    /// Client IDs that are allowed to authenticate (for validation)
    /// Supports both React SPA and Python service client IDs
    /// </summary>
    public List<string> ValidClientIds { get; set; } = new();

    /// <summary>
    /// Whether to require HTTPS for token validation
    /// </summary>
    public bool RequireHttps { get; set; } = true;

    /// <summary>
    /// Token validation clock skew in seconds
    /// </summary>
    public int ClockSkewSeconds { get; set; } = 300;
}

