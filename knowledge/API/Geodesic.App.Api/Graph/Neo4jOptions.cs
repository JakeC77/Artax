using System.Diagnostics.CodeAnalysis;

namespace Geodesic.App.Api.Graph;

public sealed class Neo4jOptions
{
    public string Uri { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
    public string? Database { get; set; }
}

