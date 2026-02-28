using System.Collections.Concurrent;
using Geodesic.App.Api.Services;
using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using Neo4j.Driver;

namespace Geodesic.App.Api.Graph;

public sealed class Neo4jGraphServiceFactory : INeo4jGraphServiceFactory
{
    private readonly IDriver _defaultDriver;
    private readonly string? _defaultDatabase;
    private readonly IDbContextFactory<AppDbContext> _dbFactory;
    private readonly IOntologySecretProtection _secretProtection;
    private readonly ILogger<Neo4jGraphServiceFactory> _logger;
    private readonly ILogger<Neo4jGraphService> _graphServiceLogger;
    private readonly ConcurrentDictionary<Guid, IDriver> _driverCache = new();

    public Neo4jGraphServiceFactory(
        IDriver defaultDriver,
        IOptions<Neo4jOptions> neo4jOptions,
        IDbContextFactory<AppDbContext> dbFactory,
        IOntologySecretProtection secretProtection,
        ILogger<Neo4jGraphServiceFactory> logger,
        ILogger<Neo4jGraphService> graphServiceLogger)
    {
        _defaultDriver = defaultDriver;
        _defaultDatabase = string.IsNullOrWhiteSpace(neo4jOptions.Value.Database) ? null : neo4jOptions.Value.Database;
        _dbFactory = dbFactory;
        _secretProtection = secretProtection;
        _logger = logger;
        _graphServiceLogger = graphServiceLogger;
    }

    public async Task<INeo4jGraphService> GetGraphServiceForOntologyAsync(Guid ontologyId, CancellationToken ct = default)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var ontology = await db.Ontologies.AsNoTracking()
            .FirstOrDefaultAsync(o => o.OntologyId == ontologyId, ct);
        if (ontology is null ||
            string.IsNullOrWhiteSpace(ontology.Neo4jUri) ||
            string.IsNullOrWhiteSpace(ontology.Neo4jUsername) ||
            string.IsNullOrWhiteSpace(ontology.Neo4jEncryptedPassword))
            return new Neo4jGraphService(_defaultDriver, _defaultDatabase, _graphServiceLogger);

        var uri = ontology.Neo4jUri.Trim();
        var username = ontology.Neo4jUsername.Trim();
        string password;
        try
        {
            password = _secretProtection.Decrypt(ontology.Neo4jEncryptedPassword);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to decrypt Neo4j password for ontology {OntologyId}; using default connection.", ontologyId);
            return new Neo4jGraphService(_defaultDriver, _defaultDatabase, _graphServiceLogger);
        }

        var driver = _driverCache.GetOrAdd(ontologyId, _ => CreateDriver(uri, username, password));
        return new Neo4jGraphService(driver, database: null, _graphServiceLogger);
    }

    private static IDriver CreateDriver(string uri, string username, string password)
    {
        return GraphDatabase.Driver(
            uri,
            AuthTokens.Basic(username, password),
            o =>
            {
                o.WithMaxTransactionRetryTime(TimeSpan.FromSeconds(15));
                o.WithConnectionTimeout(TimeSpan.FromSeconds(5));
            });
    }

    public void InvalidateOntologyNeo4jCache(Guid ontologyId)
    {
        if (_driverCache.TryRemove(ontologyId, out var driver))
        {
            try { driver.Dispose(); } catch { /* ignore */ }
            _logger.LogDebug("Invalidated Neo4j driver cache for ontology {OntologyId}.", ontologyId);
        }
    }
}
