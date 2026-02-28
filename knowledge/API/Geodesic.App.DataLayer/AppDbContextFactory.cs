using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace Geodesic.App.DataLayer;

public sealed class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
{
    public AppDbContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<AppDbContext>();
        // Design-time only: use a local default; actual runtime config happens in API Program.cs
        var cs = "Host=localhost;Port=5432;Database=appdb;Username=postgres;Password=postgres";
        optionsBuilder.UseNpgsql(cs, o => o.SetPostgresVersion(new Version(16, 0)));
        optionsBuilder.UseSnakeCaseNamingConvention();
        return new AppDbContext(optionsBuilder.Options);
    }
}

