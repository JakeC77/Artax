using Microsoft.EntityFrameworkCore;
using SnapQuote.Core.Models;
using SnapQuote.Infrastructure.Data;

namespace SnapQuote.Infrastructure.Repositories;

public interface IQuoteRepository
{
    Task<Quote?> GetByIdAsync(Guid id);
    Task<IEnumerable<Quote>> GetByUserAsync(Guid userId, int limit = 50);
    Task<Quote> CreateAsync(Quote quote);
    Task UpdateStatusAsync(Guid id, QuoteStatus status);
}

public class QuoteRepository : IQuoteRepository
{
    private readonly SnapQuoteDbContext _db;

    public QuoteRepository(SnapQuoteDbContext db)
    {
        _db = db;
    }

    public async Task<Quote?> GetByIdAsync(Guid id)
    {
        var entity = await _db.Quotes
            .Include(q => q.LineItems)
            .Include(q => q.User)
            .FirstOrDefaultAsync(q => q.Id == id);

        return entity == null ? null : MapToModel(entity);
    }

    public async Task<IEnumerable<Quote>> GetByUserAsync(Guid userId, int limit = 50)
    {
        var entities = await _db.Quotes
            .Include(q => q.LineItems)
            .Where(q => q.UserId == userId)
            .OrderByDescending(q => q.CreatedAt)
            .Take(limit)
            .ToListAsync();

        return entities.Select(MapToModel);
    }

    public async Task<Quote> CreateAsync(Quote quote)
    {
        var entity = new QuoteEntity
        {
            Id = quote.Id,
            UserId = quote.UserId != Guid.Empty ? Guid.Parse(quote.UserId) : Guid.NewGuid(),
            RawText = quote.RawText,
            CustomerName = quote.CustomerName,
            Notes = quote.Notes,
            Tax = quote.Tax,
            PdfUrl = quote.PdfUrl,
            ShareableLink = quote.ShareableLink,
            CreatedAt = quote.CreatedAt,
            Status = quote.Status,
            LineItems = quote.LineItems.Select(li => new LineItemEntity
            {
                Id = Guid.NewGuid(),
                Description = li.Description,
                Quantity = li.Quantity,
                UnitPrice = li.UnitPrice
            }).ToList()
        };

        _db.Quotes.Add(entity);
        await _db.SaveChangesAsync();

        return MapToModel(entity);
    }

    public async Task UpdateStatusAsync(Guid id, QuoteStatus status)
    {
        var entity = await _db.Quotes.FindAsync(id)
            ?? throw new InvalidOperationException($"Quote {id} not found");

        entity.Status = status;
        await _db.SaveChangesAsync();
    }

    private static Quote MapToModel(QuoteEntity entity) => new()
    {
        Id = entity.Id,
        UserId = entity.UserId.ToString(),
        PhoneNumber = entity.User?.PhoneNumber ?? string.Empty,
        RawText = entity.RawText,
        CustomerName = entity.CustomerName,
        Notes = entity.Notes,
        Tax = entity.Tax,
        PdfUrl = entity.PdfUrl,
        ShareableLink = entity.ShareableLink,
        CreatedAt = entity.CreatedAt,
        Status = entity.Status,
        LineItems = entity.LineItems.Select(li => new LineItem
        {
            Description = li.Description,
            Quantity = li.Quantity,
            UnitPrice = li.UnitPrice
        }).ToList()
    };
}
