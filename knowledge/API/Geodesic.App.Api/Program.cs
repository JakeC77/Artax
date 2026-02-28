using Geodesic.App.Api.Models;
using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Geodesic.App.DataLayer.Tenancy;
using Geodesic.App.Api.Graph;
using Geodesic.App.Api.Services;
using Neo4j.Driver;
using Microsoft.EntityFrameworkCore;
using Azure.Messaging.ServiceBus;
using Azure.Identity;
using Geodesic.App.Api.Messaging;
using Geodesic.App.Api.Storage;
using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using HotChocolate;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Geodesic.App.Api.Authentication;
using System.Security.Claims;
using System.Linq;

var builder = WebApplication.CreateBuilder(args);

// -------------------- Authentication Configuration --------------------
var authOptions = new AuthenticationOptions();
builder.Configuration.GetSection(AuthenticationOptions.SectionName).Bind(authOptions);

// Override with environment variables if provided
var envTenantId = Environment.GetEnvironmentVariable("ENTRA_EXTERNAL_ID_TENANT_ID");
var envAuthority = Environment.GetEnvironmentVariable("ENTRA_EXTERNAL_ID_AUTHORITY");
var envAudience = Environment.GetEnvironmentVariable("ENTRA_EXTERNAL_ID_AUDIENCE");

if (!string.IsNullOrWhiteSpace(envTenantId)) authOptions.TenantId = envTenantId;
if (!string.IsNullOrWhiteSpace(envAuthority)) authOptions.Authority = envAuthority;
if (!string.IsNullOrWhiteSpace(envAudience)) authOptions.Audience = envAudience;

builder.Services.Configure<AuthenticationOptions>(builder.Configuration.GetSection(AuthenticationOptions.SectionName));

// Register User Provisioning Service
builder.Services.AddScoped<IUserProvisioningService, UserProvisioningService>();

// Always add authorization services (required for UseAuthorization middleware).
// Do not set FallbackPolicy so only endpoints with .RequireAuthorization() need auth;
// /api/agent/* and /health use .AllowAnonymous() and their own access-key or no auth.
builder.Services.AddAuthorization(options =>
{
});

