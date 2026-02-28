namespace Geodesic.App.DataLayer.Entities;

public class ReportBlockRichText
{
    public Guid ReportBlockId { get; set; }
    public string Content { get; set; } = default!; // markdown content

    public ReportBlock? ReportBlock { get; set; }
}

