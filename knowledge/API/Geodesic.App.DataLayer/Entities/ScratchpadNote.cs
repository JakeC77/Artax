namespace Geodesic.App.DataLayer.Entities;

public class ScratchpadNote
{
    public Guid ScratchpadNoteId { get; set; }
    public Guid WorkspaceId { get; set; }
    public string Title { get; set; } = default!;
    public string Text { get; set; } = default!;
    public DateTimeOffset CreatedOn { get; set; }
}

