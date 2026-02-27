"""
PDF Quote Generator for SnapQuote
Creates professional-looking quote PDFs
"""

import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


QUOTES_DIR = os.getenv("QUOTES_DIR", "quotes")


def generate_quote_pdf(
    customer_name: str,
    items: List[Dict],
    total: float,
    notes: Optional[str] = None,
    logo_path: Optional[str] = None,
    contractor_name: Optional[str] = None
) -> str:
    """
    Generate a professional quote PDF
    Returns the quote_id (filename without extension)
    """
    # Ensure quotes directory exists
    os.makedirs(QUOTES_DIR, exist_ok=True)
    
    # Generate unique ID
    quote_id = str(uuid.uuid4())[:8]
    pdf_path = os.path.join(QUOTES_DIR, f"{quote_id}.pdf")
    
    # Create document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'QuoteTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'QuoteSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20
    )
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=20,
        spaceAfter=10
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#334155')
    )
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Normal'],
        fontSize=16,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_RIGHT,
        fontName='Helvetica-Bold'
    )
    
    # Build content
    content = []
    
    # Logo (if provided)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=1.5*inch, height=1.5*inch)
            logo.hAlign = 'LEFT'
            content.append(logo)
            content.append(Spacer(1, 12))
        except:
            pass  # Skip logo if there's an issue
    
    # Title
    content.append(Paragraph("QUOTE", title_style))
    content.append(Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", subtitle_style))
    
    # Customer
    content.append(Paragraph("Prepared For:", header_style))
    content.append(Paragraph(customer_name, body_style))
    content.append(Spacer(1, 20))
    
    # Line Items Table
    content.append(Paragraph("Services & Materials", header_style))
    
    table_data = [['Description', 'Amount']]
    for item in items:
        table_data.append([
            item.get('description', 'Item'),
            f"${item.get('amount', 0):,.2f}"
        ])
    
    # Add total row
    table_data.append(['', ''])  # Spacer row
    table_data.append(['Total', f"${total:,.2f}"])
    
    table = Table(table_data, colWidths=[4.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -3), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -3), 10),
        ('TEXTCOLOR', (0, 1), (-1, -3), colors.HexColor('#334155')),
        ('BOTTOMPADDING', (0, 1), (-1, -3), 10),
        ('TOPPADDING', (0, 1), (-1, -3), 10),
        
        # Total row
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, -1), (-1, -1), 15),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#f97316')),
        
        # Alignment
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        
        # Grid
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 1), (-1, -3), 0.5, colors.HexColor('#f1f5f9')),
    ]))
    content.append(table)
    
    # Notes
    if notes:
        content.append(Spacer(1, 30))
        content.append(Paragraph("Notes", header_style))
        content.append(Paragraph(notes, body_style))
    
    # Footer
    content.append(Spacer(1, 40))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#94a3b8'),
        alignment=TA_CENTER
    )
    content.append(Paragraph("Generated by SnapQuote • snapquote.app", footer_style))
    
    # Build PDF
    doc.build(content)
    
    return quote_id
