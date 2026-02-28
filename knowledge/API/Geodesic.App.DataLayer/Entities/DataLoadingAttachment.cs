namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// One record per CSV upload for the data-loading workflow, scoped by tenant and ontology.
/// Holds storage path and runId once the workflow is started (for revisiting the stream).
/// </summary>
public class DataLoadingAttachment
{
    public Guid AttachmentId { get; set; }
    public Guid TenantId { get; set; }
    public Guid OntologyId { get; set; }
    public string FileName { get; set; } = default!;
    public string BlobPath { get; set; } = default!;
    public string? Uri { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public Guid? CreatedBy { get; set; }
    public Guid? RunId { get; set; }
    public string Status { get; set; } = "uploaded";
}
