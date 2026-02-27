using Azure.Storage.Blobs;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using SnapQuote.Core.Services;

var host = new HostBuilder()
    .ConfigureFunctionsWorkerDefaults()
    .ConfigureServices(services =>
    {
        // Azure OpenAI
        var openAiEndpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT") 
            ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT not configured");
        var openAiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_KEY")
            ?? throw new InvalidOperationException("AZURE_OPENAI_KEY not configured");
        var deploymentName = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT") ?? "gpt-4o";

        services.AddSingleton<IQuoteParser>(sp => 
            new QuoteParser(openAiEndpoint, openAiKey, deploymentName));

        // PDF Generator
        services.AddSingleton<IPdfGenerator, PdfGenerator>();

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
    })
    .Build();

host.Run();
