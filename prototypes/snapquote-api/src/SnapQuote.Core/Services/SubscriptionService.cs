using SnapQuote.Core.Models;

namespace SnapQuote.Core.Services;

public interface ISubscriptionService
{
    bool CanCreateQuote(User user);
    int GetRemainingQuotes(User user);
    Task<bool> UpgradeToProAsync(User user, string paymentMethodId);
}

public class SubscriptionService : ISubscriptionService
{
    private const int FreeQuotesPerMonth = 5;

    public bool CanCreateQuote(User user)
    {
        return user.Tier switch
        {
            UserTier.Free => user.QuotesThisMonth < FreeQuotesPerMonth,
            UserTier.Pro => true,
            UserTier.Enterprise => true,
            _ => false
        };
    }

    public int GetRemainingQuotes(User user)
    {
        return user.Tier switch
        {
            UserTier.Free => Math.Max(0, FreeQuotesPerMonth - user.QuotesThisMonth),
            UserTier.Pro => int.MaxValue,
            UserTier.Enterprise => int.MaxValue,
            _ => 0
        };
    }

    public async Task<bool> UpgradeToProAsync(User user, string paymentMethodId)
    {
        // TODO: Integrate with Stripe or other payment processor
        // For now, just mark as upgraded
        user.Tier = UserTier.Pro;
        await Task.CompletedTask;
        return true;
    }
}
