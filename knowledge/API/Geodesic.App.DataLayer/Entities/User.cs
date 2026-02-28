
namespace Geodesic.App.DataLayer.Entities;
public class User
{
    public Guid UserId { get; set; }
    public Guid TenantId { get; set; }
    public string Subject { get; set; } = default!; // OIDC sub
    public string Email { get; set; } = default!;
    public string DisplayName { get; set; } = default!;
    public bool IsAdmin { get; set; } = false;
    public string Preferences { get; set; } = "{}"; // jsonb
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
