using System.Security.Cryptography;
using System.Text;
using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Services;

/// <summary>
/// Validates agent role access keys by hashing (same as at generation) and looking up by KeyHash.
/// </summary>
public sealed class AgentAccessKeyService : IAgentAccessKeyService
{
    private readonly IDbContextFactory<AppDbContext> _dbFactory;

    public AgentAccessKeyService(IDbContextFactory<AppDbContext> dbFactory)
    {
        _dbFactory = dbFactory;
    }

    public async Task<(AgentRole Role, AgentRoleAccessKey KeyMetadata)?> ValidateAccessKeyAsync(string rawKey, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(rawKey))
            return null;

        var keyHash = ComputeKeyHash(rawKey.Trim());
        await using var db = await _dbFactory.CreateDbContextAsync(ct);

        var keyEntity = await db.AgentRoleAccessKeys
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.KeyHash == keyHash, ct);
        if (keyEntity is null)
            return null;

        if (keyEntity.ExpiresAt.HasValue && keyEntity.ExpiresAt.Value < DateTimeOffset.UtcNow)
            return null;

        var role = await db.AgentRoles
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.AgentRoleId == keyEntity.AgentRoleId, ct);
        if (role is null)
            return null;

        return (role, keyEntity);
    }

    /// <summary>
    /// Same hashing as GenerateAgentRoleAccessKeyAsync: UTF-8 bytes of full secret, SHA256, hex lowercase.
    /// </summary>
    private static string ComputeKeyHash(string secretKey)
    {
        var hashBytes = SHA256.HashData(Encoding.UTF8.GetBytes(secretKey));
        return Convert.ToHexString(hashBytes).ToLowerInvariant();
    }
}
