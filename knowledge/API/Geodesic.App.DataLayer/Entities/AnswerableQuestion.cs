namespace Geodesic.App.DataLayer.Entities;

public class AnswerableQuestion
{
    public Guid AnswerableQuestionId { get; set; }
    public Guid TenantId { get; set; }

    public string Question { get; set; } = default!;
    public string Query { get; set; } = default!;
    public string? Description { get; set; }
    public string ResultPlaybook { get; set; } = default!;
    public string[] RequiredVariables { get; set; } = Array.Empty<string>();
}

