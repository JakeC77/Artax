using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using HotChocolate;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class ReportsMutation
{
    // ---------------- Report Templates ---------------- 
    public async Task<Guid> CreateReportTemplateAsync(
        Guid templateId,
        int version,
        string name,
        string? description,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ReportTemplate
        {
            TemplateId = templateId,
            Version = version,
            Name = name,
            Description = description,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };
        db.ReportTemplates.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.TemplateId;
    }

    public async Task<bool> UpdateReportTemplateAsync(
        Guid templateId,
        int version,
        string? name,
        string? description,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportTemplates.FirstOrDefaultAsync(
            x => x.TemplateId == templateId && x.Version == version, ct);
        if (entity is null) return false;
        if (name is not null) entity.Name = name;
        if (description is not null) entity.Description = description;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteReportTemplateAsync(
        Guid templateId,
        int version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportTemplates.FirstOrDefaultAsync(
            x => x.TemplateId == templateId && x.Version == version, ct);
        if (entity is null) return false;
        db.ReportTemplates.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Report Template Sections ---------------- 
    public async Task<Guid> CreateReportTemplateSectionAsync(
        Guid templateId,
        int templateVersion,
        string sectionType,
        string header,
        int order,
        string? semanticDefinition,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ReportTemplateSection
        {
            TemplateSectionId = Guid.NewGuid(),
            TemplateId = templateId,
            TemplateVersion = templateVersion,
            SectionType = sectionType,
            Header = header,
            Order = order,
            SemanticDefinition = semanticDefinition
        };
        db.ReportTemplateSections.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.TemplateSectionId;
    }

    public async Task<bool> UpdateReportTemplateSectionAsync(
        Guid templateSectionId,
        string? sectionType,
        string? header,
        int? order,
        string? semanticDefinition,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportTemplateSections.FirstOrDefaultAsync(
            x => x.TemplateSectionId == templateSectionId, ct);
        if (entity is null) return false;
        if (sectionType is not null) entity.SectionType = sectionType;
        if (header is not null) entity.Header = header;
        if (order.HasValue) entity.Order = order.Value;
        if (semanticDefinition is not null) entity.SemanticDefinition = semanticDefinition;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteReportTemplateSectionAsync(
        Guid templateSectionId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportTemplateSections.FirstOrDefaultAsync(
            x => x.TemplateSectionId == templateSectionId, ct);
        if (entity is null) return false;
        db.ReportTemplateSections.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Report Template Blocks ---------------- 
    public async Task<Guid> CreateReportTemplateBlockAsync(
        Guid templateSectionId,
        string blockType,
        int order,
        string? layoutHints,
        string? semanticDefinition,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ReportTemplateBlock
        {
            TemplateBlockId = Guid.NewGuid(),
            TemplateSectionId = templateSectionId,
            BlockType = blockType,
            Order = order,
            LayoutHints = layoutHints ?? "{}",
            SemanticDefinition = semanticDefinition
        };
        db.ReportTemplateBlocks.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.TemplateBlockId;
    }

    public async Task<bool> UpdateReportTemplateBlockAsync(
        Guid templateBlockId,
        string? blockType,
        int? order,
        string? layoutHints,
        string? semanticDefinition,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportTemplateBlocks.FirstOrDefaultAsync(
            x => x.TemplateBlockId == templateBlockId, ct);
        if (entity is null) return false;
        if (blockType is not null) entity.BlockType = blockType;
        if (order.HasValue) entity.Order = order.Value;
        if (layoutHints is not null) entity.LayoutHints = layoutHints;
        if (semanticDefinition is not null) entity.SemanticDefinition = semanticDefinition;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteReportTemplateBlockAsync(
        Guid templateBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportTemplateBlocks.FirstOrDefaultAsync(
            x => x.TemplateBlockId == templateBlockId, ct);
        if (entity is null) return false;
        db.ReportTemplateBlocks.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Reports ---------------- 
    public async Task<Guid> CreateReportAsync(
        Guid? templateId,
        int? templateVersion,
        Guid? workspaceAnalysisId,
        Guid? scenarioId,
        string type,
        string title,
        string status,
        string? metadata,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        
        // Validate that exactly one parent is set
        if ((workspaceAnalysisId.HasValue && scenarioId.HasValue) || 
            (!workspaceAnalysisId.HasValue && !scenarioId.HasValue))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Exactly one of workspaceAnalysisId or scenarioId must be set")
                .SetCode("INVALID_REPORT_PARENT")
                .Build());
        }

        // Validate that if templateId is provided, templateVersion must also be provided
        if (templateId.HasValue && !templateVersion.HasValue)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("templateVersion must be provided when templateId is provided")
                .SetCode("INVALID_TEMPLATE_PARAMS")
                .Build());
        }

        // Validate that if templateVersion is provided, templateId must also be provided
        if (templateVersion.HasValue && !templateId.HasValue)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("templateId must be provided when templateVersion is provided")
                .SetCode("INVALID_TEMPLATE_PARAMS")
                .Build());
        }

        var entity = new Report
        {
            ReportId = Guid.NewGuid(),
            TemplateId = templateId,
            TemplateVersion = templateVersion,
            WorkspaceAnalysisId = workspaceAnalysisId,
            ScenarioId = scenarioId,
            Type = type,
            Title = title,
            Status = status,
            Metadata = metadata ?? "{}",
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };
        db.Reports.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.ReportId;
    }

    public async Task<bool> UpdateReportAsync(
        Guid reportId,
        string? title,
        string? status,
        string? metadata,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Reports.FirstOrDefaultAsync(x => x.ReportId == reportId, ct);
        if (entity is null) return false;
        if (title is not null) entity.Title = title;
        if (status is not null) entity.Status = status;
        if (metadata is not null) entity.Metadata = metadata;
        entity.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteReportAsync(
        Guid reportId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Reports.FirstOrDefaultAsync(x => x.ReportId == reportId, ct);
        if (entity is null) return false;
        db.Reports.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Report Sections ---------------- 
    public async Task<Guid> CreateReportSectionAsync(
        Guid reportId,
        Guid? templateSectionId,
        string sectionType,
        string header,
        int order,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ReportSection
        {
            ReportSectionId = Guid.NewGuid(),
            ReportId = reportId,
            TemplateSectionId = templateSectionId,
            SectionType = sectionType,
            Header = header,
            Order = order
        };
        db.ReportSections.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.ReportSectionId;
    }

    public async Task<bool> UpdateReportSectionAsync(
        Guid reportSectionId,
        string? header,
        int? order,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportSections.FirstOrDefaultAsync(
            x => x.ReportSectionId == reportSectionId, ct);
        if (entity is null) return false;
        if (header is not null) entity.Header = header;
        if (order.HasValue) entity.Order = order.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteReportSectionAsync(
        Guid reportSectionId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportSections.FirstOrDefaultAsync(
            x => x.ReportSectionId == reportSectionId, ct);
        if (entity is null) return false;
        db.ReportSections.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Report Blocks ---------------- 
    public async Task<Guid> CreateReportBlockAsync(
        Guid reportSectionId,
        Guid? templateBlockId,
        string blockType,
        string[]? sourceRefs,
        string? provenance,
        string? layoutHints,
        int order,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new ReportBlock
        {
            ReportBlockId = Guid.NewGuid(),
            ReportSectionId = reportSectionId,
            TemplateBlockId = templateBlockId,
            BlockType = blockType,
            SourceRefs = sourceRefs ?? Array.Empty<string>(),
            Provenance = provenance ?? "{}",
            LayoutHints = layoutHints ?? "{}",
            Order = order
        };
        db.ReportBlocks.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.ReportBlockId;
    }

    public async Task<bool> UpdateReportBlockAsync(
        Guid reportBlockId,
        string[]? sourceRefs,
        string? provenance,
        string? layoutHints,
        int? order,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportBlocks.FirstOrDefaultAsync(
            x => x.ReportBlockId == reportBlockId, ct);
        if (entity is null) return false;
        if (sourceRefs is not null) entity.SourceRefs = sourceRefs;
        if (provenance is not null) entity.Provenance = provenance;
        if (layoutHints is not null) entity.LayoutHints = layoutHints;
        if (order.HasValue) entity.Order = order.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteReportBlockAsync(
        Guid reportBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportBlocks.FirstOrDefaultAsync(
            x => x.ReportBlockId == reportBlockId, ct);
        if (entity is null) return false;
        db.ReportBlocks.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Report Block Content ---------------- 
    public async Task<bool> UpsertReportBlockRichTextAsync(
        Guid reportBlockId,
        string content,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportBlockRichTexts.FirstOrDefaultAsync(
            x => x.ReportBlockId == reportBlockId, ct);
        if (entity is null)
        {
            entity = new ReportBlockRichText
            {
                ReportBlockId = reportBlockId,
                Content = content
            };
            db.ReportBlockRichTexts.Add(entity);
        }
        else
        {
            entity.Content = content;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> UpsertReportBlockSingleMetricAsync(
        Guid reportBlockId,
        string label,
        string value,
        string? unit,
        string? trend,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportBlockSingleMetrics.FirstOrDefaultAsync(
            x => x.ReportBlockId == reportBlockId, ct);
        if (entity is null)
        {
            entity = new ReportBlockSingleMetric
            {
                ReportBlockId = reportBlockId,
                Label = label,
                Value = value,
                Unit = unit,
                Trend = trend
            };
            db.ReportBlockSingleMetrics.Add(entity);
        }
        else
        {
            entity.Label = label;
            entity.Value = value;
            entity.Unit = unit;
            entity.Trend = trend;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> UpsertReportBlockMultiMetricAsync(
        Guid reportBlockId,
        string metrics,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportBlockMultiMetrics.FirstOrDefaultAsync(
            x => x.ReportBlockId == reportBlockId, ct);
        if (entity is null)
        {
            entity = new ReportBlockMultiMetric
            {
                ReportBlockId = reportBlockId,
                Metrics = metrics
            };
            db.ReportBlockMultiMetrics.Add(entity);
        }
        else
        {
            entity.Metrics = metrics;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> UpsertReportBlockInsightCardAsync(
        Guid reportBlockId,
        string title,
        string body,
        string? badge,
        string? severity,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.ReportBlockInsightCards.FirstOrDefaultAsync(
            x => x.ReportBlockId == reportBlockId, ct);
        if (entity is null)
        {
            entity = new ReportBlockInsightCard
            {
                ReportBlockId = reportBlockId,
                Title = title,
                Body = body,
                Badge = badge,
                Severity = severity
            };
            db.ReportBlockInsightCards.Add(entity);
        }
        else
        {
            entity.Title = title;
            entity.Body = body;
            entity.Badge = badge;
            entity.Severity = severity;
        }
        await db.SaveChangesAsync(ct);
        return true;
    }

    // ---------------- Sources ---------------- 
    public async Task<Guid> CreateSourceAsync(
        Guid reportId,
        string sourceType,
        string? uri,
        string? title,
        string? description,
        string? metadata,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new Source
        {
            SourceId = Guid.NewGuid(),
            ReportId = reportId,
            SourceType = sourceType,
            Uri = uri,
            Title = title,
            Description = description,
            Metadata = metadata ?? "{}",
            CreatedAt = DateTimeOffset.UtcNow
        };
        db.Sources.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.SourceId;
    }

    public async Task<bool> UpdateSourceAsync(
        Guid sourceId,
        string? sourceType,
        string? uri,
        string? title,
        string? description,
        string? metadata,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Sources.FirstOrDefaultAsync(x => x.SourceId == sourceId, ct);
        if (entity is null) return false;
        if (sourceType is not null) entity.SourceType = sourceType;
        if (uri is not null) entity.Uri = uri;
        if (title is not null) entity.Title = title;
        if (description is not null) entity.Description = description;
        if (metadata is not null) entity.Metadata = metadata;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteSourceAsync(
        Guid sourceId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.Sources.FirstOrDefaultAsync(x => x.SourceId == sourceId, ct);
        if (entity is null) return false;
        db.Sources.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }
}

