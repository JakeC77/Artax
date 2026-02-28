using System.Data.Common;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Npgsql;

namespace Geodesic.App.DataLayer.Tenancy;

public sealed class SetTenantInterceptor(IHttpContextAccessor accessor) : DbConnectionInterceptor
{
    private readonly IHttpContextAccessor _accessor = accessor;

    public override void ConnectionOpened(DbConnection connection, ConnectionEndEventData eventData)
    {
        string? tenantId = null;
        var http = _accessor.HttpContext;
        if (http is not null)
        {
            tenantId = http.User?.FindFirst("tid")?.Value;
            if (string.IsNullOrWhiteSpace(tenantId))
                tenantId = http.Request.Headers["X-Tenant-Id"].ToString();
        }

        // Allow non-HTTP contexts (e.g., workers) to set tenant via env var
        if (string.IsNullOrWhiteSpace(tenantId))
        {
            var envTid = Environment.GetEnvironmentVariable("APP_TENANT_ID");
            if (!string.IsNullOrWhiteSpace(envTid))
            {
                tenantId = envTid;
            }
        }

        if (connection is NpgsqlConnection npg && !string.IsNullOrWhiteSpace(tenantId))
        {
            using var cmd = npg.CreateCommand();
            cmd.CommandText = "select set_config('app.tenant_id', @p, true)";
            cmd.Parameters.AddWithValue("p", tenantId!);
            cmd.ExecuteNonQuery();
        }
        else
        {
            // Helpful hint when RLS rejects due to missing tenant
            System.Console.Error.WriteLine("SetTenantInterceptor: tenant id not resolved for request; ensure 'tid' claim or X-Tenant-Id header is present, or set APP_TENANT_ID for non-HTTP contexts.");
        }

        base.ConnectionOpened(connection, eventData);
    }
}