// Configure JWT Bearer Authentication
if (!string.IsNullOrWhiteSpace(authOptions.Authority) && !string.IsNullOrWhiteSpace(authOptions.Audience))
{
    builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
        .AddJwtBearer(options =>
        {
            // For Entra External ID, the issuer can be in different formats
            // We'll use the tenant ID to construct the proper issuer format
            // Format: https://{tenant-id}.ciamlogin.com/{tenant-id}/v2.0
            var authority = authOptions.Authority.TrimEnd('/');
            if (!string.IsNullOrWhiteSpace(authOptions.TenantId))
            {
                // Construct the issuer format that matches the token
                // Entra External ID tokens use: https://{tenant-id}.ciamlogin.com/{tenant-id}/v2.0
                var issuerBase = $"https://{authOptions.TenantId}.ciamlogin.com/{authOptions.TenantId}/v2.0";
                options.Authority = issuerBase;
            }
            else
            {
                options.Authority = authority;
            }
            
            options.Audience = authOptions.Audience;
            options.TokenValidationParameters = new TokenValidationParameters
            {
                ValidateIssuer = true,
                ValidateAudience = true,
                ValidateLifetime = true,
                ValidateIssuerSigningKey = true,
                ClockSkew = TimeSpan.FromSeconds(authOptions.ClockSkewSeconds),
                RequireSignedTokens = true,
                RequireExpirationTime = true,
                // For Entra External ID, we need to validate against the issuer format in the token
                // The issuer format is: https://{tenant-id}.ciamlogin.com/{tenant-id}/v2.0
                ValidIssuer = !string.IsNullOrWhiteSpace(authOptions.TenantId)
                    ? $"https://{authOptions.TenantId}.ciamlogin.com/{authOptions.TenantId}/v2.0"
                    : null
            };

            // Detailed logging for authentication events
            options.Events = new JwtBearerEvents
            {
                OnAuthenticationFailed = context =>
                {
                    var logger = context.HttpContext.RequestServices
                        .GetRequiredService<ILogger<Program>>();
                    
                    var authHeader = context.HttpContext.Request.Headers["Authorization"].ToString();
                    var hasToken = !string.IsNullOrWhiteSpace(authHeader) && authHeader.StartsWith("Bearer ");
                    
                    logger.LogError(
                        "Authentication failed. " +
                        "Exception: {ExceptionType}, " +
                        "Message: {Message}, " +
                        "HasAuthorizationHeader: {HasHeader}, " +
                        "Authority: {Authority}, " +
                        "Audience: {Audience}",
                        context.Exception?.GetType().Name ?? "Unknown",
                        context.Exception?.Message ?? "No exception message",
                        hasToken,
                        authOptions.Authority,
                        authOptions.Audience);

                    // Log inner exception details if available
                    if (context.Exception?.InnerException != null)
                    {
                        logger.LogError(
                            "Inner exception: {InnerExceptionType}, Message: {InnerMessage}",
                            context.Exception.InnerException.GetType().Name,
                            context.Exception.InnerException.Message);
                    }

                    return Task.CompletedTask;
                },
                OnTokenValidated = async context =>
                {
                    var logger = context.HttpContext.RequestServices
                        .GetRequiredService<ILogger<Program>>();
                    
                    // Log successful token validation with key claims
                    var claims = context.Principal?.Claims.ToList() ?? new List<Claim>();
                    var sub = claims.FirstOrDefault(c => c.Type == "sub")?.Value ?? "N/A";
                    var email = claims.FirstOrDefault(c => c.Type == "email" || c.Type == ClaimTypes.Email)?.Value ?? "N/A";
                    var preferredUsername = claims.FirstOrDefault(c => c.Type == "preferred_username")?.Value ?? "N/A";
                    var tid = claims.FirstOrDefault(c => c.Type == "tid" || c.Type == "http://schemas.microsoft.com/identity/claims/tenantid")?.Value ?? "N/A";
                    var aud = claims.FirstOrDefault(c => c.Type == "aud")?.Value ?? "N/A";
                    var iss = claims.FirstOrDefault(c => c.Type == "iss")?.Value ?? "N/A";
                    
                    // Log all claim types for debugging
                    var allClaimTypes = claims.Select(c => c.Type).Distinct().ToList();
                    
                    logger.LogInformation(
                        "Token validated successfully. " +
                        "Subject: {Subject}, " +
                        "Email: {Email}, " +
                        "PreferredUsername: {PreferredUsername}, " +
                        "TenantId: {TenantId}, " +
                        "Audience: {Audience}, " +
                        "Issuer: {Issuer}, " +
                        "AllClaimTypes: {ClaimTypes}",
                        sub, email, preferredUsername, tid, aud, iss, string.Join(", ", allClaimTypes));

                    // Provision user from claims
                    var provisioningService = context.HttpContext.RequestServices
                        .GetRequiredService<IUserProvisioningService>();
                    try
                    {
                        await provisioningService.ProvisionUserAsync(context.Principal!, context.HttpContext.RequestAborted);
                        logger.LogDebug("User provisioned successfully for Subject: {Subject}", sub);
                    }
                    catch (Exception ex)
                    {
                        logger.LogError(ex, 
                            "Failed to provision user from JWT claims. Subject: {Subject}, Email: {Email}", 
                            sub, email);
                        context.Fail("User provisioning failed");
                    }
                },
                OnChallenge = context =>
                {
                    var logger = context.HttpContext.RequestServices
                        .GetRequiredService<ILogger<Program>>();
                    
                    var authHeader = context.HttpContext.Request.Headers["Authorization"].ToString();
                    var path = context.HttpContext.Request.Path;
                    var method = context.HttpContext.Request.Method;
                    
                    logger.LogWarning(
                        "Authentication challenge triggered. " +
                        "Path: {Path}, " +
                        "Method: {Method}, " +
                        "HasAuthorizationHeader: {HasHeader}, " +
                        "Error: {Error}, " +
                        "ErrorDescription: {ErrorDescription}",
                        path,
                        method,
                        !string.IsNullOrWhiteSpace(authHeader),
                        context.Error ?? "None",
                        context.ErrorDescription ?? "None");

                    return Task.CompletedTask;
                },
                OnMessageReceived = context =>
                {
                    // Skip JWT validation for agent API; they use access key in Bearer or X-Api-Key
                    if (context.Request.Path.StartsWithSegments("/api/agent", StringComparison.OrdinalIgnoreCase))
                    {
                        context.Token = null;
                        return Task.CompletedTask;
                    }

                    var logger = context.HttpContext.RequestServices
                        .GetRequiredService<ILogger<Program>>();
                    var authHeader = context.Request.Headers["Authorization"].ToString();
                    var hasToken = !string.IsNullOrWhiteSpace(authHeader) && authHeader.StartsWith("Bearer ");

                    if (hasToken)
                    {
                        var tokenPreview = authHeader.Length > 50
                            ? authHeader.Substring(0, 50) + "..."
                            : authHeader;
                        logger.LogDebug("Received authorization header: {TokenPreview}", tokenPreview);
                    }
                    else
                    {
                        logger.LogWarning(
                            "No authorization header found. " +
                            "Path: {Path}, " +
                            "Method: {Method}",
                            context.Request.Path,
                            context.Request.Method);
                    }

                    return Task.CompletedTask;
                }
            };
        });
}
else
{
    // If authentication is not configured, add a default authentication scheme
    // This allows the app to start without authentication, but endpoints will still require it
    // In this case, requests will fail with 401 until authentication is properly configured
    builder.Services.AddAuthentication();
}

// -------------------- CORS Configuration --------------------
var corsOrigins = Environment.GetEnvironmentVariable("CORS_ALLOWED_ORIGINS");
var corsOriginsList = !string.IsNullOrWhiteSpace(corsOrigins)
    ? corsOrigins.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList()
    : builder.Configuration.GetSection("Cors:AllowedOrigins").Get<List<string>>() ?? new List<string>();

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        if (corsOriginsList.Count > 0)
        {
            policy.WithOrigins(corsOriginsList.ToArray())
                .AllowAnyHeader()
                .AllowAnyMethod()
                .AllowCredentials(); // Required for authenticated requests
        }
        else
        {
            // Fallback: allow any origin (for development only)
            // NOTE: This should be restricted in production
            policy
                .AllowAnyOrigin()
                .AllowAnyHeader()
                .AllowAnyMethod();
        }
    });
});

