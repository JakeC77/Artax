namespace Geodesic.App.DataLayer.Entities;

public class Source
{
    public Guid SourceId { get; set; }
    public Guid ReportId { get; set; }
    public string SourceType { get; set; } = default!; // e.g., "document", "graph_node", "api_response"
    public string? Uri { get; set; } // URL or reference
    public string? Title { get; set; }
    public string? Description { get; set; }
    public string Metadata { get; set; } = "{}"; // jsonb, additional source metadata
    public DateTimeOffset CreatedAt { get; set; }

    public Report? Report { get; set; }
}

