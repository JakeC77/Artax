namespace Geodesic.App.DataLayer.Entities;

public class SemanticField
{
    public Guid SemanticFieldId { get; set; }
    public Guid SemanticEntityId { get; set; }
    public int Version { get; set; } = 1;
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public string? DataType { get; set; }
    public string? RangeInfo { get; set; }

    public SemanticEntity? SemanticEntity { get; set; }
}