// Connection string: prefer non-empty APP_CONN, then non-empty appsettings, then default
var envCs = Environment.GetEnvironmentVariable("APP_CONN");
var configCs = builder.Configuration.GetConnectionString("App");
var cs = !string.IsNullOrWhiteSpace(envCs)
    ? envCs
    : (!string.IsNullOrWhiteSpace(configCs)
        ? configCs
        : "Host=localhost;Port=5432;Database=appdb;Username=postgres;Password=postgres");

System.Diagnostics.Debug.WriteLine("Effective DB connection string resolved from: " + (!string.IsNullOrWhiteSpace(envCs) ? "APP_CONN" : (!string.IsNullOrWhiteSpace(configCs) ? "appsettings.json" : "default")));
// Allow resolvers to read headers/claims for tenancy
builder.Services.AddHttpContextAccessor();
builder.Services.AddHttpClient();

// Interceptor that sets app.tenant_id per request (RLS)
// Uses IHttpContextAccessor internally, safe as singleton
builder.Services.AddSingleton<SetTenantInterceptor>();

// Pooled DbContext factory (resolver-safe)
builder.Services.AddPooledDbContextFactory<AppDbContext>((sp, opt) =>
{
    var interceptor = sp.GetService<SetTenantInterceptor>();
    opt.UseNpgsql(cs, o => o.SetPostgresVersion(new Version(16, 0)));
    opt.UseSnakeCaseNamingConvention();
    if (interceptor is not null)
        opt.AddInterceptors(interceptor);
});

// -------------------- Neo4j Graph --------------------
var envNeo4jUri = Environment.GetEnvironmentVariable("NEO4J_URI");
var envNeo4jUser = Environment.GetEnvironmentVariable("NEO4J_USERNAME");
var envNeo4jPass = Environment.GetEnvironmentVariable("NEO4J_PASSWORD");
var envNeo4jDb = Environment.GetEnvironmentVariable("NEO4J_DATABASE");

var cfgNeo4jUri = builder.Configuration["Neo4j:Uri"];
var cfgNeo4jUser = builder.Configuration["Neo4j:Username"];
var cfgNeo4jPass = builder.Configuration["Neo4j:Password"];
var cfgNeo4jDb = builder.Configuration["Neo4j:Database"];

string neo4jUri = !string.IsNullOrWhiteSpace(envNeo4jUri)
    ? envNeo4jUri
    : (!string.IsNullOrWhiteSpace(cfgNeo4jUri) ? cfgNeo4jUri : "bolt://localhost:7687");
string neo4jUser = !string.IsNullOrWhiteSpace(envNeo4jUser)
    ? envNeo4jUser
    : (!string.IsNullOrWhiteSpace(cfgNeo4jUser) ? cfgNeo4jUser : "neo4j");
string neo4jPass = !string.IsNullOrWhiteSpace(envNeo4jPass)
    ? envNeo4jPass
    : (!string.IsNullOrWhiteSpace(cfgNeo4jPass) ? cfgNeo4jPass : "password");
string? neo4jDb = !string.IsNullOrWhiteSpace(envNeo4jDb)
    ? envNeo4jDb
    : (!string.IsNullOrWhiteSpace(cfgNeo4jDb) ? cfgNeo4jDb : null);

Console.Error.WriteLine(
    "Effective Neo4j config from: " +
    $"Uri={(string.IsNullOrWhiteSpace(envNeo4jUri) ? (string.IsNullOrWhiteSpace(cfgNeo4jUri) ? "default" : "appsettings.json") : "env")} " +
    $"User={(string.IsNullOrWhiteSpace(envNeo4jUser) ? (string.IsNullOrWhiteSpace(cfgNeo4jUser) ? "default" : "appsettings.json") : "env")} " +
    $"Pass={(string.IsNullOrWhiteSpace(envNeo4jPass) ? (string.IsNullOrWhiteSpace(cfgNeo4jPass) ? "default" : "appsettings.json") : "env")} " +
    $"Db={(string.IsNullOrWhiteSpace(envNeo4jDb) ? (string.IsNullOrWhiteSpace(cfgNeo4jDb) ? "unset" : "appsettings.json") : "env")}");

builder.Services.AddSingleton<IDriver>(_ =>
    GraphDatabase.Driver(
        neo4jUri,
        AuthTokens.Basic(neo4jUser, neo4jPass),
        o =>
        {
            // Enable built-in retries for transient errors during transaction functions
            o.WithMaxTransactionRetryTime(TimeSpan.FromSeconds(15));
            // Optional: faster failure on bad connections (keep modest)
            o.WithConnectionTimeout(TimeSpan.FromSeconds(5));
        }));
builder.Services.AddScoped<INeo4jGraphService>(sp =>
    new Neo4jGraphService(sp.GetRequiredService<IDriver>(), neo4jDb, sp.GetService<ILogger<Neo4jGraphService>>()));
