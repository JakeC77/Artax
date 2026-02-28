
namespace Geodesic.App.DataLayer.Entities;
public class Role
{
    public Guid TenantId { get; set; }
    public string RoleName { get; set; } = default!;
    public string? Description { get; set; }
}
