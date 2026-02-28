using System.Text.RegularExpressions;

namespace Geodesic.App.Api.Graph;

/// <summary>
/// Validates that Cypher queries are read-only by checking for write operation keywords.
/// </summary>
public static class CypherQueryValidator
{
    // Write operation keywords that should be rejected
    private static readonly string[] WriteKeywords = new[]
    {
        "CREATE",
        "MERGE",
        "SET",
        "DELETE",
        "REMOVE",
        "DROP",
        "DETACH DELETE",
        "FOREACH"
    };

    /// <summary>
    /// Validates that the Cypher query is read-only.
    /// </summary>
    /// <param name="cypherQuery">The Cypher query to validate</param>
    /// <exception cref="ArgumentException">Thrown if the query contains write operations</exception>
    public static void ValidateReadOnly(string cypherQuery)
    {
        if (string.IsNullOrWhiteSpace(cypherQuery))
        {
            throw new ArgumentException("Cypher query cannot be null or empty.", nameof(cypherQuery));
        }

        // Remove comments and string literals to avoid false positives
        var sanitized = RemoveCommentsAndStrings(cypherQuery);

        // Check for write operation keywords (case-insensitive)
        foreach (var keyword in WriteKeywords)
        {
            // Use word boundary regex to avoid matching keywords within other words
            // For multi-word keywords like "DETACH DELETE", we need special handling
            if (keyword.Contains(' '))
            {
                // For multi-word keywords, check for the full phrase
                var pattern = $@"\b{Regex.Escape(keyword)}\b";
                if (Regex.IsMatch(sanitized, pattern, RegexOptions.IgnoreCase | RegexOptions.Multiline))
                {
                    throw new ArgumentException(
                        $"Cypher query contains write operation '{keyword}'. Only read-only queries are allowed.",
                        nameof(cypherQuery));
                }
            }
            else
            {
                // For single-word keywords, use word boundaries
                var pattern = $@"\b{Regex.Escape(keyword)}\b";
                if (Regex.IsMatch(sanitized, pattern, RegexOptions.IgnoreCase | RegexOptions.Multiline))
                {
                    throw new ArgumentException(
                        $"Cypher query contains write operation '{keyword}'. Only read-only queries are allowed.",
                        nameof(cypherQuery));
                }
            }
        }
    }

    /// <summary>
    /// Removes comments and string literals from the query to avoid false positives when checking for keywords.
    /// </summary>
    private static string RemoveCommentsAndStrings(string query)
    {
        var result = query;
        
        // Remove single-line comments (// ...)
        result = Regex.Replace(result, @"//.*?$", string.Empty, RegexOptions.Multiline);
        
        // Remove multi-line comments (/* ... */)
        result = Regex.Replace(result, @"/\*.*?\*/", string.Empty, RegexOptions.Singleline);
        
        // Remove single-quoted strings ('...')
        result = Regex.Replace(result, @"'([^'\\]|\\.)*'", "''", RegexOptions.None);
        
        // Remove double-quoted strings ("...")
        result = Regex.Replace(result, @"""([^""\\]|\\.)*""", "\"\"", RegexOptions.None);
        
        // Remove backtick-quoted identifiers (`...`)
        // Note: We keep backticks in the result but remove their content to preserve structure
        result = Regex.Replace(result, @"`([^`\\]|\\.)*`", "``", RegexOptions.None);
        
        return result;
    }
}

