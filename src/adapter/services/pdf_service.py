"""ReportLab PDF Generation Service Implementation

Implements PDF generation using ReportLab library.
"""

from io import BytesIO
from typing import List
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

from src.app.services.pdf_service import PdfService
from src.domain.invoice import Invoice
from src.domain.invoice_line import InvoiceLine


class ReportLabPdfService(PdfService):
    """
    ReportLab implementation of PdfService

    Generates professional PDF invoices using ReportLab.
    """

    def generate_proforma_invoice(
        self,
        invoice: Invoice,
        invoice_lines: List[InvoiceLine],
        company_name: str = "Super Agent Platform",
        company_address: str = "123 AI Street, Tech City, TC 12345",
    ) -> bytes:
        """
        Generate a proforma invoice PDF

        Args:
            invoice: Invoice entity with billing details
            invoice_lines: List of line items for the invoice
            company_name: Company name to display on invoice
            company_address: Company address to display on invoice

        Returns:
            PDF document as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=10,
            textColor=colors.HexColor("#2C3E50"),
        )
        proforma_style = ParagraphStyle(
            "ProformaStyle",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#E74C3C"),
            spaceAfter=20,
        )
        header_style = ParagraphStyle(
            "HeaderStyle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#7F8C8D"),
        )
        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontSize=10,
        )
        bold_style = ParagraphStyle(
            "BoldStyle",
            parent=styles["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
        )

        # Header - Company Info and PROFORMA label
        elements.append(Paragraph(company_name, title_style))
        elements.append(Paragraph(company_address, header_style))
        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph("PROFORMA INVOICE", proforma_style))

        # Invoice Details Table
        invoice_info = [
            ["Invoice Number:", invoice.invoice_number],
            ["Status:", invoice.status.value.upper()],
            ["Currency:", invoice.currency],
            [
                "Billing Period:",
                f"{invoice.billing_period_start.strftime('%Y-%m-%d')} to "
                f"{invoice.billing_period_end.strftime('%Y-%m-%d')}",
            ],
            ["Created:", invoice.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
        ]

        if invoice.issued_at:
            invoice_info.append(
                ["Issued:", invoice.issued_at.strftime("%Y-%m-%d %H:%M:%S UTC")]
            )

        invoice_table = Table(invoice_info, colWidths=[40 * mm, 100 * mm])
        invoice_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#7F8C8D")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        elements.append(invoice_table)
        elements.append(Spacer(1, 10 * mm))

        # Tenant Info
        elements.append(Paragraph("Bill To:", bold_style))
        elements.append(Paragraph(f"Tenant ID: {invoice.tenant_id}", normal_style))
        elements.append(Spacer(1, 10 * mm))

        # Line Items Table
        if invoice_lines:
            line_data = [["Description", "Quantity", "Unit Price", "Total"]]
            for line in invoice_lines:
                line_data.append(
                    [
                        line.description,
                        f"{line.quantity:,.6f}".rstrip("0").rstrip("."),
                        f"{invoice.currency} {line.unit_price:,.2f}",
                        f"{invoice.currency} {line.total_price:,.2f}",
                    ]
                )
        else:
            # If no line items, show a single line with total
            line_data = [
                ["Description", "Quantity", "Unit Price", "Total"],
                [
                    "Monthly subscription charges",
                    "1",
                    f"{invoice.currency} {invoice.total_amount:,.2f}",
                    f"{invoice.currency} {invoice.total_amount:,.2f}",
                ],
            ]

        line_table = Table(
            line_data, colWidths=[80 * mm, 25 * mm, 30 * mm, 35 * mm]
        )
        line_table.setStyle(
            TableStyle(
                [
                    # Header row
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    # Data rows
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    # Alternate row colors
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8F9F9")],
                    ),
                ]
            )
        )

        elements.append(line_table)
        elements.append(Spacer(1, 5 * mm))

        # Total
        total_data = [
            ["", "", "Total:", f"{invoice.currency} {invoice.total_amount:,.2f}"]
        ]
        total_table = Table(total_data, colWidths=[80 * mm, 25 * mm, 30 * mm, 35 * mm])
        total_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (2, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                    ("LINEABOVE", (2, 0), (-1, 0), 1.5, colors.HexColor("#2C3E50")),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        elements.append(total_table)
        elements.append(Spacer(1, 15 * mm))

        # Footer note
        footer_note = Paragraph(
            "<i>This is a proforma invoice for preview purposes only. "
            "It is not a legally binding document until officially issued.</i>",
            ParagraphStyle(
                "FooterNote",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#95A5A6"),
            ),
        )
        elements.append(footer_note)

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes
