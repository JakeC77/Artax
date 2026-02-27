using QuestPDF.Fluent;
using QuestPDF.Helpers;
using QuestPDF.Infrastructure;
using SnapQuote.Core.Models;

namespace SnapQuote.Core.Services;

public interface IPdfGenerator
{
    byte[] Generate(Quote quote, User user);
}

public class PdfGenerator : IPdfGenerator
{
    static PdfGenerator()
    {
        QuestPDF.Settings.License = LicenseType.Community;
    }

    public byte[] Generate(Quote quote, User user)
    {
        var document = Document.Create(container =>
        {
            container.Page(page =>
            {
                page.Size(PageSizes.Letter);
                page.Margin(50);
                page.DefaultTextStyle(x => x.FontSize(11).FontFamily("Arial"));

                page.Header().Element(c => ComposeHeader(c, user, quote));
                page.Content().Element(c => ComposeContent(c, quote));
                page.Footer().Element(ComposeFooter);
            });
        });

        return document.GeneratePdf();
    }

    private void ComposeHeader(IContainer container, User user, Quote quote)
    {
        container.Row(row =>
        {
            row.RelativeItem().Column(col =>
            {
                col.Item().Text(user.BusinessName ?? "Quote")
                    .FontSize(24).Bold().FontColor(Colors.Blue.Darken2);

                if (!string.IsNullOrEmpty(quote.CustomerName))
                {
                    col.Item().PaddingTop(10).Text($"Prepared for: {quote.CustomerName}")
                        .FontSize(12).FontColor(Colors.Grey.Darken1);
                }
            });

            row.ConstantItem(100).Column(col =>
            {
                col.Item().AlignRight().Text("QUOTE").FontSize(28).Bold().FontColor(Colors.Grey.Lighten1);
                col.Item().AlignRight().Text($"#{quote.Id.ToString()[..8].ToUpper()}")
                    .FontSize(10).FontColor(Colors.Grey.Darken1);
                col.Item().AlignRight().Text(quote.CreatedAt.ToString("MMM dd, yyyy"))
                    .FontSize(10).FontColor(Colors.Grey.Darken1);
            });
        });
    }

    private void ComposeContent(IContainer container, Quote quote)
    {
        container.PaddingVertical(30).Column(col =>
        {
            // Line items table
            col.Item().Table(table =>
            {
                table.ColumnsDefinition(columns =>
                {
                    columns.RelativeColumn(3);
                    columns.RelativeColumn(1);
                    columns.RelativeColumn(1);
                    columns.RelativeColumn(1);
                });

                // Header
                table.Header(header =>
                {
                    header.Cell().Background(Colors.Blue.Darken2).Padding(8)
                        .Text("Description").FontColor(Colors.White).Bold();
                    header.Cell().Background(Colors.Blue.Darken2).Padding(8)
                        .AlignRight().Text("Qty").FontColor(Colors.White).Bold();
                    header.Cell().Background(Colors.Blue.Darken2).Padding(8)
                        .AlignRight().Text("Price").FontColor(Colors.White).Bold();
                    header.Cell().Background(Colors.Blue.Darken2).Padding(8)
                        .AlignRight().Text("Amount").FontColor(Colors.White).Bold();
                });

                // Items
                var isAlternate = false;
                foreach (var item in quote.LineItems)
                {
                    var bgColor = isAlternate ? Colors.Grey.Lighten4 : Colors.White;

                    table.Cell().Background(bgColor).Padding(8).Text(item.Description);
                    table.Cell().Background(bgColor).Padding(8).AlignRight()
                        .Text(item.Quantity.ToString("N0"));
                    table.Cell().Background(bgColor).Padding(8).AlignRight()
                        .Text(item.UnitPrice.ToString("C"));
                    table.Cell().Background(bgColor).Padding(8).AlignRight()
                        .Text(item.Amount.ToString("C"));

                    isAlternate = !isAlternate;
                }
            });

            // Totals
            col.Item().PaddingTop(20).AlignRight().Width(200).Column(totals =>
            {
                totals.Item().Row(row =>
                {
                    row.RelativeItem().Text("Subtotal:").Bold();
                    row.ConstantItem(80).AlignRight().Text(quote.Subtotal.ToString("C"));
                });

                if (quote.Tax > 0)
                {
                    totals.Item().Row(row =>
                    {
                        row.RelativeItem().Text("Tax:");
                        row.ConstantItem(80).AlignRight().Text(quote.Tax.ToString("C"));
                    });
                }

                totals.Item().PaddingTop(5).BorderTop(1).BorderColor(Colors.Grey.Darken1).Row(row =>
                {
                    row.RelativeItem().Text("Total:").FontSize(14).Bold();
                    row.ConstantItem(80).AlignRight().Text(quote.Total.ToString("C"))
                        .FontSize(14).Bold().FontColor(Colors.Blue.Darken2);
                });
            });

            // Notes
            if (!string.IsNullOrEmpty(quote.Notes))
            {
                col.Item().PaddingTop(30).Column(notes =>
                {
                    notes.Item().Text("Notes").Bold().FontColor(Colors.Grey.Darken1);
                    notes.Item().PaddingTop(5).Text(quote.Notes).FontColor(Colors.Grey.Darken2);
                });
            }
        });
    }

    private void ComposeFooter(IContainer container)
    {
        container.AlignCenter().Text(text =>
        {
            text.Span("Generated by ").FontColor(Colors.Grey.Darken1);
            text.Span("SnapQuote").Bold().FontColor(Colors.Blue.Darken2);
            text.Span(" • snapquote.com").FontColor(Colors.Grey.Darken1);
        });
    }
}
