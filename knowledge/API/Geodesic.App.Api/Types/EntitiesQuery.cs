using System.Collections.Generic;
using Geodesic.App.Api.Storage;
using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using HotChocolate;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class EntitiesQuery
{
    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Tenant> Tenants([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Tenants.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Role> Roles([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Roles.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<UserRole> UserRoles([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().UserRoles.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<WorkspaceMember> WorkspaceMembers([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().WorkspaceMembers.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<WorkspaceItem> WorkspaceItems([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().WorkspaceItems.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<OverlayChangeset> OverlayChangesets([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().OverlayChangesets.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<OverlayNodePatch> OverlayNodePatches([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().OverlayNodePatches.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<OverlayEdgePatch> OverlayEdgePatches([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().OverlayEdgePatches.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Scenario> Scenarios([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Scenarios.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ScenarioRun> ScenarioRuns([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ScenarioRuns.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Insight> Insights([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Insights.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<AITeam> AITeams([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().AITeams.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<AITeamMember> AITeamMembers([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().AITeamMembers.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<WorkspaceAnalysis> WorkspaceAnalyses([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().WorkspaceAnalyses.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<WorkspaceAnalysisMetric> WorkspaceAnalysisMetrics([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().WorkspaceAnalysisMetrics.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ScenarioMetric> ScenarioMetrics([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ScenarioMetrics.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ScratchpadAttachment> ScratchpadAttachments([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ScratchpadAttachments.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ScratchpadNote> ScratchpadNotes([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ScratchpadNotes.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Ontology> Ontologies([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Ontologies.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Company> Companies([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Companies.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<DataLoadingAttachment> DataLoadingAttachments([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().DataLoadingAttachments.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Intent> Intents([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Intents.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<AgentRole> AgentRoles([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().AgentRoles.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public async Task<IQueryable<SemanticEntity>> SemanticEntities(
        Guid? workspaceId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        var db = dbFactory.CreateDbContext();
        var query = db.SemanticEntities.AsNoTracking();
        if (workspaceId is not { } wid)
            return query;
        var workspace = await db.Workspaces.AsNoTracking().FirstOrDefaultAsync(w => w.WorkspaceId == wid, ct);
        if (workspace is null)
            return query.Where(_ => false);
        return query.Where(e => e.OntologyId == workspace.OntologyId);
    }

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<SemanticField> SemanticFields([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().SemanticFields.AsNoTracking();

    public Task<Workspace?> WorkspaceByIdAsync(Guid workspaceId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Workspaces.AsNoTracking().FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId, ct);

    public Task<User?> UserByIdAsync(Guid userId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Users.AsNoTracking().FirstOrDefaultAsync(x => x.UserId == userId, ct);

    public Task<Tenant?> TenantByIdAsync(Guid tenantId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Tenants.AsNoTracking().FirstOrDefaultAsync(x => x.TenantId == tenantId, ct);

    public Task<Scenario?> ScenarioByIdAsync(Guid scenarioId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Scenarios.AsNoTracking().FirstOrDefaultAsync(x => x.ScenarioId == scenarioId, ct);

    public Task<ScenarioRun?> ScenarioRunByIdAsync(Guid runId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().ScenarioRuns.AsNoTracking().FirstOrDefaultAsync(x => x.RunId == runId, ct);

    public Task<OverlayChangeset?> OverlayChangesetByIdAsync(Guid changesetId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().OverlayChangesets.AsNoTracking().FirstOrDefaultAsync(x => x.ChangesetId == changesetId, ct);

    public Task<Insight?> InsightByIdAsync(Guid insightId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Insights.AsNoTracking().FirstOrDefaultAsync(x => x.InsightId == insightId, ct);

    public Task<AITeam?> AITeamByIdAsync(Guid aiTeamId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().AITeams.AsNoTracking().FirstOrDefaultAsync(x => x.AITeamId == aiTeamId, ct);

    public Task<AITeamMember?> AITeamMemberByIdAsync(Guid aiTeamMemberId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().AITeamMembers.AsNoTracking().FirstOrDefaultAsync(x => x.AITeamMemberId == aiTeamMemberId, ct);

    public Task<WorkspaceAnalysis?> WorkspaceAnalysisByIdAsync(Guid workspaceAnalysisId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().WorkspaceAnalyses.AsNoTracking().FirstOrDefaultAsync(x => x.WorkspaceAnalysisId == workspaceAnalysisId, ct);

    public Task<WorkspaceAnalysisMetric?> WorkspaceAnalysisMetricByIdAsync(Guid workspaceAnalysisMetricId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().WorkspaceAnalysisMetrics.AsNoTracking().FirstOrDefaultAsync(x => x.WorkspaceAnalysisMetricId == workspaceAnalysisMetricId, ct);

    public Task<ScenarioMetric?> ScenarioMetricByIdAsync(Guid scenarioMetricId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().ScenarioMetrics.AsNoTracking().FirstOrDefaultAsync(x => x.ScenarioMetricId == scenarioMetricId, ct);

    public Task<ScratchpadAttachment?> ScratchpadAttachmentByIdAsync(Guid scratchpadAttachmentId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().ScratchpadAttachments.AsNoTracking().FirstOrDefaultAsync(x => x.ScratchpadAttachmentId == scratchpadAttachmentId, ct);

    /// <summary>Returns the contents of the processed pipeline's assertions.json for the attachment, or null if the attachment or file is missing.</summary>
    public async Task<string?> ScratchpadAttachmentAssertionsAsync(
        Guid scratchpadAttachmentId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        [Service] IOptions<AzureStorageOptions> storageOptions,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var attachment = await db.ScratchpadAttachments
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.ScratchpadAttachmentId == scratchpadAttachmentId, ct);
        if (attachment is null)
            return null;

        var workspace = await db.Workspaces
            .AsNoTracking()
            .FirstOrDefaultAsync(w => w.WorkspaceId == attachment.WorkspaceId, ct);
        if (workspace is null)
            return null;

        var container = storageOptions.Value.AttachmentsContainer ?? "scratchpad-attachments";
        var blobPath = $"processed/{workspace.TenantId}/{attachment.ScratchpadAttachmentId}/assertions.json";
        return await storage.GetContentAsStringAsync(container, blobPath, ct);
    }

    public Task<ScratchpadNote?> ScratchpadNoteByIdAsync(Guid scratchpadNoteId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().ScratchpadNotes.AsNoTracking().FirstOrDefaultAsync(x => x.ScratchpadNoteId == scratchpadNoteId, ct);

    public Task<Ontology?> OntologyByIdAsync(Guid ontologyId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Ontologies.AsNoTracking().FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);

    public Task<Company?> CompanyByIdAsync(Guid companyId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Companies.AsNoTracking().FirstOrDefaultAsync(x => x.CompanyId == companyId, ct);

    public Task<Intent?> IntentByIdAsync(Guid intentId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().Intents.AsNoTracking().FirstOrDefaultAsync(x => x.IntentId == intentId, ct);

    public Task<AgentRole?> AgentRoleByIdAsync(Guid agentRoleId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().AgentRoles.AsNoTracking().FirstOrDefaultAsync(x => x.AgentRoleId == agentRoleId, ct);

    /// <summary>Access keys for an agent role (metadata only; secret is never returned).</summary>
    public async Task<IReadOnlyList<AgentRoleAccessKey>> AgentRoleAccessKeysAsync(Guid agentRoleId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.AgentRoleAccessKeys.AsNoTracking().Where(x => x.AgentRoleId == agentRoleId).OrderByDescending(x => x.CreatedOn).ToListAsync(ct);
    }

    /// <summary>Returns the contents of the ontology JSON file from blob storage (from jsonUri or default path). Null if ontology or file is missing.</summary>
    public async Task<string?> OntologyJsonAsync(
        Guid ontologyId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IFileStorage storage,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var ontology = await db.Ontologies
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (ontology is null)
            return null;

        string container;
        string blobPath;
        var jsonUri = ontology.JsonUri?.Trim();
        if (!string.IsNullOrEmpty(jsonUri) && Uri.TryCreate(jsonUri, UriKind.Absolute, out var uri) &&
            (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps) &&
            uri.Host.Contains(".blob.core.windows.net", StringComparison.OrdinalIgnoreCase))
        {
            var pathSegments = uri.AbsolutePath.TrimStart('/').Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (pathSegments.Length < 2)
                return null;
            container = pathSegments[0];
            blobPath = string.Join("/", pathSegments.Skip(1));
        }
        else if (!string.IsNullOrEmpty(jsonUri))
        {
            container = "scratchpad-attachments";
            blobPath = jsonUri;
        }
        else
        {
            container = "scratchpad-attachments";
            blobPath = $"ontology-drafts/{Guid.Empty:D}/{ontology.OntologyId}/draft.json";
        }

        return await storage.GetContentAsStringAsync(container, blobPath, ct);
    }

    public Task<DataLoadingAttachment?> DataLoadingAttachmentByIdAsync(Guid attachmentId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().DataLoadingAttachments.AsNoTracking().FirstOrDefaultAsync(x => x.AttachmentId == attachmentId, ct);

    public Task<SemanticEntity?> SemanticEntityByNodeLabelAsync(string nodeLabel, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().SemanticEntities.AsNoTracking().FirstOrDefaultAsync(x => x.NodeLabel == nodeLabel, ct);

    public Task<List<SemanticField>> SemanticFieldsBySemanticEntityIdAsync(Guid semanticEntityId, [Service] IDbContextFactory<AppDbContext> dbFactory, CancellationToken ct)
        => dbFactory.CreateDbContext().SemanticFields.AsNoTracking().Where(x => x.SemanticEntityId == semanticEntityId).ToListAsync(ct);
}