builder.Services.AddScoped<SemanticFieldRangeService>(sp =>
    new SemanticFieldRangeService(
        sp.GetRequiredService<IDbContextFactory<AppDbContext>>(),
        sp.GetRequiredService<IDriver>(),
        neo4jDb));
builder.Services.AddScoped<OntologySemanticSyncService>();
builder.Services.AddScoped<IAgentAccessKeyService, AgentAccessKeyService>();

// Per-ontology Neo4j: encryption and factory (optional EncryptionKeyBase64; required when setting per-ontology credentials)
builder.Services.Configure<Neo4jOptions>(o =>
{
    o.Uri = neo4jUri;
    o.Username = neo4jUser;
    o.Password = neo4jPass;
    o.Database = neo4jDb ?? string.Empty;
});
builder.Services.Configure<Geodesic.App.Api.Services.OntologySecretProtectionOptions>(
    builder.Configuration.GetSection(Geodesic.App.Api.Services.OntologySecretProtectionOptions.SectionName));
builder.Services.AddSingleton<Geodesic.App.Api.Services.IOntologySecretProtection, Geodesic.App.Api.Services.OntologySecretProtection>();
builder.Services.AddSingleton<INeo4jGraphServiceFactory, Neo4jGraphServiceFactory>();

// -------------------- Azure Service Bus (ScenarioRun events) --------------------
// Read from env first, then appsettings
var envSbConn = Environment.GetEnvironmentVariable("AZURE_SERVICEBUS_CONNECTION_STRING");
var envSbQueue = Environment.GetEnvironmentVariable("SCENARIO_RUNS_QUEUE");
var cfgSbConn = builder.Configuration["ServiceBus:ConnectionString"];
var cfgSbQueue = builder.Configuration["ServiceBus:QueueName"];

builder.Services.Configure<ServiceBusOptions>(o =>
{
    o.ConnectionString = !string.IsNullOrWhiteSpace(envSbConn) ? envSbConn : cfgSbConn;
    o.QueueName = !string.IsNullOrWhiteSpace(envSbQueue) ? envSbQueue : cfgSbQueue;
});

builder.Services.AddSingleton<IScenarioRunEventPublisher, AzureScenarioRunEventPublisher>();


// -------------------- Service Bus (Queue Sender) --------------------
var sbConn = builder.Configuration["ServiceBus:ConnectionString"] ?? Environment.GetEnvironmentVariable("SB_CONNECTION");
var sbNamespace = builder.Configuration["ServiceBus:FullyQualifiedNamespace"] ?? Environment.GetEnvironmentVariable("SB_NAMESPACE");
var sbQueue = builder.Configuration["ServiceBus:Queue"] ?? Environment.GetEnvironmentVariable("SB_QUEUE") ?? "scenario-runs-dev";

var sbConfigured = !string.IsNullOrWhiteSpace(sbConn) || !string.IsNullOrWhiteSpace(sbNamespace);
if (sbConfigured)
{
    builder.Services.AddSingleton<ServiceBusClient>(_ =>
    {
        if (!string.IsNullOrWhiteSpace(sbConn))
            return new ServiceBusClient(sbConn);
        return new ServiceBusClient(sbNamespace!, new DefaultAzureCredential());
    });
    builder.Services.AddSingleton(sp =>
    {
        var client = sp.GetRequiredService<ServiceBusClient>();
        return client.CreateSender(sbQueue);
    });
}
// If Service Bus not configured, GetService<ServiceBusSender>() will return null

// -------------------- Workflow dispatch (Service Bus or Container Apps Job) --------------------
builder.Services.Configure<WorkflowDispatchOptions>(builder.Configuration.GetSection(WorkflowDispatchOptions.SectionName));
builder.Services.AddSingleton<IWorkflowDispatcher>(sp =>
{
    var options = sp.GetRequiredService<Microsoft.Extensions.Options.IOptions<WorkflowDispatchOptions>>().Value;
    var mode = options.Mode?.Trim() ?? "ServiceBus";
    if (string.Equals(mode, "ContainerAppsJob", StringComparison.OrdinalIgnoreCase))
    {
        var credentialOptions = new DefaultAzureCredentialOptions();
        if (!string.IsNullOrWhiteSpace(options.TenantId))
            credentialOptions.TenantId = options.TenantId;
        return new ContainerAppsJobWorkflowDispatcher(
            sp.GetRequiredService<Microsoft.Extensions.Options.IOptions<WorkflowDispatchOptions>>(),
            sp.GetRequiredService<Microsoft.Extensions.Options.IOptions<AzureStorageOptions>>(),
            new DefaultAzureCredential(credentialOptions),
            sp.GetService<Microsoft.Extensions.Logging.ILogger<ContainerAppsJobWorkflowDispatcher>>());
    }
    return new ServiceBusWorkflowDispatcher(
        sp.GetService<ServiceBusSender>(),
        sp.GetService<Microsoft.Extensions.Logging.ILogger<ServiceBusWorkflowDispatcher>>());
});

// DataLoader registrations (scoped per request)
builder.Services.AddScoped<Geodesic.App.Api.DataLoaders.UsersByIdLoader>();
builder.Services.AddScoped<Geodesic.App.Api.DataLoaders.WorkspaceMembersByWorkspaceIdLoader>();

