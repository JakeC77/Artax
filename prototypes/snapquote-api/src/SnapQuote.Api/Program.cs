using Azure.Storage.Blobs;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using SnapQuote.Core.Services;
using SnapQuote.Infrastructure.Data;
using SnapQuote.Infrastructure.Repositories;

var host = new HostBuilder()
    .ConfigureFunctionsWorkerDefaults()
    .ConfigureServices(services =>
    {
        // Database
        var sqlConnection = Environment.GetEnvironmentVariable("SQL_CONNECTION_STRING")
            ?? "Server=(localdb)\\mssqllocaldb;Database=SnapQuote;Trusted_Connection=True;";
        services.AddDbContext<SnapQuoteDbContext>(options =>
            options.UseSqlServer(sqlConnection));

        // Repositories
        services.AddScoped<IUserRepository, UserRepository>();
        services.AddScoped<IQuoteRepository, QuoteRepository>();

        // Azure OpenAI - Quote Parser
        var openAiEndpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")
            ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT not configured");
        var openAiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_KEY")
            ?? throw new InvalidOperationException("AZURE_OPENAI_KEY not configured");
        var deploymentName = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT") ?? "gpt-4o";
        services.AddSingleton<IQuoteParser>(sp =>
            new QuoteParser(openAiEndpoint, openAiKey, deploymentName));

        // PDF Generator
        services.AddSingleton<IPdfGenerator, PdfGenerator>();

        // SMS Service (ClickSend)
        var clickSendKey = Environment.GetEnvironmentVariable("CLICKSEND_API_KEY") ?? "";
        var clickSendSecret = Environment.GetEnvironmentVariable("CLICKSEND_API_SECRET") ?? "";
        var smsFromNumber = Environment.GetEnvironmentVariable("SMS_FROM_NUMBER") ?? "";
        services.AddSingleton<ISmsService>(sp =>
            new ClickSendSmsService(clickSendKey, clickSendSecret, smsFromNumber));

        // Blob Storage
        var storageConnection = Environment.GetEnvironmentVariable("AZURE_STORAGE_CONNECTION")
            ?? throw new InvalidOperationException("AZURE_STORAGE_CONNECTION not configured");
        var containerName = Environment.GetEnvironmentVariable("BLOB_CONTAINER_NAME") ?? "snapquote";
        services.AddSingleton(sp =>
        {
            var blobServiceClient = new BlobServiceClient(storageConnection);
            var container = blobServiceClient.GetBlobContainerClient(containerName);
            container.CreateIfNotExists();
            return container;
        });

        // Logo Service
        var baseUrl = Environment.GetEnvironmentVariable("BASE_URL") ?? "https://snapquote.azurewebsites.net";
        services.AddSingleton<ILogoService>(sp =>
        {
            var container = sp.GetRequiredService<BlobContainerClient>();
            return new BlobLogoService(container, baseUrl);
        });

        // Subscription Service
        services.AddSingleton<ISubscriptionService, SubscriptionService>();
    })
    .Build();

host.Run();
