namespace Geodesic.App.Api.Graph;

/// <summary>
/// Resolves the appropriate Neo4j graph service for an ontology.
/// When the ontology has custom Neo4j connection (Uri/Username/EncryptedPassword), uses that instance;
/// otherwise returns the app default.
/// </summary>
public interface INeo4jGraphServiceFactory
{
    /// <summary>
    /// Returns a graph service for the given ontology. Uses per-ontology Neo4j when configured; otherwise default.
    /// </summary>
    Task<INeo4jGraphService> GetGraphServiceForOntologyAsync(Guid ontologyId, CancellationToken ct = default);

    /// <summary>
    /// Invalidates cached driver/service for the ontology (call after set/clear connection).
    /// </summary>
    void InvalidateOntologyNeo4jCache(Guid ontologyId);
}
