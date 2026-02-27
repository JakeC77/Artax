using Microsoft.EntityFrameworkCore;
using SnapQuote.Core.Models;

namespace SnapQuote.Infrastructure.Data;

public class SnapQuoteDbContext : DbContext
{
    public SnapQuoteDbContext(DbContextOptions<SnapQuoteDbContext> options) : base(options) { }

    public DbSet<UserEntity> Users => Set<UserEntity>();
    public DbSet<QuoteEntity> Quotes => Set<QuoteEntity>();
    public DbSet<LineItemEntity> LineItems => Set<LineItemEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<UserEntity>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.PhoneNumber).IsUnique();
            entity.Property(e => e.PhoneNumber).HasMaxLength(20).IsRequired();
            entity.Property(e => e.BusinessName).HasMaxLength(200);
            entity.Property(e => e.Email).HasMaxLength(200);
        });

        modelBuilder.Entity<QuoteEntity>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.UserId);
            entity.Property(e => e.RawText).HasMaxLength(4000);
            entity.Property(e => e.CustomerName).HasMaxLength(200);
            entity.Property(e => e.Notes).HasMaxLength(2000);
            entity.Property(e => e.PdfUrl).HasMaxLength(500);
            
            entity.HasOne(e => e.User)
                .WithMany(u => u.Quotes)
                .HasForeignKey(e => e.UserId);
        });

        modelBuilder.Entity<LineItemEntity>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Description).HasMaxLength(500).IsRequired();
            entity.Property(e => e.Quantity).HasPrecision(10, 2);
            entity.Property(e => e.UnitPrice).HasPrecision(10, 2);
            
            entity.HasOne(e => e.Quote)
                .WithMany(q => q.LineItems)
                .HasForeignKey(e => e.QuoteId);
        });
    }
}

// Entity classes with EF Core navigation properties
public class UserEntity
{
    public Guid Id { get; set; }
    public string PhoneNumber { get; set; } = string.Empty;
    public string? BusinessName { get; set; }
    public string? LogoUrl { get; set; }
    public string? Email { get; set; }
    public UserTier Tier { get; set; } = UserTier.Free;
    public int QuotesThisMonth { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? LastActiveAt { get; set; }
    
    // Navigation
    public ICollection<QuoteEntity> Quotes { get; set; } = new List<QuoteEntity>();
}

public class QuoteEntity
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public string RawText { get; set; } = string.Empty;
    public string? CustomerName { get; set; }
    public string? Notes { get; set; }
    public decimal Tax { get; set; }
    public string? PdfUrl { get; set; }
    public string? ShareableLink { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public QuoteStatus Status { get; set; } = QuoteStatus.Draft;
    
    // Navigation
    public UserEntity User { get; set; } = null!;
    public ICollection<LineItemEntity> LineItems { get; set; } = new List<LineItemEntity>();
}

public class LineItemEntity
{
    public Guid Id { get; set; }
    public Guid QuoteId { get; set; }
    public string Description { get; set; } = string.Empty;
    public decimal Quantity { get; set; } = 1;
    public decimal UnitPrice { get; set; }
    
    // Navigation
    public QuoteEntity Quote { get; set; } = null!;
}