// -------------------- Azure Blob Storage (Scratchpad uploads) --------------------
var envBlobConn = Environment.GetEnvironmentVariable("AZURE_STORAGE_CONNECTION_STRING");
var envBlobSvcUri = Environment.GetEnvironmentVariable("AZURE_BLOB_SERVICE_URI");
var envAttachContainer = Environment.GetEnvironmentVariable("SCRATCHPAD_ATTACHMENTS_CONTAINER");

builder.Services.Configure<AzureStorageOptions>(o =>
{
    o.ConnectionString = !string.IsNullOrWhiteSpace(envBlobConn) ? envBlobConn : builder.Configuration["AzureStorage:ConnectionString"];
    o.ServiceUri = !string.IsNullOrWhiteSpace(envBlobSvcUri) ? envBlobSvcUri : builder.Configuration["AzureStorage:ServiceUri"];
    o.AttachmentsContainer = !string.IsNullOrWhiteSpace(envAttachContainer) ? envAttachContainer : (builder.Configuration["AzureStorage:AttachmentsContainer"] ?? "scratchpad-attachments");
});
builder.Services.AddSingleton<IFileStorage, AzureBlobFileStorage>();

// GraphQL server
builder.Services
    .AddGraphQLServer()
    .AddQueryType<Query>()
    .AddTypeExtension<Geodesic.App.Api.Types.EntitiesQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.AnswerableQuestionsQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.WorkspaceNodesQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.GraphQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.FeedbackQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.ReportsQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.ScenarioRunsQuery>()
    .AddTypeExtension<Geodesic.App.Api.Types.WorkspaceSetupQuery>()
    .AddMutationType<Mutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.EntitiesMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.AnswerableQuestionsMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.WorkspaceNodesMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.GraphMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.ScenarioRunsMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.FeedbackMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.ReportsMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.WorkspaceSetupMutation>()
    .AddTypeExtension<Geodesic.App.Api.Types.WorkspaceTypeExtensions>()
    .AddTypeExtension<Geodesic.App.Api.Types.WorkspaceMemberTypeExtensions>()
    .AddTypeExtension<Geodesic.App.Api.Types.OntologyTypeExtensions>()
    .AddTypeExtension<Geodesic.App.Api.Types.IntentTypeExtensions>()
    .AddTypeExtension<Geodesic.App.Api.Types.AgentRoleTypeExtensions>()
    .AddTypeExtension<Geodesic.App.Api.Types.AgentRoleAccessKeyTypeExtensions>()
    // Allow arbitrary JSON-like values for graph properties
    .AddType<HotChocolate.Types.AnyType>()
    .AddUploadType()
    .AddErrorFilter<Geodesic.App.Api.Graph.LoggingErrorFilter>()
    .AddProjections()
    .AddFiltering()
    .AddSorting();

var app = builder.Build();

// Log Service Bus and Neo4j encryption key at startup (no secrets)
using (var scope = app.Services.CreateScope())
{
    var startupLogger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();
    if (sbConfigured)
    {
        var authMode = !string.IsNullOrWhiteSpace(sbConn) ? "ConnectionString" : "ManagedIdentity";
        startupLogger.LogInformation(
            "Service Bus configured. Queue={Queue}, Auth={AuthMode}",
            sbQueue, authMode);
    }
    else
    {
        startupLogger.LogWarning(
            "Service Bus not configured (no ConnectionString or FullyQualifiedNamespace). Document indexing and scenario run messages will not be sent.");
    }

    var neo4jEncryptionKey = app.Configuration["Neo4j:EncryptionKeyBase64"];
    if (string.IsNullOrWhiteSpace(neo4jEncryptionKey))
    {
        startupLogger.LogWarning(
            "Neo4j:EncryptionKeyBase64 is null or empty. Per-ontology Neo4j credentials (setOntologyNeo4jConnection) will not work until this is set to a base64-encoded 32-byte key.");
    }
}

// Enable CORS before authentication
app.UseCors();

// Enable Authentication and Authorization
app.UseAuthentication();
app.UseAuthorization();

// Enable GraphQL endpoint and allow multipart/form-data (file uploads)
// Require auth when GraphQL:RequireAuthorization is true (default); set false in appsettings for local UI access.
// When false, must AllowAnonymous so the endpoint opts out of the global FallbackPolicy (require auth).
var requireGraphQLAuth = app.Configuration.GetValue<bool>("GraphQL:RequireAuthorization", true);
var graphqlMap = app.MapGraphQL("/gql")
    .WithMetadata(new Microsoft.AspNetCore.Mvc.ConsumesAttribute(
        "application/json", new string[] { "application/graphql", "multipart/form-data" }))
    .WithOptions(new HotChocolate.AspNetCore.GraphQLServerOptions
    {
        EnableMultipartRequests = true,
        EnforceMultipartRequestsPreflightHeader = false
    }); // Banana Cake Pop at /gql
if (requireGraphQLAuth)
    graphqlMap.RequireAuthorization();
else
    graphqlMap.AllowAnonymous();

