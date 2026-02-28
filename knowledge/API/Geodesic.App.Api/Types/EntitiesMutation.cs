using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using HotChocolate;
using HotChocolate.Types;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using Geodesic.App.Api.Storage;
using Geodesic.App.Api.Services;
using Geodesic.App.Api.Graph;
using Geodesic.App.Api.Messaging;
using Geodesic.App.Api.Models;
using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.Extensions.Options;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class EntitiesMutation
{
    // ---------------- Tenants ----------------
    public async Task<Guid> CreateTenantAsync(
        string name,
        string? region,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Tenant
        {
            TenantId = Guid.NewGuid(),
            Name = name,
            Region = string.IsNullOrWhiteSpace(region) ? "us" : region!
        };
        db.Tenants.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.TenantId;
    }

    public async Task<bool> UpdateTenantAsync(
        Guid tenantId,
        string? name,
        string? region,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Tenants.FirstOrDefaultAsync(x => x.TenantId == tenantId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (region is not null) entity.Region = region;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteTenantAsync(Guid tenantId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Tenants.FirstOrDefaultAsync(x => x.TenantId == tenantId, ct);
        if (entity is null) return false;
        db.Tenants.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Roles ----------------
    public async Task<bool> UpsertRoleAsync(
        Guid tenantId,
        string roleName,
        string? description,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Roles.FirstOrDefaultAsync(x => x.TenantId == tenantId && x.RoleName == roleName, ct);
        if (entity is null)
        {
            entity = new Role { TenantId = tenantId, RoleName = roleName, Description = description };
            db.Roles.Add(entity);
        }
        else
        {
            entity.Description = description;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteRoleAsync(Guid tenantId, string roleName, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Roles.FirstOrDefaultAsync(x => x.TenantId == tenantId && x.RoleName == roleName, ct);
        if (entity is null) return false;
        db.Roles.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Users ----------------
    public async Task<Guid> CreateUserAsync(
        Guid tenantId,
        string subject,
        string email,
        string displayName,
        bool? isAdmin,
        string? preferences,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new User
        {
            UserId = Guid.NewGuid(),
            TenantId = tenantId,
            Subject = subject,
            Email = email,
            DisplayName = displayName,
            IsAdmin = isAdmin ?? false,
            Preferences = preferences ?? "{}"
        };
        db.Users.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.UserId;
    }

    public async Task<bool> UpdateUserAsync(
        Guid userId,
        string? subject,
        string? email,
        string? displayName,
        bool? isAdmin,
        string? preferences,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Users.FirstOrDefaultAsync(x => x.UserId == userId, ct);
        if (entity is null) return false;
        if (subject is not null) entity.Subject = subject;
        if (email is not null) entity.Email = email;
        if (displayName is not null) entity.DisplayName = displayName;
        if (isAdmin.HasValue) entity.IsAdmin = isAdmin.Value;
        if (preferences is not null) entity.Preferences = preferences;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- AI Teams ----------------
    public async Task<Guid> CreateAITeamAsync(
        Guid workspaceId,
        string name,
        string? description,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new AITeam
        {
            AITeamId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            Name = name,
            Description = description,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };
        db.AITeams.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.AITeamId;
    }

    public async Task<bool> UpdateAITeamAsync(
        Guid aiTeamId,
        string? name,
        string? description,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AITeams.FirstOrDefaultAsync(x => x.AITeamId == aiTeamId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteAITeamAsync(
        Guid aiTeamId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AITeams.FirstOrDefaultAsync(x => x.AITeamId == aiTeamId, ct);
        if (entity is null) return false;
        db.AITeams.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- AITeamMembers ----------------
    public async Task<Guid> CreateAITeamMemberAsync(
        Guid aiTeamId,
        string agentId,
        string name,
        string? description,
        string role,
        string? systemPrompt,
        string? model,
        decimal? temperature,
        int? maxTokens,
        string[]? tools,
        string[]? expertise,
        string? communicationStyle,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new AITeamMember
        {
            AITeamMemberId = Guid.NewGuid(),
            AITeamId = aiTeamId,
            AgentId = agentId,
            Name = name,
            Description = description,
            Role = string.IsNullOrWhiteSpace(role) ? "worker" : role,
            SystemPrompt = systemPrompt,
            Model = model,
            Temperature = temperature,
            MaxTokens = maxTokens,
            Tools = tools ?? Array.Empty<string>(),
            Expertise = expertise ?? Array.Empty<string>(),
            CommunicationStyle = communicationStyle,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };
        db.AITeamMembers.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.AITeamMemberId;
    }

    public async Task<bool> UpdateAITeamMemberAsync(
        Guid aiTeamMemberId,
        Guid? aiTeamId,
        string? agentId,
        string? name,
        string? description,
        string? role,
        string? systemPrompt,
        string? model,
        decimal? temperature,
        int? maxTokens,
        string[]? tools,
        string[]? expertise,
        string? communicationStyle,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AITeamMembers.FirstOrDefaultAsync(x => x.AITeamMemberId == aiTeamMemberId, ct);
        if (entity is null) return false;
        if (aiTeamId.HasValue) entity.AITeamId = aiTeamId.Value;
        if (agentId is not null) entity.AgentId = agentId;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        if (role is not null) entity.Role = role;
        if (systemPrompt is not null) entity.SystemPrompt = systemPrompt;
        if (model is not null) entity.Model = model;
        if (temperature.HasValue) entity.Temperature = temperature;
        if (maxTokens.HasValue) entity.MaxTokens = maxTokens;
        if (tools is not null) entity.Tools = tools;
        if (expertise is not null) entity.Expertise = expertise;
        if (communicationStyle is not null) entity.CommunicationStyle = communicationStyle;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteAITeamMemberAsync(
        Guid aiTeamMemberId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AITeamMembers.FirstOrDefaultAsync(x => x.AITeamMemberId == aiTeamMemberId, ct);
        if (entity is null) return false;
        db.AITeamMembers.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteUserAsync(Guid userId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Users.FirstOrDefaultAsync(x => x.UserId == userId, ct);
        if (entity is null) return false;
        db.Users.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- UserRoles ----------------
    public async Task<bool> AddUserRoleAsync(Guid userId, string roleName, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var existing = await db.UserRoles.FirstOrDefaultAsync(x => x.UserId == userId && x.RoleName == roleName, ct);
        if (existing is not null) return true;
        db.UserRoles.Add(new UserRole { UserId = userId, RoleName = roleName });
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> RemoveUserRoleAsync(Guid userId, string roleName, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.UserRoles.FirstOrDefaultAsync(x => x.UserId == userId && x.RoleName == roleName, ct);
        if (entity is null) return false;
        db.UserRoles.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Workspaces ----------------
    public async Task<Guid> CreateWorkspaceAsync(
        string name,
        string? description,
        string? intent,
        Guid? companyId,
        Guid? ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] Microsoft.Extensions.Logging.ILogger<EntitiesMutation> logger,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Resolve tenant from claims or header for clearer errors under RLS
        var http = accessor.HttpContext;
        Guid tenantId = Guid.Empty;
        try
        {
            var tidStr = http?.User?.FindFirst("tid")?.Value ?? http?.Request.Headers["X-Tenant-Id"].ToString();
            if (!Guid.TryParse(tidStr, out tenantId))
            {
                logger.LogWarning("createWorkspace: missing or invalid tenant id. name={Name}", name);
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Tenant id missing or invalid for createWorkspace")
                    .SetCode("TENANT_REQUIRED")
                    .Build());
            }
        }
        catch (GraphQLException)
        {
            throw;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "createWorkspace: unexpected error while resolving tenant id. name={Name}", name);
            throw;
        }

        // Always resolve ownerUserId from JWT claims to ensure proof of who created it
        var subject = http?.User?.FindFirst("sub")?.Value
            ?? http?.User?.FindFirst(ClaimTypes.NameIdentifier)?.Value
            ?? http?.User?.FindFirst("oid")?.Value;

        if (string.IsNullOrWhiteSpace(subject))
        {
            logger.LogWarning("createWorkspace: missing 'sub' claim. name={Name}", name);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("User subject claim missing or invalid. Authentication is required to create a workspace.")
                .SetCode("USER_REQUIRED")
                .Build());
        }

        // Look up user in database using TenantId + Subject
        var user = await db.Users
            .FirstOrDefaultAsync(u => u.Subject == subject, ct);

        if (user == null)
        {
            logger.LogWarning("createWorkspace: user not found. tenantId={TenantId}, subject={Subject}, name={Name}", tenantId, subject, name);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("User not found. Please ensure your user account is provisioned.")
                .SetCode("USER_NOT_FOUND")
                .Build());
        }

        var ownerUserId = user.UserId;
        logger.LogInformation("createWorkspace: resolved ownerUserId={OwnerUserId} from JWT subject={Subject}, name={Name}", ownerUserId, subject, name);

        var ws = new Workspace
        {
            WorkspaceId = Guid.NewGuid(),
            TenantId = tenantId,
            CompanyId = companyId,
            OntologyId = ontologyId,
            OwnerUserId = ownerUserId,
            Name = name,
            Description = description,
            Intent = intent,
            Visibility = "private",
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };
        db.Workspaces.Add(ws);
        await db.SaveChangesAsync(ct);

        return ws.WorkspaceId;
    }

    public async Task<bool> UpdateWorkspaceAsync(
        Guid workspaceId,
        string? name,
        string? description,
        string? visibility,
        DateTimeOffset? baseSnapshotTs,
        string? intent,
        string? state,
        Optional<Guid?> companyId,
        Optional<Guid?> ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Workspaces.FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        if (intent is not null) entity.Intent = intent;
        if (visibility is not null) entity.Visibility = visibility;
        if (baseSnapshotTs.HasValue) entity.BaseSnapshotTs = baseSnapshotTs.Value;
        if (state is not null) entity.State = state;
        if (companyId.HasValue) entity.CompanyId = companyId.Value;
        if (ontologyId.HasValue) entity.OntologyId = ontologyId.Value;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteWorkspaceAsync(Guid workspaceId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Workspaces.FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId, ct);
        if (entity is null) return false;
        db.Workspaces.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Workspace Members ----------------
    public async Task<bool> UpsertWorkspaceMemberAsync(
        Guid workspaceId,
        Guid userId,
        string? role,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceMembers.FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId && x.UserId == userId, ct);
        if (entity is null)
        {
            entity = new WorkspaceMember { WorkspaceId = workspaceId, UserId = userId, Role = role ?? "viewer" };
            db.WorkspaceMembers.Add(entity);
        }
        else
        {
            if (role is not null) entity.Role = role;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> RemoveWorkspaceMemberAsync(Guid workspaceId, Guid userId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceMembers.FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId && x.UserId == userId, ct);
        if (entity is null) return false;
        db.WorkspaceMembers.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Workspace Items (generic CRUD) ----------------
    public async Task<bool> UpsertWorkspaceItemAsync(
        Guid workspaceId,
        string graphNodeId,
        string? graphEdgeId,
        string[]? labels,
        Guid? pinnedBy,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceItems.FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId && x.GraphNodeId == graphNodeId && x.GraphEdgeId == graphEdgeId, ct);
        if (entity is null)
        {
            entity = new WorkspaceItem {
                WorkspaceId = workspaceId,
                GraphNodeId = graphNodeId,
                GraphEdgeId = graphEdgeId,
                Labels = labels ?? Array.Empty<string>(),
                PinnedBy = pinnedBy ?? Guid.Empty,
                PinnedAt = DateTimeOffset.UtcNow
            };
            db.WorkspaceItems.Add(entity);
        }
        else
        {
            if (labels is not null) entity.Labels = labels;
            if (pinnedBy.HasValue) entity.PinnedBy = pinnedBy.Value;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteWorkspaceItemAsync(Guid workspaceId, string graphNodeId, string? graphEdgeId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceItems.FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId && x.GraphNodeId == graphNodeId && x.GraphEdgeId == graphEdgeId, ct);
        if (entity is null) return false;
        db.WorkspaceItems.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Overlay Changesets ----------------
    public async Task<Guid> CreateOverlayChangesetAsync(
        Guid workspaceId,
        Guid createdBy,
        string? status,
        string? comment,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new OverlayChangeset {
            ChangesetId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            CreatedBy = createdBy,
            Status = status ?? "draft",
            Comment = comment,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };
        db.OverlayChangesets.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.ChangesetId;
    }

    public async Task<bool> UpdateOverlayChangesetAsync(Guid changesetId, string? status, string? comment, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.OverlayChangesets.FirstOrDefaultAsync(x => x.ChangesetId == changesetId, ct);
        if (entity is null) return false;
        if (status is not null) entity.Status = status;
        if (comment is not null) entity.Comment = comment;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteOverlayChangesetAsync(Guid changesetId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.OverlayChangesets.FirstOrDefaultAsync(x => x.ChangesetId == changesetId, ct);
        if (entity is null) return false;
        db.OverlayChangesets.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Overlay Node Patch ----------------
    public async Task<bool> UpsertOverlayNodePatchAsync(Guid changesetId, string graphNodeId, string? op, string? patch, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.OverlayNodePatches.FirstOrDefaultAsync(x => x.ChangesetId == changesetId && x.GraphNodeId == graphNodeId, ct);
        if (entity is null)
        {
            entity = new OverlayNodePatch { ChangesetId = changesetId, GraphNodeId = graphNodeId, Op = op ?? "upsert", Patch = patch ?? "{}" };
            db.OverlayNodePatches.Add(entity);
        }
        else
        {
            if (op is not null) entity.Op = op;
            if (patch is not null) entity.Patch = patch;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteOverlayNodePatchAsync(Guid changesetId, string graphNodeId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.OverlayNodePatches.FirstOrDefaultAsync(x => x.ChangesetId == changesetId && x.GraphNodeId == graphNodeId, ct);
        if (entity is null) return false;
        db.OverlayNodePatches.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Overlay Edge Patch ----------------
    public async Task<bool> UpsertOverlayEdgePatchAsync(Guid changesetId, string graphEdgeId, string? op, string? patch, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.OverlayEdgePatches.FirstOrDefaultAsync(x => x.ChangesetId == changesetId && x.GraphEdgeId == graphEdgeId, ct);
        if (entity is null)
        {
            entity = new OverlayEdgePatch { ChangesetId = changesetId, GraphEdgeId = graphEdgeId, Op = op ?? "upsert", Patch = patch ?? "{}" };
            db.OverlayEdgePatches.Add(entity);
        }
        else
        {
            if (op is not null) entity.Op = op;
            if (patch is not null) entity.Patch = patch;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteOverlayEdgePatchAsync(Guid changesetId, string graphEdgeId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.OverlayEdgePatches.FirstOrDefaultAsync(x => x.ChangesetId == changesetId && x.GraphEdgeId == graphEdgeId, ct);
        if (entity is null) return false;
        db.OverlayEdgePatches.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Scenarios ----------------
    public async Task<Guid> CreateScenarioAsync(
        Guid workspaceId,
        string name,
        string? headerText,
        string? mainText,
        Guid? relatedChangesetId,
        Guid createdBy,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Scenario
        {
            ScenarioId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            Name = name,
            HeaderText = headerText,
            MainText = mainText,
            RelatedChangesetId = relatedChangesetId,
            CreatedBy = createdBy,
            CreatedAt = DateTimeOffset.UtcNow
        };
        db.Scenarios.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.ScenarioId;
    }

    public async Task<bool> UpdateScenarioAsync(
        Guid scenarioId,
        string? name,
        string? headerText,
        string? mainText,
        Guid? relatedChangesetId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Scenarios.FirstOrDefaultAsync(x => x.ScenarioId == scenarioId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (headerText is not null) entity.HeaderText = headerText;
        if (mainText is not null) entity.MainText = mainText;
        if (relatedChangesetId.HasValue) entity.RelatedChangesetId = relatedChangesetId;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteScenarioAsync(Guid scenarioId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Scenarios.FirstOrDefaultAsync(x => x.ScenarioId == scenarioId, ct);
        if (entity is null) return false;
        db.Scenarios.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Scenario Runs ----------------
    public async Task<Guid> CreateScenarioRunAsync(
        Guid scenarioId,
        string engine,
        string? inputs,
        string? status,
        string? prompt,
        string? title,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] IHttpContextAccessor accessor,
        [Service] Microsoft.Extensions.Logging.ILogger<EntitiesMutation> logger,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Resolve tenant from claims or header for clearer errors under RLS
        Guid tenantId = Guid.Empty;
        try
        {
            var http = accessor.HttpContext;
            var tidStr = http?.User?.FindFirst("tid")?.Value ?? http?.Request.Headers["X-Tenant-Id"].ToString();
            if (!Guid.TryParse(tidStr, out tenantId))
            {
                logger.LogWarning("createScenarioRun: missing or invalid tenant id. scenarioId={ScenarioId}, engine={Engine}", scenarioId, engine);
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Tenant id missing or invalid for createScenarioRun")
                    .SetCode("TENANT_REQUIRED")
                    .Build());
            }
        }
        catch (GraphQLException)
        {
            throw;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "createScenarioRun: unexpected error while resolving tenant id. scenarioId={ScenarioId}, engine={Engine}", scenarioId, engine);
            throw;
        }

        // Validate scenario exists (provides clearer feedback than DB-level errors)
        var scenario = await db.Scenarios.AsNoTracking().FirstOrDefaultAsync(x => x.ScenarioId == scenarioId, ct);
        if (scenario == null)
        {
            logger.LogWarning("createScenarioRun: scenario not found. scenarioId={ScenarioId}", scenarioId);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Scenario not found")
                .SetCode("SCENARIO_NOT_FOUND")
                .Build());
        }
        var entity = new ScenarioRun {
            RunId = Guid.NewGuid(),
            WorkspaceId = scenario.WorkspaceId,
            ScenarioId = scenarioId,
            Title = title,
            Engine = engine,
            Prompt = prompt,
            Inputs = inputs ?? "{}",
            Status = status ?? "queued",
            StartedAt = DateTimeOffset.UtcNow
        };
        db.ScenarioRuns.Add(entity);
        await db.SaveChangesAsync(ct);

        try
        {
            var payload = new WorkflowEventPayload
            {
                RunId = entity.RunId,
                TenantId = tenantId,
                WorkspaceId = scenario.WorkspaceId,
                ScenarioId = scenarioId,
                WorkflowId = engine,
                Engine = engine,
                Inputs = entity.Inputs,
                Prompt = entity.Prompt,
                Status = entity.Status,
                RequestedAt = DateTimeOffset.UtcNow,
                RelatedChangesetId = scenario.RelatedChangesetId
            };
            await dispatcher.DispatchAsync(payload, ct);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "createScenarioRun: failed to dispatch workflow. runId={RunId}, scenarioId={ScenarioId}", entity.RunId, scenarioId);
        }

        return entity.RunId;
    }

    public async Task<Guid> CreateWorkspaceRunAsync(
        Guid workspaceId,
        Guid? scenarioId,
        string engine,
        string? inputs,
        string? status,
        string? prompt,
        string? title,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] IHttpContextAccessor accessor,
        [Service] Microsoft.Extensions.Logging.ILogger<EntitiesMutation> logger,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Resolve tenant from claims or header for clearer errors under RLS
        Guid tenantId = Guid.Empty;
        try
        {
            var http = accessor.HttpContext;
            var tidStr = http?.User?.FindFirst("tid")?.Value ?? http?.Request.Headers["X-Tenant-Id"].ToString();
            if (!Guid.TryParse(tidStr, out tenantId))
            {
                logger.LogWarning("createWorkspaceRun: missing or invalid tenant id. workspaceId={WorkspaceId}, engine={Engine}", workspaceId, engine);
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Tenant id missing or invalid for createWorkspaceRun")
                    .SetCode("TENANT_REQUIRED")
                    .Build());
            }
        }
        catch (GraphQLException)
        {
            throw;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "createWorkspaceRun: unexpected error while resolving tenant id. workspaceId={WorkspaceId}, engine={Engine}", workspaceId, engine);
            throw;
        }

        // Validate workspace exists
        var workspaceExists = await db.Workspaces.AsNoTracking().AnyAsync(x => x.WorkspaceId == workspaceId, ct);
        if (!workspaceExists)
        {
            logger.LogWarning("createWorkspaceRun: workspace not found. workspaceId={WorkspaceId}", workspaceId);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Workspace not found")
                .SetCode("WORKSPACE_NOT_FOUND")
                .Build());
        }

        // If scenarioId is provided, validate it exists and belongs to the workspace
        Guid? relatedChangesetId = null;
        if (scenarioId.HasValue)
        {
            var scenario = await db.Scenarios.AsNoTracking().FirstOrDefaultAsync(x => x.ScenarioId == scenarioId.Value, ct);
            if (scenario == null)
            {
                logger.LogWarning("createWorkspaceRun: scenario not found. scenarioId={ScenarioId}", scenarioId.Value);
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Scenario not found")
                    .SetCode("SCENARIO_NOT_FOUND")
                    .Build());
            }
            if (scenario.WorkspaceId != workspaceId)
            {
                logger.LogWarning("createWorkspaceRun: scenario does not belong to workspace. scenarioId={ScenarioId}, workspaceId={WorkspaceId}, scenarioWorkspaceId={ScenarioWorkspaceId}", scenarioId.Value, workspaceId, scenario.WorkspaceId);
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Scenario does not belong to the specified workspace")
                    .SetCode("SCENARIO_WORKSPACE_MISMATCH")
                    .Build());
            }
            relatedChangesetId = scenario.RelatedChangesetId;
        }

        var entity = new ScenarioRun {
            RunId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            ScenarioId = scenarioId,
            Title = title,
            Engine = engine,
            Prompt = prompt,
            Inputs = inputs ?? "{}",
            Status = status ?? "queued",
            StartedAt = DateTimeOffset.UtcNow
        };
        db.ScenarioRuns.Add(entity);
        await db.SaveChangesAsync(ct);

        try
        {
            var payload = new WorkflowEventPayload
            {
                RunId = entity.RunId,
                TenantId = tenantId,
                WorkspaceId = workspaceId,
                ScenarioId = scenarioId ?? Guid.Empty,
                WorkflowId = engine,
                Engine = engine,
                Inputs = entity.Inputs,
                Prompt = entity.Prompt,
                Status = entity.Status,
                RequestedAt = DateTimeOffset.UtcNow,
                RelatedChangesetId = relatedChangesetId
            };
            await dispatcher.DispatchAsync(payload, ct);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "createWorkspaceRun: failed to dispatch workflow. runId={RunId}, workspaceId={WorkspaceId}", entity.RunId, workspaceId);
        }

        return entity.RunId;
    }

    public async Task<bool> UpdateScenarioRunAsync(
        Guid runId,
        string? status,
        string? outputs,
        string? errorMessage,
        string? artifactsUri,
        string? prompt,
        string? title,
        DateTimeOffset? startedAt,
        DateTimeOffset? finishedAt,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScenarioRuns.FirstOrDefaultAsync(x => x.RunId == runId, ct);
        if (entity is null) return false;
        if (status is not null) entity.Status = status;
        if (outputs is not null) entity.Outputs = outputs;
        if (errorMessage is not null) entity.ErrorMessage = errorMessage;
        if (artifactsUri is not null) entity.ArtifactsUri = artifactsUri;
        if (prompt is not null) entity.Prompt = prompt;
        if (title is not null) entity.Title = title;
        if (startedAt.HasValue) entity.StartedAt = startedAt;
        if (finishedAt.HasValue) entity.FinishedAt = finishedAt;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteScenarioRunAsync(Guid runId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScenarioRuns.FirstOrDefaultAsync(x => x.RunId == runId, ct);
        if (entity is null) return false;
        db.ScenarioRuns.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Insights ----------------
    public async Task<Guid> CreateInsightAsync(
        Guid tenantId,
        Guid? workspaceId,
        string severity,
        string title,
        string body,
        string[]? relatedGraphIds,
        string? evidenceRefs,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Insight {
            InsightId = Guid.NewGuid(),
            TenantId = tenantId,
            WorkspaceId = workspaceId,
            Severity = string.IsNullOrWhiteSpace(severity) ? "info" : severity,
            Title = title,
            Body = body,
            RelatedGraphIds = relatedGraphIds ?? Array.Empty<string>(),
            EvidenceRefs = evidenceRefs ?? "[]",
            GeneratedAt = DateTimeOffset.UtcNow
        };
        db.Insights.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.InsightId;
    }

    public async Task<bool> UpdateInsightAsync(
        Guid insightId,
        string? severity,
        string? title,
        string? body,
        string[]? relatedGraphIds,
        string? evidenceRefs,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Insights.FirstOrDefaultAsync(x => x.InsightId == insightId, ct);
        if (entity is null) return false;
        if (severity is not null) entity.Severity = severity;
        if (title is not null) entity.Title = title;
        if (body is not null) entity.Body = body;
        if (relatedGraphIds is not null) entity.RelatedGraphIds = relatedGraphIds;
        if (evidenceRefs is not null) entity.EvidenceRefs = evidenceRefs;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteInsightAsync(Guid insightId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Insights.FirstOrDefaultAsync(x => x.InsightId == insightId, ct);
        if (entity is null) return false;
        db.Insights.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Workspace Analyses ----------------
    public async Task<Guid> CreateWorkspaceAnalysisAsync(
        Guid workspaceId,
        string titleText,
        string? bodyText,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new WorkspaceAnalysis
        {
            WorkspaceAnalysisId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            TitleText = titleText,
            BodyText = bodyText,
            CreatedOn = DateTimeOffset.UtcNow,
            Version = version ?? 1
        };
        db.WorkspaceAnalyses.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.WorkspaceAnalysisId;
    }

    public async Task<bool> UpdateWorkspaceAnalysisAsync(
        Guid workspaceAnalysisId,
        string? titleText,
        string? bodyText,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceAnalyses.FirstOrDefaultAsync(x => x.WorkspaceAnalysisId == workspaceAnalysisId, ct);
        if (entity is null) return false;
        if (titleText is not null) entity.TitleText = titleText;
        if (bodyText is not null) entity.BodyText = bodyText;
        if (version.HasValue) entity.Version = version.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteWorkspaceAnalysisAsync(Guid workspaceAnalysisId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceAnalyses.FirstOrDefaultAsync(x => x.WorkspaceAnalysisId == workspaceAnalysisId, ct);
        if (entity is null) return false;
        db.WorkspaceAnalyses.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Workspace Analysis Metrics ----------------
    public async Task<Guid> CreateWorkspaceAnalysisMetricAsync(
        Guid workspaceAnalysisId,
        string? mainText,
        string? secondaryText,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new WorkspaceAnalysisMetric
        {
            WorkspaceAnalysisMetricId = Guid.NewGuid(),
            WorkspaceAnalysisId = workspaceAnalysisId,
            MainText = mainText,
            SecondaryText = secondaryText,
            CreatedOn = DateTimeOffset.UtcNow
        };
        db.WorkspaceAnalysisMetrics.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.WorkspaceAnalysisMetricId;
    }

    public async Task<bool> UpdateWorkspaceAnalysisMetricAsync(
        Guid workspaceAnalysisMetricId,
        string? mainText,
        string? secondaryText,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceAnalysisMetrics.FirstOrDefaultAsync(x => x.WorkspaceAnalysisMetricId == workspaceAnalysisMetricId, ct);
        if (entity is null) return false;
        if (mainText is not null) entity.MainText = mainText;
        if (secondaryText is not null) entity.SecondaryText = secondaryText;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteWorkspaceAnalysisMetricAsync(Guid workspaceAnalysisMetricId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.WorkspaceAnalysisMetrics.FirstOrDefaultAsync(x => x.WorkspaceAnalysisMetricId == workspaceAnalysisMetricId, ct);
        if (entity is null) return false;
        db.WorkspaceAnalysisMetrics.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Scenario Metrics ----------------
    public async Task<Guid> CreateScenarioMetricAsync(
        Guid scenarioId,
        string? mainText,
        string? secondaryText,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ScenarioMetric
        {
            ScenarioMetricId = Guid.NewGuid(),
            ScenarioId = scenarioId,
            MainText = mainText,
            SecondaryText = secondaryText,
            CreatedOn = DateTimeOffset.UtcNow,
            Version = version ?? 1
        };
        db.ScenarioMetrics.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.ScenarioMetricId;
    }

    public async Task<bool> UpdateScenarioMetricAsync(
        Guid scenarioMetricId,
        string? mainText,
        string? secondaryText,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScenarioMetrics.FirstOrDefaultAsync(x => x.ScenarioMetricId == scenarioMetricId, ct);
        if (entity is null) return false;
        if (mainText is not null) entity.MainText = mainText;
        if (secondaryText is not null) entity.SecondaryText = secondaryText;
        if (version.HasValue) entity.Version = version.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteScenarioMetricAsync(Guid scenarioMetricId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScenarioMetrics.FirstOrDefaultAsync(x => x.ScenarioMetricId == scenarioMetricId, ct);
        if (entity is null) return false;
        db.ScenarioMetrics.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Scratchpad Notes ----------------
    public async Task<Guid> CreateScratchpadNoteAsync(
        Guid workspaceId,
        string title,
        string text,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var note = new ScratchpadNote
        {
            ScratchpadNoteId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            Title = title,
            Text = text,
            CreatedOn = DateTimeOffset.UtcNow
        };
        db.ScratchpadNotes.Add(note);
        await db.SaveChangesAsync(ct);
        return note.ScratchpadNoteId;
    }

    public async Task<bool> UpdateScratchpadNoteAsync(
        Guid scratchpadNoteId,
        string? title,
        string? text,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var note = await db.ScratchpadNotes.FirstOrDefaultAsync(x => x.ScratchpadNoteId == scratchpadNoteId, ct);
        if (note is null) return false;
        if (title is not null) note.Title = title;
        if (text is not null) note.Text = text;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteScratchpadNoteAsync(
        Guid scratchpadNoteId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var note = await db.ScratchpadNotes.FirstOrDefaultAsync(x => x.ScratchpadNoteId == scratchpadNoteId, ct);
        if (note is null) return false;
        db.ScratchpadNotes.Remove(note);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Companies (tenant-scoped) ----------------
    public async Task<Guid> CreateCompanyAsync(
        Guid tenantId,
        string name,
        string? markdownContent,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Company
        {
            CompanyId = Guid.NewGuid(),
            TenantId = tenantId,
            Name = name,
            MarkdownContent = markdownContent
        };
        db.Companies.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.CompanyId;
    }

    public async Task<bool> UpdateCompanyAsync(
        Guid companyId,
        string? name,
        string? markdownContent,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Companies.FirstOrDefaultAsync(x => x.CompanyId == companyId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (markdownContent is not null) entity.MarkdownContent = markdownContent;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteCompanyAsync(
        Guid companyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Companies.FirstOrDefaultAsync(x => x.CompanyId == companyId, ct);
        if (entity is null) return false;
        db.Companies.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Ontologies (tenant-scoped; shared across workspaces) ----------------
    public async Task<Guid> CreateOntologyAsync(
        Guid tenantId,
        string name,
        string? description,
        string? semVer,
        Guid? createdBy,
        string? status,
        Guid? companyId,
        string? domainExamples,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Ontology
        {
            OntologyId = Guid.NewGuid(),
            TenantId = tenantId,
            CompanyId = companyId,
            Name = name,
            Description = description,
            SemVer = semVer,
            CreatedOn = DateTimeOffset.UtcNow,
            CreatedBy = createdBy,
            Status = status ?? "draft",
            DomainExamples = domainExamples
        };
        db.Ontologies.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.OntologyId;
    }

    public async Task<bool> UpdateOntologyAsync(
        Guid ontologyId,
        string? name,
        string? description,
        string? semVer,
        Guid? lastEditedBy,
        string? status,
        Guid? runId,
        string? jsonUri,
        Optional<Guid?> companyId,
        Optional<string?> domainExamples,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Ontologies.FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        if (semVer is not null) entity.SemVer = semVer;
        if (lastEditedBy is not null) entity.LastEditedBy = lastEditedBy;
        if (status is not null) entity.Status = status;
        if (runId is not null) entity.RunId = runId;
        if (jsonUri is not null) entity.JsonUri = jsonUri;
        if (companyId.HasValue) entity.CompanyId = companyId.Value;
        if (domainExamples.HasValue) entity.DomainExamples = domainExamples.Value;
        entity.LastEdit = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteOntologyAsync(
        Guid ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Ontologies.FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (entity is null) return false;
        db.Ontologies.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Intents (tenant-scoped; agent intent operations) ----------------
    public async Task<Guid> CreateIntentAsync(
        Guid tenantId,
        string opId,
        string intentName,
        string? route,
        string? description,
        string? dataSource,
        string? inputSchema,
        string? outputSchema,
        string? grounding,
        Guid? ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Intent
        {
            IntentId = Guid.NewGuid(),
            TenantId = tenantId,
            OntologyId = ontologyId,
            OpId = opId,
            IntentName = intentName,
            Route = route,
            Description = description,
            DataSource = dataSource,
            InputSchema = inputSchema,
            OutputSchema = outputSchema,
            Grounding = grounding,
            CreatedOn = DateTimeOffset.UtcNow
        };
        db.Intents.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.IntentId;
    }

    public async Task<bool> UpdateIntentAsync(
        Guid intentId,
        Optional<string> opId,
        Optional<string> intentName,
        Optional<string?> route,
        Optional<string?> description,
        Optional<string?> dataSource,
        Optional<string?> inputSchema,
        Optional<string?> outputSchema,
        Optional<string?> grounding,
        Optional<Guid?> ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Intents.FirstOrDefaultAsync(x => x.IntentId == intentId, ct);
        if (entity is null) return false;
        if (opId.HasValue) entity.OpId = opId.Value;
        if (intentName.HasValue) entity.IntentName = intentName.Value;
        if (route.HasValue) entity.Route = route.Value;
        if (description.HasValue) entity.Description = description.Value;
        if (dataSource.HasValue) entity.DataSource = dataSource.Value;
        if (inputSchema.HasValue) entity.InputSchema = inputSchema.Value;
        if (outputSchema.HasValue) entity.OutputSchema = outputSchema.Value;
        if (grounding.HasValue) entity.Grounding = grounding.Value;
        if (ontologyId.HasValue) entity.OntologyId = ontologyId.Value;
        entity.LastEdit = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteIntentAsync(
        Guid intentId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Intents.FirstOrDefaultAsync(x => x.IntentId == intentId, ct);
        if (entity is null) return false;
        db.Intents.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Agent Roles ----------------
    public async Task<Guid> CreateAgentRoleAsync(
        Guid tenantId,
        string name,
        string? description,
        Guid? readOntologyId,
        Guid? writeOntologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new AgentRole
        {
            AgentRoleId = Guid.NewGuid(),
            TenantId = tenantId,
            Name = name,
            Description = description,
            ReadOntologyId = readOntologyId,
            WriteOntologyId = writeOntologyId,
            CreatedOn = DateTimeOffset.UtcNow
        };
        db.AgentRoles.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.AgentRoleId;
    }

    public async Task<bool> UpdateAgentRoleAsync(
        Guid agentRoleId,
        Optional<string> name,
        Optional<string?> description,
        Optional<Guid?> readOntologyId,
        Optional<Guid?> writeOntologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AgentRoles.FirstOrDefaultAsync(x => x.AgentRoleId == agentRoleId, ct);
        if (entity is null) return false;
        if (name.HasValue) entity.Name = name.Value;
        if (description.HasValue) entity.Description = description.Value;
        if (readOntologyId.HasValue) entity.ReadOntologyId = readOntologyId.Value;
        if (writeOntologyId.HasValue) entity.WriteOntologyId = writeOntologyId.Value;
        entity.LastEdit = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteAgentRoleAsync(
        Guid agentRoleId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AgentRoles.FirstOrDefaultAsync(x => x.AgentRoleId == agentRoleId, ct);
        if (entity is null) return false;
        db.AgentRoles.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> SetAgentRoleIntentsAsync(
        Guid agentRoleId,
        IReadOnlyList<Guid> intentIds,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var role = await db.AgentRoles.FirstOrDefaultAsync(x => x.AgentRoleId == agentRoleId, ct);
        if (role is null) return false;
        var existing = await db.AgentRoleIntents.Where(x => x.AgentRoleId == agentRoleId).ToListAsync(ct);
        db.AgentRoleIntents.RemoveRange(existing);
        foreach (var intentId in intentIds.Distinct())
        {
            var intent = await db.Intents.AsNoTracking().FirstOrDefaultAsync(i => i.IntentId == intentId, ct);
            if (intent is null || intent.TenantId != role.TenantId) continue;
            db.AgentRoleIntents.Add(new AgentRoleIntent { AgentRoleId = agentRoleId, IntentId = intentId });
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<GenerateAgentRoleAccessKeyResult> GenerateAgentRoleAccessKeyAsync(
        Guid agentRoleId,
        string? name,
        DateTimeOffset? expiresAt,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var role = await db.AgentRoles.FirstOrDefaultAsync(x => x.AgentRoleId == agentRoleId, ct);
        if (role is null)
            throw new GraphQLException("Agent role not found.");
        var secretBytes = new byte[32];
        RandomNumberGenerator.Fill(secretBytes);
        var secretKey = "ge_" + Convert.ToHexString(secretBytes).ToLowerInvariant();
        var hashBytes = SHA256.HashData(Encoding.UTF8.GetBytes(secretKey));
        var keyHash = Convert.ToHexString(hashBytes).ToLowerInvariant();
        var keyPrefix = "ge_" + secretKey.AsSpan(3, 8).ToString();
        var accessKeyId = Guid.NewGuid();
        var entity = new AgentRoleAccessKey
        {
            AccessKeyId = accessKeyId,
            AgentRoleId = agentRoleId,
            KeyHash = keyHash,
            KeyPrefix = keyPrefix,
            Name = name,
            CreatedOn = DateTimeOffset.UtcNow,
            ExpiresAt = expiresAt
        };
        db.AgentRoleAccessKeys.Add(entity);
        await db.SaveChangesAsync(ct);
        return new GenerateAgentRoleAccessKeyResult
        {
            AccessKeyId = accessKeyId,
            SecretKey = secretKey,
            KeyPrefix = keyPrefix,
            ExpiresAt = expiresAt
        };
    }

    public async Task<bool> RevokeAgentRoleAccessKeyAsync(
        Guid accessKeyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AgentRoleAccessKeys.FirstOrDefaultAsync(x => x.AccessKeyId == accessKeyId, ct);
        if (entity is null) return false;
        db.AgentRoleAccessKeys.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    /// <summary>Clones an ontology: new DB row plus copy of draft.json to the new ontology's default blob path. Neo4j credentials are not copied.</summary>
    public async Task<Guid> CloneOntologyAsync(
        Guid sourceOntologyId,
        string? name,
        Guid tenantId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        [Service] IOptions<AzureStorageOptions> storageOptions,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var source = await db.Ontologies.AsNoTracking().FirstOrDefaultAsync(x => x.OntologyId == sourceOntologyId, ct);
        if (source is null || source.TenantId != tenantId)
            throw new GraphQLException("Ontology not found or tenant mismatch.");

        string sourceContainer;
        string sourceBlobPath;
        var jsonUri = source.JsonUri?.Trim();
        if (!string.IsNullOrEmpty(jsonUri) && Uri.TryCreate(jsonUri, UriKind.Absolute, out var uri) &&
            (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps) &&
            uri.Host.Contains(".blob.core.windows.net", StringComparison.OrdinalIgnoreCase))
        {
            var pathSegments = uri.AbsolutePath.TrimStart('/').Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (pathSegments.Length < 2)
            {
                sourceContainer = "scratchpad-attachments";
                sourceBlobPath = $"ontology-drafts/{Guid.Empty:D}/{sourceOntologyId}/draft.json";
            }
            else
            {
                sourceContainer = pathSegments[0];
                sourceBlobPath = string.Join("/", pathSegments.Skip(1));
            }
        }
        else if (!string.IsNullOrEmpty(jsonUri))
        {
            sourceContainer = "scratchpad-attachments";
            sourceBlobPath = jsonUri;
        }
        else
        {
            sourceContainer = "scratchpad-attachments";
            sourceBlobPath = $"ontology-drafts/{Guid.Empty:D}/{sourceOntologyId}/draft.json";
        }

        var draftContent = await storage.GetContentAsStringAsync(sourceContainer, sourceBlobPath, ct);

        var newId = Guid.NewGuid();
        var newName = !string.IsNullOrWhiteSpace(name) ? name.Trim() : ("Copy of " + source.Name);
        var clone = new Ontology
        {
            OntologyId = newId,
            TenantId = source.TenantId,
            CompanyId = source.CompanyId,
            Name = newName,
            Description = source.Description,
            SemVer = source.SemVer,
            DomainExamples = source.DomainExamples,
            Status = "draft",
            CreatedOn = DateTimeOffset.UtcNow,
            JsonUri = null,
            RunId = null
        };
        db.Ontologies.Add(clone);
        await db.SaveChangesAsync(ct);

        if (!string.IsNullOrEmpty(draftContent))
        {
            var container = storageOptions.Value.AttachmentsContainer ?? "scratchpad-attachments";
            var newBlobPath = $"ontology-drafts/{Guid.Empty:D}/{newId}/draft.json";
            var bytes = Encoding.UTF8.GetBytes(draftContent);
            await using var stream = new MemoryStream(bytes);
            await storage.UploadAsync(container, newBlobPath, stream, "application/json", ct);
        }

        return newId;
    }

    /// <summary>
    /// Sets per-ontology Neo4j connection (e.g. for a different Aura instance). Password is encrypted at rest; never returned.
    /// Requires Neo4j:EncryptionKeyBase64 in config.
    /// </summary>
    public async Task<bool> SetOntologyNeo4jConnectionAsync(
        Guid tenantId,
        Guid ontologyId,
        SetOntologyNeo4jConnectionInput input,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IOntologySecretProtection secretProtection,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(input.Uri) || string.IsNullOrWhiteSpace(input.Username) || string.IsNullOrWhiteSpace(input.Password))
            throw new GraphQLException("Uri, Username, and Password are required.");
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Ontologies.FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (entity is null || entity.TenantId != tenantId)
            throw new GraphQLException("Ontology not found or tenant mismatch.");
        entity.Neo4jUri = input.Uri.Trim();
        entity.Neo4jUsername = input.Username.Trim();
        entity.Neo4jEncryptedPassword = secretProtection.Encrypt(input.Password);
        await db.SaveChangesAsync(ct);
        neo4jFactory.InvalidateOntologyNeo4jCache(ontologyId);
        return true;
    }

    /// <summary>
    /// Clears per-ontology Neo4j connection; ontology will use the app default Neo4j.
    /// </summary>
    public async Task<bool> ClearOntologyNeo4jConnectionAsync(
        Guid tenantId,
        Guid ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Ontologies.FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (entity is null || entity.TenantId != tenantId)
            throw new GraphQLException("Ontology not found or tenant mismatch.");
        entity.Neo4jUri = null;
        entity.Neo4jUsername = null;
        entity.Neo4jEncryptedPassword = null;
        await db.SaveChangesAsync(ct);
        neo4jFactory.InvalidateOntologyNeo4jCache(ontologyId);
        return true;
    }

    // ---------------- Data loading workflow (CSV uploads + pipeline) ----------------
    private const string DataLoadingContainer = "data-loading";

    public async Task<Guid> CreateDataLoadingAttachmentAsync(
        Guid tenantId,
        Guid ontologyId,
        IFile file,
        string? fileName,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var ontology = await db.Ontologies.AsNoTracking().FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (ontology is null || ontology.TenantId != tenantId)
            throw new GraphQLException("Ontology not found or tenant mismatch.");

        var attachmentId = Guid.NewGuid();
        var fname = !string.IsNullOrWhiteSpace(fileName) ? fileName : System.IO.Path.GetFileName(file.Name ?? file.GetHashCode().ToString());
        if (string.IsNullOrWhiteSpace(fname)) fname = attachmentId.ToString("N") + ".csv";
        var safeName = string.Join("_", fname.Split(System.IO.Path.GetInvalidFileNameChars(), StringSplitOptions.RemoveEmptyEntries));
        var blobPath = $"data-loading/{tenantId}/{attachmentId}/{safeName}";

        var entity = new DataLoadingAttachment
        {
            AttachmentId = attachmentId,
            TenantId = tenantId,
            OntologyId = ontologyId,
            FileName = safeName,
            BlobPath = blobPath,
            CreatedOn = DateTimeOffset.UtcNow,
            Status = "uploaded"
        };
        db.DataLoadingAttachments.Add(entity);
        await db.SaveChangesAsync(ct);

        await using var stream = file.OpenReadStream();
        var uri = await storage.UploadAsync(DataLoadingContainer, blobPath, stream, file.ContentType ?? "text/csv", ct);
        entity.Uri = uri.ToString();
        await db.SaveChangesAsync(ct);

        return entity.AttachmentId;
    }

    public async Task<StartDataLoadingResult> StartDataLoadingPipelineAsync(
        Guid dataLoadingAttachmentId,
        Guid? workspaceId,
        string? initialInstructions,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] Microsoft.Extensions.Logging.ILogger<EntitiesMutation> logger,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var attachment = await db.DataLoadingAttachments.FirstOrDefaultAsync(x => x.AttachmentId == dataLoadingAttachmentId, ct);
        if (attachment is null)
            return new StartDataLoadingResult { Success = false, RunId = null };

        var tenantId = attachment.TenantId;
        var runId = Guid.NewGuid();
        var effectiveWorkspaceId = workspaceId ?? Guid.Empty;

        var inputsObj = new Dictionary<string, object?>
        {
            ["csv_path"] = attachment.BlobPath,
            ["ontology_id"] = attachment.OntologyId.ToString()
        };
        if (!string.IsNullOrWhiteSpace(initialInstructions))
            inputsObj["initial_instructions"] = initialInstructions;
        var inputs = JsonSerializer.Serialize(inputsObj);

        var payload = new WorkflowEventPayload
        {
            RunId = runId,
            TenantId = tenantId,
            WorkspaceId = effectiveWorkspaceId,
            ScenarioId = Guid.Empty,
            WorkflowId = "data-loading",
            Inputs = inputs,
            Status = "running",
            RequestedAt = DateTimeOffset.UtcNow
        };
        try
        {
            var dispatched = await dispatcher.DispatchAsync(payload, ct);
            if (!dispatched)
                logger.LogWarning("Workflow dispatcher did not send; data-loading message not sent. AttachmentId={AttachmentId}", dataLoadingAttachmentId);

            attachment.RunId = runId;
            attachment.Status = "running";
            await db.SaveChangesAsync(ct);

            if (dispatched)
                logger.LogInformation("Data-loading workflow dispatched. AttachmentId={AttachmentId}, RunId={RunId}", dataLoadingAttachmentId, runId);
            return new StartDataLoadingResult { Success = true, RunId = runId };
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "StartDataLoadingPipeline: failed to dispatch workflow. AttachmentId={AttachmentId}", dataLoadingAttachmentId);
            return new StartDataLoadingResult { Success = false, RunId = runId };
        }
    }

    public async Task<bool> DeleteDataLoadingAttachmentAsync(
        Guid attachmentId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.DataLoadingAttachments.FirstOrDefaultAsync(x => x.AttachmentId == attachmentId, ct);
        if (entity is null) return false;
        try { await storage.DeleteAsync(DataLoadingContainer, entity.BlobPath, ct); } catch { /* best effort */ }
        db.DataLoadingAttachments.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Scratchpad Attachments ----------------
    public async Task<Guid> CreateScratchpadAttachmentAsync(
        Guid workspaceId,
        string title,
        string? description,
        IFile file,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        [Service] Microsoft.Extensions.Options.IOptions<Geodesic.App.Api.Storage.AzureStorageOptions> storageOptions,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ScratchpadAttachment
        {
            ScratchpadAttachmentId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            Title = title,
            Description = description,
            CreatedOn = DateTimeOffset.UtcNow,
            FileType = file.ContentType,
            ProcessingStatus = "unprocessed",
        };
        // Precalculate size by reading length if available
        try { entity.Size = file.Length; } catch { /* ignore if not available */ }

        db.ScratchpadAttachments.Add(entity);
        await db.SaveChangesAsync(ct);

        // Upload to blob storage
        var fname = System.IO.Path.GetFileName(file.Name ?? file.GetHashCode().ToString());
        if (string.IsNullOrWhiteSpace(fname)) fname = entity.ScratchpadAttachmentId.ToString("N");
        var safeName = string.Join("_", fname.Split(System.IO.Path.GetInvalidFileNameChars(), StringSplitOptions.RemoveEmptyEntries));
        var blobPath = $"workspaces/{workspaceId}/attachments/{entity.ScratchpadAttachmentId}/{safeName}";
        await using var stream = file.OpenReadStream();
        var container = storageOptions.Value.AttachmentsContainer ?? "scratchpad-attachments";
        var uri = await storage.UploadAsync(container, blobPath, stream, file.ContentType, ct);

        // Update entity with URI
        entity.Uri = uri.ToString();
        await db.SaveChangesAsync(ct);

        return entity.ScratchpadAttachmentId;
    }

    /// <summary>Starts the document-indexing workflow for an existing scratchpad attachment.</summary>
    public async Task<bool> StartDocumentIndexingPipelineAsync(
        Guid scratchpadAttachmentId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] IHttpContextAccessor accessor,
        [Service] Microsoft.Extensions.Logging.ILogger<EntitiesMutation> logger,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScratchpadAttachments.FirstOrDefaultAsync(x => x.ScratchpadAttachmentId == scratchpadAttachmentId, ct);
        if (entity is null) return false;

        var workspace = await db.Workspaces.AsNoTracking().FirstOrDefaultAsync(x => x.WorkspaceId == entity.WorkspaceId, ct);
        var tenantId = workspace?.TenantId ?? Guid.Empty;

        // Derive blob path from stored Uri (e.g. https://account.blob.core.windows.net/container/path -> path)
        var blobPath = "";
        if (!string.IsNullOrWhiteSpace(entity.Uri) && Uri.TryCreate(entity.Uri, UriKind.Absolute, out var uri))
        {
            var path = uri.AbsolutePath.Trim('/');
            var segments = path.Split('/', 2, StringSplitOptions.RemoveEmptyEntries);
            if (segments.Length == 2) blobPath = segments[1];
        }

        var uploadedBy = accessor.HttpContext?.User?.FindFirst(ClaimTypes.NameIdentifier)?.Value
            ?? accessor.HttpContext?.User?.FindFirst("sub")?.Value;
        var filename = !string.IsNullOrWhiteSpace(blobPath) ? System.IO.Path.GetFileName(blobPath) : entity.Title ?? entity.ScratchpadAttachmentId.ToString("N");

        var inputs = JsonSerializer.Serialize(new
        {
            docId = entity.ScratchpadAttachmentId,
            tenantId,
            workspaceId = entity.WorkspaceId,
            scratchpadAttachmentId = entity.ScratchpadAttachmentId,
            blobPath,
            contentType = entity.FileType ?? "",
            filename,
            uploadedBy,
            uploadedAt = entity.CreatedOn
        });
        var payload = new WorkflowEventPayload
        {
            RunId = entity.ScratchpadAttachmentId,
            TenantId = tenantId,
            WorkspaceId = entity.WorkspaceId,
            ScenarioId = Guid.Empty,
            WorkflowId = "document-graphiti",
            Inputs = inputs,
            Status = "queued",
            RequestedAt = DateTimeOffset.UtcNow
        };
        try
        {
            await dispatcher.DispatchAsync(payload, ct);
            logger.LogInformation(
                "Document indexing workflow dispatched. ScratchpadAttachmentId={ScratchpadAttachmentId}",
                scratchpadAttachmentId);
            entity.ProcessingStatus = "queued";
            entity.ProcessingError = null;
            await db.SaveChangesAsync(ct);
            return true;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "StartDocumentIndexingPipeline: failed to dispatch workflow. ScratchpadAttachmentId={ScratchpadAttachmentId}", scratchpadAttachmentId);
            return false;
        }
    }

    /// <summary>
    /// Starts the ontology-creation workflow (new or resume). Dispatches a WorkflowEvent (Service Bus or Container Apps Job).
    /// Returns runId so the frontend can subscribe to the run's event stream.
    /// </summary>
    public async Task<StartOntologyCreationResult> StartOntologyCreationPipelineAsync(
        Guid workspaceId,
        string? initialContext,
        Guid? ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] Microsoft.Extensions.Logging.ILogger<EntitiesMutation> logger,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var workspace = await db.Workspaces.AsNoTracking().FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId, ct);
        if (workspace is null)
            return new StartOntologyCreationResult { Success = false, RunId = null };

        var tenantId = workspace.TenantId;
        var runId = Guid.NewGuid();

        var inputsObj = new Dictionary<string, object?>();
        if (!string.IsNullOrWhiteSpace(initialContext))
            inputsObj["initial_context"] = initialContext;
        if (ontologyId.HasValue)
            inputsObj["ontology_id"] = ontologyId.Value.ToString();
        var inputs = JsonSerializer.Serialize(inputsObj);

        var payload = new WorkflowEventPayload
        {
            RunId = runId,
            TenantId = tenantId,
            WorkspaceId = workspaceId,
            ScenarioId = Guid.Empty,
            WorkflowId = "ontology-conversation",
            Inputs = inputs,
            Status = "running",
            RequestedAt = DateTimeOffset.UtcNow
        };
        try
        {
            var dispatched = await dispatcher.DispatchAsync(payload, ct);
            if (!dispatched)
                logger.LogWarning("Workflow dispatcher did not send; ontology creation message not sent. WorkspaceId={WorkspaceId}", workspaceId);
            else
                logger.LogInformation(
                    "Ontology creation workflow dispatched. WorkspaceId={WorkspaceId}, RunId={RunId}, OntologyId={OntologyId}",
                    workspaceId, runId, ontologyId);
            return new StartOntologyCreationResult { Success = true, RunId = runId };
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "StartOntologyCreationPipeline: failed to dispatch workflow. WorkspaceId={WorkspaceId}", workspaceId);
            return new StartOntologyCreationResult { Success = false, RunId = runId };
        }
    }

    public async Task<bool> UpdateScratchpadAttachmentAsync(
        Guid scratchpadAttachmentId,
        string? title,
        string? description,
        string? processingStatus,
        string? processingError,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScratchpadAttachments.FirstOrDefaultAsync(x => x.ScratchpadAttachmentId == scratchpadAttachmentId, ct);
        if (entity is null) return false;
        if (title is not null) entity.Title = title;
        if (description is not null) entity.Description = description;
        if (processingStatus is not null) entity.ProcessingStatus = processingStatus;
        if (processingError is not null) entity.ProcessingError = processingError;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteScratchpadAttachmentAsync(
        Guid scratchpadAttachmentId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ScratchpadAttachments.FirstOrDefaultAsync(x => x.ScratchpadAttachmentId == scratchpadAttachmentId, ct);
        if (entity is null) return false;

        // Try delete blob if we can parse container/path from URI
        if (!string.IsNullOrWhiteSpace(entity.Uri))
        {
            try
            {
                var u = new Uri(entity.Uri);
                var segments = u.AbsolutePath.Trim('/').Split('/', 2);
                if (segments.Length == 2)
                {
                    var container = segments[0];
                    var path = segments[1];
                    try { await storage.DeleteAsync(container, path, ct); } catch { /* best effort */ }
                }
            }
            catch { /* ignore parse errors */ }
        }

        db.ScratchpadAttachments.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Semantic Entities ----------------
    public async Task<Guid> CreateSemanticEntityAsync(
        Guid tenantId,
        string nodeLabel,
        string name,
        string? description,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new SemanticEntity
        {
            SemanticEntityId = Guid.NewGuid(),
            TenantId = tenantId,
            NodeLabel = nodeLabel,
            Name = name,
            Description = description,
            Version = version ?? 1,
            CreatedOn = DateTimeOffset.UtcNow
        };
        db.SemanticEntities.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.SemanticEntityId;
    }

    public async Task<bool> UpdateSemanticEntityAsync(
        Guid semanticEntityId,
        string? nodeLabel,
        string? name,
        string? description,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.SemanticEntities.FirstOrDefaultAsync(x => x.SemanticEntityId == semanticEntityId, ct);
        if (entity is null) return false;
        if (nodeLabel is not null) entity.NodeLabel = nodeLabel;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        if (version is not null) entity.Version = version.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteSemanticEntityAsync(
        Guid semanticEntityId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.SemanticEntities.FirstOrDefaultAsync(x => x.SemanticEntityId == semanticEntityId, ct);
        if (entity is null) return false;
        db.SemanticEntities.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Semantic Fields ----------------
    public async Task<Guid> CreateSemanticFieldAsync(
        Guid semanticEntityId,
        string name,
        string? description,
        string? dataType,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new SemanticField
        {
            SemanticFieldId = Guid.NewGuid(),
            SemanticEntityId = semanticEntityId,
            Name = name,
            Description = description,
            DataType = dataType,
            Version = version ?? 1
        };
        db.SemanticFields.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.SemanticFieldId;
    }

    public async Task<bool> UpdateSemanticFieldAsync(
        Guid semanticFieldId,
        string? name,
        string? description,
        string? dataType,
        int? version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.SemanticFields.FirstOrDefaultAsync(x => x.SemanticFieldId == semanticFieldId, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        if (dataType is not null) entity.DataType = dataType;
        if (version is not null) entity.Version = version.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteSemanticFieldAsync(
        Guid semanticFieldId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.SemanticFields.FirstOrDefaultAsync(x => x.SemanticFieldId == semanticFieldId, ct);
        if (entity is null) return false;
        db.SemanticFields.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Semantic Field Range Calculation (Admin) ----------------
    public async Task<bool> CalculateSemanticFieldRangesAsync(
        [Service] SemanticFieldRangeService rangeService,
        CancellationToken ct)
    {
        var updatedCount = await rangeService.CalculateRangesAsync(ct);
        return updatedCount >= 0; // Return true if no errors occurred
    }

    /// <summary>Syncs ontology draft.json to semantic_entities/semantic_fields for the given ontology and computes range info from Neo4j.</summary>
    public async Task<SyncOntologyToSemanticEntitiesResult> SyncOntologyToSemanticEntitiesAsync(
        Guid ontologyId,
        [Service] OntologySemanticSyncService syncService,
        CancellationToken ct)
    {
        return await syncService.SyncAsync(ontologyId, ct);
    }
}

/// <summary>
/// Result of starting the data-loading pipeline. RunId is set when the workflow was queued so the client can subscribe to the run stream.
/// </summary>
public sealed class StartDataLoadingResult
{
    /// <summary>Run ID for this workflow run; use to connect to the run's event stream. Null if the run was not queued.</summary>
    public Guid? RunId { get; set; }
    /// <summary>True if the workflow was accepted (queued or no Service Bus); false if attachment/workspace not found or send failed.</summary>
    public bool Success { get; set; }
}

/// <summary>
/// Result of starting the ontology-creation pipeline. RunId is set when the workflow was queued so the client can subscribe to the run stream.
/// </summary>
public sealed class StartOntologyCreationResult
{
    /// <summary>Run ID for this workflow run; use to connect to the run's event stream. Null if the run was not queued (e.g. workspace not found).</summary>
    public Guid? RunId { get; set; }
    /// <summary>True if the workflow was accepted (queued or no Service Bus); false if workspace not found or send failed.</summary>
    public bool Success { get; set; }
}

/// <summary>
/// Result of generating an agent role access key. SecretKey is returned only once; client must store it.
/// </summary>
public sealed class GenerateAgentRoleAccessKeyResult
{
    public Guid AccessKeyId { get; set; }
    /// <summary>Full secret; returned only on generation. Never stored or returned again.</summary>
    public string SecretKey { get; set; } = default!;
    public string KeyPrefix { get; set; } = default!;
    public DateTimeOffset? ExpiresAt { get; set; }
}

