namespace Geodesic.App.DataLayer.Entities;

public class ScratchpadAttachment
{
    public Guid ScratchpadAttachmentId { get; set; }
    public Guid WorkspaceId { get; set; }
    public string Title { get; set; } = default!;
    public string? Description { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public string? Uri { get; set; }
    public string? FileType { get; set; }
    public long? Size { get; set; }
    public string ProcessingStatus { get; set; } = "unprocessed";
    public string? ProcessingError { get; set; }
}