// Health check endpoint (no authentication required)
app.MapGet("/health", () => Results.Ok(new { status = "healthy", timestamp = DateTimeOffset.UtcNow }))
    .AllowAnonymous();

app.MapGet("/", () => Results.Redirect("/gql"));

// Agent intent-execution API (REST-like; auth via access key, not JWT)
app.MapGet("/api/agent/intents", async (
    HttpRequest request,
    [Service] IAgentAccessKeyService accessKeyService,
    [Service] IDbContextFactory<AppDbContext> dbFactory,
    CancellationToken ct) =>
{
    var authHeader = request.Headers.Authorization.ToString();
    var apiKeyHeader = request.Headers["X-Api-Key"].ToString();
    var rawKey = !string.IsNullOrWhiteSpace(authHeader) && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
        ? authHeader["Bearer ".Length..].Trim()
        : (!string.IsNullOrWhiteSpace(apiKeyHeader) ? apiKeyHeader.Trim() : null);

    if (string.IsNullOrEmpty(rawKey))
        return Results.Json(new { error = "Missing or invalid access key" }, statusCode: 401);

    var validation = await accessKeyService.ValidateAccessKeyAsync(rawKey, ct);
    if (validation is null)
        return Results.Json(new { error = "Missing or invalid access key" }, statusCode: 401);

    var (role, _) = validation.Value;
    await using var db = await dbFactory.CreateDbContextAsync(ct);
    var intentIds = await db.AgentRoleIntents.AsNoTracking()
        .Where(x => x.AgentRoleId == role.AgentRoleId)
        .Select(x => x.IntentId)
        .ToListAsync(ct);
    var intents = intentIds.Count == 0
        ? new List<Intent>()
        : await db.Intents.AsNoTracking().Where(i => intentIds.Contains(i.IntentId)).ToListAsync(ct);

    var dtos = intents.Select(i => new AgentIntentDto
    {
        IntentId = i.IntentId,
        OpId = i.OpId,
        IntentName = i.IntentName,
        Route = i.Route,
        Description = i.Description,
        DataSource = i.DataSource,
        InputSchema = i.InputSchema,
        OutputSchema = i.OutputSchema,
        Grounding = i.Grounding,
        OntologyId = i.OntologyId,
        CreatedOn = i.CreatedOn,
        LastEdit = i.LastEdit
    }).ToList();

    return Results.Json(dtos);
})
.AllowAnonymous();

// Execute intent: run grounding Cypher with parameters (same access-key auth)
app.MapPost("/api/agent/intents/execute", async (
    HttpRequest request,
    [Service] IAgentAccessKeyService accessKeyService,
    [Service] IDbContextFactory<AppDbContext> dbFactory,
    [Service] INeo4jGraphServiceFactory neo4jFactory,
    [Service] INeo4jGraphService defaultGraph,
    CancellationToken ct) =>
{
    var authHeader = request.Headers.Authorization.ToString();
    var apiKeyHeader = request.Headers["X-Api-Key"].ToString();
    var rawKey = !string.IsNullOrWhiteSpace(authHeader) && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
        ? authHeader["Bearer ".Length..].Trim()
        : (!string.IsNullOrWhiteSpace(apiKeyHeader) ? apiKeyHeader.Trim() : null);

    if (string.IsNullOrEmpty(rawKey))
        return Results.Json(new { error = "Missing or invalid access key" }, statusCode: 401);

    var validation = await accessKeyService.ValidateAccessKeyAsync(rawKey, ct);
    if (validation is null)
        return Results.Json(new { error = "Missing or invalid access key" }, statusCode: 401);

    var (role, _) = validation.Value;

    ExecuteIntentRequest? body;
    try
    {
        body = await request.ReadFromJsonAsync<ExecuteIntentRequest>(ct);
    }
    catch
    {
        return Results.Json(new { error = "Invalid request body." }, statusCode: 400);
    }

    if (body is null || (!body.IntentId.HasValue && string.IsNullOrWhiteSpace(body.OpId)))
        return Results.Json(new { error = "Request must include opId or intentId." }, statusCode: 400);

    await using var db = await dbFactory.CreateDbContextAsync(ct);
    var intentIds = await db.AgentRoleIntents.AsNoTracking()
        .Where(x => x.AgentRoleId == role.AgentRoleId)
        .Select(x => x.IntentId)
        .ToListAsync(ct);
    if (intentIds.Count == 0)
        return Results.Json(new { error = "Intent not found or not allowed for this role." }, statusCode: 404);

    Intent? intent = null;
    if (body.IntentId.HasValue)
    {
        if (!intentIds.Contains(body.IntentId.Value))
            return Results.Json(new { error = "Intent not allowed for this role." }, statusCode: 403);
        intent = await db.Intents.AsNoTracking().FirstOrDefaultAsync(i => i.IntentId == body.IntentId.Value && i.TenantId == role.TenantId, ct);
    }
    else
    {
        var allowedIntents = await db.Intents.AsNoTracking().Where(i => intentIds.Contains(i.IntentId)).ToListAsync(ct);
        intent = allowedIntents.FirstOrDefault(i => string.Equals(i.OpId, body.OpId!.Trim(), StringComparison.OrdinalIgnoreCase));
    }

    if (intent is null)
        return Results.Json(new { error = "Intent not found or not allowed for this role." }, statusCode: 404);

    if (string.IsNullOrWhiteSpace(intent.Grounding))
        return Results.Json(new { error = "Intent has no grounding query." }, statusCode: 400);

    var graph = intent.OntologyId.HasValue
        ? await neo4jFactory.GetGraphServiceForOntologyAsync(intent.OntologyId.Value, ct)
        : defaultGraph;

    var paramDict = ToNeo4jParameters(body.Parameters);

    CypherRowResult cypherResult;
    try
    {
        cypherResult = await graph.ExecuteCypherRowsAsync(intent.Grounding, paramDict, limit: 10_000, ct);
    }
    catch (ArgumentException)
    {
        return Results.Json(new { error = "Invalid grounding query or parameters." }, statusCode: 400);
    }
    catch (Exception)
    {
        return Results.Json(new { error = "Graph execution failed." }, statusCode: 502);
    }

    var response = new ExecuteIntentResponse
    {
        Columns = cypherResult.Columns,
        Rows = cypherResult.Rows,
        RowCount = cypherResult.RowCount,
        Truncated = cypherResult.Truncated
    };
    return Results.Json(response);

    static Dictionary<string, object?>? ToNeo4jParameters(Dictionary<string, object?>? parameters)
    {
        if (parameters is null || parameters.Count == 0)
            return null;
        var result = new Dictionary<string, object?>();
        foreach (var kv in parameters)
            result[kv.Key] = ToNeo4jValue(kv.Value);
        return result;
    }

    static object? ToNeo4jValue(object? value)
    {
        if (value is null)
            return null;
        if (value is System.Text.Json.JsonElement je)
        {
            return je.ValueKind switch
            {
                System.Text.Json.JsonValueKind.String => je.GetString(),
                System.Text.Json.JsonValueKind.Number => je.TryGetInt64(out var l) ? l : je.GetDouble(),
                System.Text.Json.JsonValueKind.True => true,
                System.Text.Json.JsonValueKind.False => false,
                System.Text.Json.JsonValueKind.Null => null,
                System.Text.Json.JsonValueKind.Array => je.EnumerateArray().Select(e => ToNeo4jValue(e)).ToList(),
                System.Text.Json.JsonValueKind.Object => je.EnumerateObject().ToDictionary(p => p.Name, p => ToNeo4jValue(p.Value)),
                _ => je.GetRawText()
            };
        }
        if (value is string or long or int or double or bool)
            return value;
        return value;
    }
})
.AllowAnonymous();

