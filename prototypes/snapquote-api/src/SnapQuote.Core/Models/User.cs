namespace SnapQuote.Core.Models;

public class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string PhoneNumber { get; set; } = string.Empty;
    public string? BusinessName { get; set; }
    public string? LogoUrl { get; set; }
    public string? Email { get; set; }
    public UserTier Tier { get; set; } = UserTier.Free;
    public int QuotesThisMonth { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? LastActiveAt { get; set; }
}

public enum UserTier
{
    Free,      // 5 quotes/month
    Pro,       // Unlimited
    Enterprise // Custom
}
