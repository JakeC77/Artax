
namespace Geodesic.App.DataLayer.Entities;
public class Tenant
{
    public Guid TenantId { get; set; }
    public string Name { get; set; } = default!;
    public string Region { get; set; } = "us";
    public DateTimeOffset CreatedAt { get; set; }
}