// SSE stream of scenario run logs (tenant-scoped via X-Tenant-Id header)
// Requires authentication
app.MapGet("/runs/{runId:guid}/events", async (
    Guid runId,
    HttpContext http,
    [Service] IDbContextFactory<AppDbContext> dbFactory,
    CancellationToken ct) =>
{
    http.Response.Headers.ContentType = "text/event-stream";
    http.Response.Headers.CacheControl = "no-cache";
    http.Response.Headers["X-Accel-Buffering"] = "no";
    await using var db = await dbFactory.CreateDbContextAsync(ct);

    // Allow tenant to be provided via header or query string for SSE (EventSource cannot set custom headers)
    var tidHeader = http.Request.Headers["X-Tenant-Id"].ToString();
    var tidQuery = http.Request.Query["tid"].ToString();
    var tid = !string.IsNullOrWhiteSpace(tidHeader) ? tidHeader : tidQuery;
    if (!string.IsNullOrWhiteSpace(tid))
    {
        try
        {
            await db.Database.ExecuteSqlRawAsync("select set_config('app.tenant_id', {0}, true)", [tid], ct);
        }
        catch { /* best effort; if RLS blocks, no logs will stream */ }
    }

    long lastId = 0;
    // Send any existing logs, then tail for new ones
    while (!ct.IsCancellationRequested)
    {
        var logs = await db.ScenarioRunLogs
            .AsNoTracking()
            .Where(x => x.RunId == runId && x.LogId > lastId)
            .OrderBy(x => x.LogId)
            .Take(100)
            .ToListAsync(ct);

        foreach (var log in logs)
        {
            lastId = log.LogId;
            var payload = log.Content.Replace("\n", "\\n");
            await http.Response.WriteAsync($"id: {lastId}\n", ct);
            await http.Response.WriteAsync("event: message\n", ct);
            await http.Response.WriteAsync($"data: {payload}\n\n", ct);
            await http.Response.Body.FlushAsync(ct);
        }

        // heartbeat to keep connection alive
        await http.Response.WriteAsync(":\n\n", ct);
        await http.Response.Body.FlushAsync(ct);

        await Task.Delay(500, ct);
    }
})
.RequireAuthorization();

