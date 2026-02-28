using HotChocolate;
using HotChocolate.Execution;
using HotChocolate.Resolvers;
using Microsoft.Extensions.Logging;

namespace Geodesic.App.Api.Graph;

public sealed class LoggingErrorFilter(ILogger<LoggingErrorFilter> logger) : IErrorFilter
{
    private readonly ILogger<LoggingErrorFilter> _logger = logger;

    public IError OnError(IError error)
    {
        // Log resolver exceptions with context once; avoid double-logging GraphQLException without InnerException
        if (error.Exception is not null)
        {
            var path = error.Path?.ToString() ?? "<no-path>";
            _logger.LogError(error.Exception, "GraphQL resolver error at {Path}: {Message}", path, error.Message);
        }
        return error;
    }
}

