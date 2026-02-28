using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using HotChocolate;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class ReportsQuery
{
    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ReportTemplate> ReportTemplates([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ReportTemplates.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ReportTemplateSection> ReportTemplateSections([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ReportTemplateSections.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ReportTemplateBlock> ReportTemplateBlocks([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ReportTemplateBlocks.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Report> Reports([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Reports.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ReportSection> ReportSections([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ReportSections.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ReportBlock> ReportBlocks([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ReportBlocks.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Source> Sources([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Sources.AsNoTracking();

    public async Task<ReportTemplate?> ReportTemplateByIdAsync(
        Guid templateId,
        int version,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportTemplates
            .AsNoTracking()
            .Include(x => x.Sections)
                .ThenInclude(x => x.Blocks)
            .FirstOrDefaultAsync(x => x.TemplateId == templateId && x.Version == version, ct);
    }

    public async Task<Report?> ReportByIdAsync(
        Guid reportId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Reports
            .AsNoTracking()
            .Include(x => x.Sections)
                .ThenInclude(x => x.Blocks)
            .Include(x => x.Sources)
            .FirstOrDefaultAsync(x => x.ReportId == reportId, ct);
    }

    public async Task<ReportTemplateSection?> ReportTemplateSectionByIdAsync(
        Guid templateSectionId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportTemplateSections
            .AsNoTracking()
            .Include(x => x.Blocks)
            .FirstOrDefaultAsync(x => x.TemplateSectionId == templateSectionId, ct);
    }

    public async Task<ReportSection?> ReportSectionByIdAsync(
        Guid reportSectionId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportSections
            .AsNoTracking()
            .Include(x => x.Blocks)
            .FirstOrDefaultAsync(x => x.ReportSectionId == reportSectionId, ct);
    }

    public async Task<ReportBlock?> ReportBlockByIdAsync(
        Guid reportBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportBlocks
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.ReportBlockId == reportBlockId, ct);
    }

    public async Task<Source?> SourceByIdAsync(
        Guid sourceId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Sources
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.SourceId == sourceId, ct);
    }

    // Convenience queries for block content
    public async Task<ReportBlockRichText?> ReportBlockRichTextByBlockIdAsync(
        Guid reportBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportBlockRichTexts
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.ReportBlockId == reportBlockId, ct);
    }

    public async Task<ReportBlockSingleMetric?> ReportBlockSingleMetricByBlockIdAsync(
        Guid reportBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportBlockSingleMetrics
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.ReportBlockId == reportBlockId, ct);
    }

    public async Task<ReportBlockMultiMetric?> ReportBlockMultiMetricByBlockIdAsync(
        Guid reportBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportBlockMultiMetrics
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.ReportBlockId == reportBlockId, ct);
    }

    public async Task<ReportBlockInsightCard?> ReportBlockInsightCardByBlockIdAsync(
        Guid reportBlockId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.ReportBlockInsightCards
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.ReportBlockId == reportBlockId, ct);
    }
}