// Download a scratchpad attachment by ID via server (authz via tenant RLS)
// Requires authentication
app.MapGet("/scratchpad/attachments/{scratchpadAttachmentId:guid}/download", async (
    Guid scratchpadAttachmentId,
    [Service] IDbContextFactory<AppDbContext> dbFactory,
    [Service] Microsoft.Extensions.Options.IOptions<AzureStorageOptions> storageOptions,
    CancellationToken ct) =>
{
    await using var db = await dbFactory.CreateDbContextAsync(ct);
    var attachment = await db.ScratchpadAttachments
        .AsNoTracking()
        .FirstOrDefaultAsync(x => x.ScratchpadAttachmentId == scratchpadAttachmentId, ct);

    if (attachment is null)
        return Results.NotFound();

    if (string.IsNullOrWhiteSpace(attachment.Uri))
        return Results.Problem("Attachment has no backing storage URI.", statusCode: 500);

    Uri uri;
    try { uri = new Uri(attachment.Uri); }
    catch { return Results.Problem("Invalid attachment URI.", statusCode: 500); }

    var path = uri.AbsolutePath.Trim('/');
    var segs = path.Split('/', 2);
    if (segs.Length < 2)
        return Results.Problem("Malformed storage path.", statusCode: 500);

    var container = segs[0];
    var blobPath = segs[1];

    var opts = storageOptions.Value;
    BlobServiceClient svc;
    if (!string.IsNullOrWhiteSpace(opts.ConnectionString))
    {
        svc = new BlobServiceClient(opts.ConnectionString);
    }
    else if (!string.IsNullOrWhiteSpace(opts.ServiceUri))
    {
        svc = new BlobServiceClient(new Uri(opts.ServiceUri), new DefaultAzureCredential());
    }
    else
    {
        return Results.Problem("Azure Storage not configured.", statusCode: 500);
    }

    var blob = svc.GetBlobContainerClient(container).GetBlobClient(blobPath);
    try
    {
        var resp = await blob.DownloadStreamingAsync(cancellationToken: ct);
        var contentType = resp.Value.Details.ContentType ?? attachment.FileType ?? "application/octet-stream";
        var fileName = System.IO.Path.GetFileName(blobPath);
        return Results.Stream(resp.Value.Content, contentType: contentType, fileDownloadName: fileName);
    }
    catch (Azure.RequestFailedException ex) when (ex.Status == 404)
    {
        return Results.NotFound();
    }
})
.RequireAuthorization();

// Download ontology draft.json (authz via tenant RLS when using DB)
app.MapGet("/api/ontology/{ontologyId:guid}/draft/download", async (
    Guid ontologyId,
    [Service] IDbContextFactory<AppDbContext> dbFactory,
    [Service] Microsoft.Extensions.Options.IOptions<AzureStorageOptions> storageOptions,
    CancellationToken ct) =>
{
    await using var db = await dbFactory.CreateDbContextAsync(ct);
    var ontology = await db.Ontologies
        .AsNoTracking()
        .FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
    if (ontology is null)
        return Results.NotFound();

    string container;
    string blobPath;
    var jsonUri = ontology.JsonUri?.Trim();
    if (!string.IsNullOrEmpty(jsonUri) && Uri.TryCreate(jsonUri, UriKind.Absolute, out var uri) &&
        (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps) &&
        uri.Host.Contains(".blob.core.windows.net", StringComparison.OrdinalIgnoreCase))
    {
        var pathSegments = uri.AbsolutePath.TrimStart('/').Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (pathSegments.Length < 2)
            return Results.NotFound();
        container = pathSegments[0];
        blobPath = string.Join("/", pathSegments.Skip(1));
    }
    else if (!string.IsNullOrEmpty(jsonUri))
    {
        container = "scratchpad-attachments";
        blobPath = jsonUri;
    }
    else
    {
        container = "scratchpad-attachments";
        blobPath = $"ontology-drafts/{Guid.Empty:D}/{ontology.OntologyId}/draft.json";
    }

    var opts = storageOptions.Value;
    BlobServiceClient svc;
    if (!string.IsNullOrWhiteSpace(opts.ConnectionString))
        svc = new BlobServiceClient(opts.ConnectionString);
    else if (!string.IsNullOrWhiteSpace(opts.ServiceUri))
        svc = new BlobServiceClient(new Uri(opts.ServiceUri), new DefaultAzureCredential());
    else
        return Results.Problem("Azure Storage not configured.", statusCode: 500);

    var blob = svc.GetBlobContainerClient(container).GetBlobClient(blobPath);
    try
    {
        var resp = await blob.DownloadStreamingAsync(cancellationToken: ct);
        var contentType = resp.Value.Details.ContentType ?? "application/json";
        var fileName = string.IsNullOrWhiteSpace(ontology.Name)
            ? "draft.json"
            : string.Concat(ontology.Name.Split(System.IO.Path.GetInvalidFileNameChars())) + ".json";
        return Results.Stream(resp.Value.Content, contentType: contentType, fileDownloadName: fileName);
    }
    catch (Azure.RequestFailedException ex) when (ex.Status == 404)
    {
        return Results.NotFound();
    }
})
.RequireAuthorization();

app.Run();

// -------------------- GraphQL Root Types --------------------
public class Query
{
    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Geodesic.App.DataLayer.Entities.Workspace> Workspaces(
        [Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Workspaces.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Geodesic.App.DataLayer.Entities.User> Users(
        [Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Users.AsNoTracking();
}

// Base Mutation class - extended by mutation classes in Types folder
public class Mutation
{
}
