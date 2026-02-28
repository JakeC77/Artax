using System.Security.Claims;
using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Geodesic.App.Api.Authentication;

public interface IUserProvisioningService
{
    /// <summary>
    /// Provisions or updates a user from JWT claims.
    /// Returns the User entity and whether it was newly created.
    /// </summary>
    Task<(User user, bool wasCreated)> ProvisionUserAsync(ClaimsPrincipal principal, CancellationToken ct = default);
}

public class UserProvisioningService : IUserProvisioningService
{
    private readonly IDbContextFactory<AppDbContext> _dbFactory;
    private readonly ILogger<UserProvisioningService> _logger;

    public UserProvisioningService(
        IDbContextFactory<AppDbContext> dbFactory,
        ILogger<UserProvisioningService> logger)
    {
        _dbFactory = dbFactory;
        _logger = logger;
    }

    public async Task<(User user, bool wasCreated)> ProvisionUserAsync(ClaimsPrincipal principal, CancellationToken ct = default)
    {
        // Log all available claims for debugging
        var allClaims = principal.Claims.Select(c => $"{c.Type}={c.Value}").ToList();
        _logger.LogDebug("Available claims in token: {Claims}", string.Join(", ", allClaims));

        // Extract claims - try multiple claim name variations
        var subject = principal.FindFirstValue("sub") 
            ?? principal.FindFirstValue(ClaimTypes.NameIdentifier)
            ?? principal.FindFirstValue("oid"); // Object ID as fallback

        // Try multiple claim names for email
        var email = principal.FindFirstValue("email") 
            ?? principal.FindFirstValue(ClaimTypes.Email)
            ?? principal.FindFirstValue("preferred_username") // Common in Entra External ID
            ?? principal.FindFirstValue("upn") // User Principal Name
            ?? principal.FindFirstValue("unique_name");

        // Try multiple claim names for display name
        var displayName = principal.FindFirstValue("name") 
            ?? principal.FindFirstValue(ClaimTypes.Name)
            ?? principal.FindFirstValue("given_name") + " " + principal.FindFirstValue("family_name")
            ?? principal.FindFirstValue("preferred_username")
            ?? email
            ?? "Unknown User";

        // Clean up display name (remove extra spaces)
        displayName = displayName?.Trim() ?? "Unknown User";

        // Extract tenant ID
        var tenantIdStr = principal.FindFirstValue("tid") 
            ?? principal.FindFirstValue("http://schemas.microsoft.com/identity/claims/tenantid")
            ?? principal.FindFirstValue("tenantid");

        if (string.IsNullOrWhiteSpace(subject))
        {
            _logger.LogError("Missing 'sub' claim. Available claims: {Claims}", string.Join(", ", allClaims));
            throw new InvalidOperationException($"JWT token missing 'sub' claim. Available claim types: {string.Join(", ", principal.Claims.Select(c => c.Type).Distinct())}");
        }

        // Email is optional - we can use preferred_username or subject as fallback
        // Note: preferred_username is already checked above, but if it's still empty, use fallback
        if (string.IsNullOrWhiteSpace(email))
        {
            // Final fallback - use subject with domain
            email = $"{subject}@external.local";
            
            _logger.LogWarning(
                "JWT token missing 'email' and 'preferred_username' claims. Using fallback: {Email}. Available claims: {Claims}", 
                email, 
                string.Join(", ", allClaims));
        }
        else
        {
            _logger.LogInformation("Using email from claim: {Email}", email);
        }

        if (string.IsNullOrWhiteSpace(tenantIdStr) || !Guid.TryParse(tenantIdStr, out var tenantId))
        {
            _logger.LogError("Missing or invalid 'tid' claim. Value: {TenantIdStr}, Available claims: {Claims}", 
                tenantIdStr, 
                string.Join(", ", allClaims));
            throw new InvalidOperationException($"JWT token missing or invalid 'tid' claim. Available claim types: {string.Join(", ", principal.Claims.Select(c => c.Type).Distinct())}");
        }

        await using var db = await _dbFactory.CreateDbContextAsync(ct);

        // Check if user already exists
        var existingUser = await db.Users
            .FirstOrDefaultAsync(u => u.TenantId == tenantId && u.Subject == subject, ct);

        if (existingUser != null)
        {
            // Update existing user if needed
            var updated = false;
            if (existingUser.Email != email)
            {
                existingUser.Email = email;
                updated = true;
            }
            if (existingUser.DisplayName != displayName)
            {
                existingUser.DisplayName = displayName;
                updated = true;
            }
            if (updated)
            {
                existingUser.UpdatedAt = DateTimeOffset.UtcNow;
                await db.SaveChangesAsync(ct);
                _logger.LogInformation("Updated user {UserId} (Subject: {Subject}, Email: {Email})", existingUser.UserId, subject, email);
            }
            return (existingUser, false);
        }

        // Create new user
        var newUser = new User
        {
            UserId = Guid.NewGuid(),
            TenantId = tenantId,
            Subject = subject,
            Email = email,
            DisplayName = displayName,
            IsAdmin = false,
            Preferences = "{}",
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };

        db.Users.Add(newUser);
        await db.SaveChangesAsync(ct);

        _logger.LogInformation("Created new user {UserId} (Subject: {Subject}, Email: {Email}, TenantId: {TenantId})",
            newUser.UserId, subject, email, tenantId);

        return (newUser, true);
    }
}

