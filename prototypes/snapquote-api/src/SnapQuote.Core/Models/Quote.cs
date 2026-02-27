namespace SnapQuote.Core.Models;

public class Quote
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string UserId { get; set; } = string.Empty;
    public string PhoneNumber { get; set; } = string.Empty;
    public string RawText { get; set; } = string.Empty;
    public List<LineItem> LineItems { get; set; } = new();
    public decimal Subtotal => LineItems.Sum(x => x.Amount);
    public decimal Tax { get; set; }
    public decimal Total => Subtotal + Tax;
    public string? CustomerName { get; set; }
    public string? Notes { get; set; }
    public string? PdfUrl { get; set; }
    public string? ShareableLink { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public QuoteStatus Status { get; set; } = QuoteStatus.Draft;
}

public class LineItem
{
    public string Description { get; set; } = string.Empty;
    public decimal Quantity { get; set; } = 1;
    public decimal UnitPrice { get; set; }
    public decimal Amount => Quantity * UnitPrice;
}

public enum QuoteStatus
{
    Draft,
    Sent,
    Viewed,
    Accepted,
    Declined
}
