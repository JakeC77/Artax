using System.Text;
using System.Text.Json;
using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class AnswerableQuestionsQuery
{
    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<AnswerableQuestion> AnswerableQuestions([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().AnswerableQuestions.AsNoTracking();

    public Task<AnswerableQuestion?> AnswerableQuestionByIdAsync(
        Guid answerableQuestionId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
        => dbFactory.CreateDbContext().AnswerableQuestions.AsNoTracking()
            .FirstOrDefaultAsync(x => x.AnswerableQuestionId == answerableQuestionId, ct);
}

public sealed class AnswerQuestionPayload
{
    public Guid AnswerableQuestionId { get; set; }
    public string Question { get; set; } = default!;
    public string ResultPlaybook { get; set; } = default!;
    [GraphQLType(typeof(AnyType))]
    public object? Response { get; set; }
}

[ExtendObjectType(typeof(Mutation))]
public sealed class AnswerableQuestionsMutation
{
    public async Task<Guid> CreateAnswerableQuestionAsync(
        Guid tenantId,
        string question,
        string query,
        string? description,
        string resultPlaybook,
        string[]? requiredVariables,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = new AnswerableQuestion
        {
            AnswerableQuestionId = Guid.NewGuid(),
            TenantId = tenantId,
            Question = question,
            Query = query,
            Description = description,
            ResultPlaybook = resultPlaybook,
            RequiredVariables = requiredVariables ?? Array.Empty<string>()
        };
        db.AnswerableQuestions.Add(entity);
        await db.SaveChangesAsync(ct);
        return entity.AnswerableQuestionId;
    }

    public async Task<bool> UpdateAnswerableQuestionAsync(
        Guid answerableQuestionId,
        string? question,
        string? query,
        string? description,
        string? resultPlaybook,
        string[]? requiredVariables,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AnswerableQuestions.FirstOrDefaultAsync(x => x.AnswerableQuestionId == answerableQuestionId, ct);
        if (entity is null) return false;
        if (question is not null) entity.Question = question;
        if (query is not null) entity.Query = query;
        if (description is not null) entity.Description = description;
        if (resultPlaybook is not null) entity.ResultPlaybook = resultPlaybook;
        if (requiredVariables is not null) entity.RequiredVariables = requiredVariables;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteAnswerableQuestionAsync(
        Guid answerableQuestionId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var entity = await db.AnswerableQuestions.FirstOrDefaultAsync(x => x.AnswerableQuestionId == answerableQuestionId, ct);
        if (entity is null) return false;
        db.AnswerableQuestions.Remove(entity);
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<AnswerQuestionPayload?> AnswerQuestionAsync(
        string question,
        Dictionary<string, string> variables,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpClientFactory httpClientFactory,
        [Service] IConfiguration configuration,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var aq = await db.AnswerableQuestions.AsNoTracking()
            .FirstOrDefaultAsync(x => x.Question == question, ct);
        if (aq is null) return null;

        var renderedQuery = aq.Query;
        if (variables is not null)
        {
            foreach (var kv in variables)
            {
                var token = "{{" + kv.Key + "}}";
                renderedQuery = renderedQuery.Replace(token, kv.Value ?? string.Empty);
            }
        }

        var endpoint = Environment.GetEnvironmentVariable("EXTERNAL_GQL_ENDPOINT")
            ?? configuration["ExternalGql:Endpoint"]
            ?? string.Empty;

        object? responseObj = null;
        if (!string.IsNullOrWhiteSpace(endpoint))
        {
            var client = httpClientFactory.CreateClient();
            using var req = new HttpRequestMessage(HttpMethod.Post, endpoint);
            var payload = new { query = renderedQuery };
            var json = JsonSerializer.Serialize(payload);
            req.Content = new StringContent(json, Encoding.UTF8, "application/json");
            using var resp = await client.SendAsync(req, ct);
            var respStr = await resp.Content.ReadAsStringAsync(ct);
            try
            {
                responseObj = JsonSerializer.Deserialize<JsonElement>(respStr);
            }
            catch
            {
                responseObj = respStr;
            }
        }

        return new AnswerQuestionPayload
        {
            AnswerableQuestionId = aq.AnswerableQuestionId,
            Question = aq.Question,
            ResultPlaybook = aq.ResultPlaybook,
            Response = responseObj
        };
    }
}

