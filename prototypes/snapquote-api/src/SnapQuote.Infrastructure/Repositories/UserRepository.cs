using Microsoft.EntityFrameworkCore;
using SnapQuote.Core.Models;
using SnapQuote.Infrastructure.Data;

namespace SnapQuote.Infrastructure.Repositories;

public interface IUserRepository
{
    Task<User?> GetByPhoneAsync(string phoneNumber);
    Task<User> GetOrCreateAsync(string phoneNumber);
    Task UpdateAsync(User user);
    Task IncrementQuoteCountAsync(Guid userId);
}

public class UserRepository : IUserRepository
{
    private readonly SnapQuoteDbContext _db;

    public UserRepository(SnapQuoteDbContext db)
    {
        _db = db;
    }

    public async Task<User?> GetByPhoneAsync(string phoneNumber)
    {
        var entity = await _db.Users
            .FirstOrDefaultAsync(u => u.PhoneNumber == phoneNumber);

        return entity == null ? null : MapToModel(entity);
    }

    public async Task<User> GetOrCreateAsync(string phoneNumber)
    {
        var entity = await _db.Users
            .FirstOrDefaultAsync(u => u.PhoneNumber == phoneNumber);

        if (entity == null)
        {
            entity = new UserEntity
            {
                Id = Guid.NewGuid(),
                PhoneNumber = phoneNumber,
                CreatedAt = DateTime.UtcNow
            };
            _db.Users.Add(entity);
            await _db.SaveChangesAsync();
        }

        entity.LastActiveAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        return MapToModel(entity);
    }

    public async Task UpdateAsync(User user)
    {
        var entity = await _db.Users.FindAsync(user.Id)
            ?? throw new InvalidOperationException($"User {user.Id} not found");

        entity.BusinessName = user.BusinessName;
        entity.LogoUrl = user.LogoUrl;
        entity.Email = user.Email;
        entity.Tier = user.Tier;
        entity.LastActiveAt = DateTime.UtcNow;

        await _db.SaveChangesAsync();
    }

    public async Task IncrementQuoteCountAsync(Guid userId)
    {
        var entity = await _db.Users.FindAsync(userId)
            ?? throw new InvalidOperationException($"User {userId} not found");

        entity.QuotesThisMonth++;
        await _db.SaveChangesAsync();
    }

    private static User MapToModel(UserEntity entity) => new()
    {
        Id = entity.Id,
        PhoneNumber = entity.PhoneNumber,
        BusinessName = entity.BusinessName,
        LogoUrl = entity.LogoUrl,
        Email = entity.Email,
        Tier = entity.Tier,
        QuotesThisMonth = entity.QuotesThisMonth,
        CreatedAt = entity.CreatedAt,
        LastActiveAt = entity.LastActiveAt
    };
}
