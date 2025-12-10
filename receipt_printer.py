# receipt_printer.py
# Generate and print sales receipts (satış makbuzu) for A4 paper

from __future__ import annotations
import tempfile
import webbrowser
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import db
from sqlalchemy import func

TURKISH_MONTHS = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]


def format_currency(amount: Decimal) -> str:
    """Format amount as Turkish Lira, e.g., 1.000,00"""
    s = f"{amount:,.2f}"
    integer, dec = s.split(".")
    integer = integer.replace(",", ".")
    return f"{integer},{dec}"


def generate_receipt_html(sale_id: int, company_name: str = "ENES BEKO") -> str:
    """Generate HTML for a sales receipt."""

    with db.session() as s:
        sale = s.get(db.Sale, sale_id)
        if not sale:
            raise ValueError(f"Sale {sale_id} not found")

        customer = sale.customer
        installments = sorted(sale.installments, key=lambda x: x.due_date)

        # Calculate down payment
        total_installments = sum(inst.amount for inst in installments)
        down_payment = sale.total - total_installments

        # Determine if this is a peşin (cash) sale
        is_pesin = len(installments) <= 1 and down_payment >= sale.total

        # Get current date/time for receipt
        now = datetime.now()
        tarih = now.strftime("%d/%m/%Y")
        saat = now.strftime("%H:%M")

        # Build HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Satış Makbuzu - {customer.name}</title>
    <style>
        @media print {{
            @page {{
                margin: 0;
                size: A4;
            }}
            body {{ margin: 0; }}
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            max-width: 21cm;
            margin: 0 auto;
            padding: 1.5cm 1.5cm;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 12px;
        }}
        .company-name {{
            font-size: 18pt;
            font-weight: bold;
            color: #1a1a1a;
            margin-bottom: 6px;
        }}
        .company-info {{
            font-size: 9pt;
            color: #444;
            line-height: 1.3;
        }}
        .title {{
            font-size: 13pt;
            font-weight: bold;
            margin: 18px 0 15px 0;
            text-align: center;
            color: #1a1a1a;
        }}
        .info-section {{
            margin: 15px 0;
            background: #f9f9f9;
            padding: 12px;
            border-radius: 4px;
        }}
        .info-row {{
            margin: 5px 0;
            display: flex;
        }}
        .info-label {{
            font-weight: 600;
            color: #333;
            min-width: 90px;
        }}
        .info-value {{
            color: #555;
        }}
        .sale-details {{
            margin: 15px 0;
            padding: 12px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .sale-row {{
            margin: 8px 0;
            font-size: 10pt;
        }}
        .amount {{
            font-weight: 600;
            color: #2c5282;
        }}
        .installment-section {{
            margin: 15px 0;
        }}
        .installment-header {{
            font-weight: 600;
            font-size: 10pt;
            margin-bottom: 6px;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 4px;
        }}
        .installment-columns {{
            display: flex;
            gap: 15px;
        }}
        .installment-col {{
            flex: 1;
        }}
        .installment-item {{
            padding: 4px 8px;
            margin: 3px 0;
            background: #f5f5f5;
            border-radius: 3px;
            font-size: 9pt;
        }}
        .totals-section {{
            margin: 15px 0;
            padding: 12px;
            background: #f0f4f8;
            border-radius: 4px;
        }}
        .total-row {{
            display: flex;
            justify-content: space-between;
            margin: 6px 0;
            font-size: 10pt;
        }}
        .grand-total {{
            font-weight: bold;
            font-size: 11pt;
            color: #1a1a1a;
            border-top: 2px solid #333;
            padding-top: 8px;
            margin-top: 8px;
        }}
        .footer {{
            margin-top: 25px;
            text-align: center;
            border-top: 2px solid #333;
            padding-top: 15px;
        }}
        .thank-you {{
            font-size: 10pt;
            color: #333;
            margin-bottom: 8px;
        }}
        .company-footer {{
            font-weight: bold;
            font-size: 11pt;
            color: #1a1a1a;
        }}
        .legal-name {{
            font-size: 9pt;
            color: #666;
            margin-top: 8px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="company-name">{company_name}</div>
        <div class="company-info">
            KOZAN CD. PTT EVLERİ KAVŞAĞI NO: 689, ADANA<br>
            Telefon: (0322) 329 92 32 | Web: https://enesbeko.com
        </div>
    </div>

    <div class="title">
        {"Satış Makbuzu" if is_pesin else "Taksitli Alışveriş - Satış Makbuzu"}
    </div>

    <div style="display: flex; justify-content: space-between; margin-bottom: 15px; font-size: 9pt;">
        <div><strong>Tarih:</strong> {tarih}</div>
        <div><strong>Saat:</strong> {saat}</div>
    </div>

    <div class="info-section">
        <div class="info-row">
            <span class="info-label">Hesap No:</span>
            <span class="info-value">{customer.id}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Sayın:</span>
            <span class="info-value">{customer.name}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Adres:</span>
            <span class="info-value">{customer.address or ""}</span>
        </div>
    </div>

    <div class="sale-details">
        <div class="sale-row">
            <strong>{sale.date.strftime("%d/%m/%Y")}</strong> Tarihinde
            <span class="amount">{format_currency(sale.total)} TL</span> Alışveriş Yapılıp
        </div>
        <div class="sale-row">
            <span class="amount">{format_currency(down_payment)} TL</span>
            {"Ödenmiştir" if is_pesin else "Peşinat Alınmıştır"}
        </div>
    </div>
"""

        # If installment sale, show installment details
        if not is_pesin:
            # Separate overdue and upcoming installments
            today = datetime.now().date()
            geciken = [inst for inst in installments if inst.due_date < today and not inst.paid]
            taksitler = [inst for inst in installments if inst.due_date >= today and not inst.paid]

            geciken_total = sum(inst.amount for inst in geciken)
            taksitler_total = sum(inst.amount for inst in taksitler)

            html += """
    <div class="installment-section">
        <div class="installment-columns">
            <div class="installment-col">
                <div class="installment-header">Geciken Taksitler</div>
"""
            if geciken:
                for inst in geciken:
                    html += f'                <div class="installment-item">{inst.due_date.strftime("%d/%m/%Y")} - {format_currency(inst.amount)} TL</div>\n'
            else:
                html += '                <div class="installment-item">Yok</div>\n'

            html += """            </div>
            <div class="installment-col">
                <div class="installment-header">Yaklaşan Taksitler</div>
"""
            if taksitler:
                for inst in taksitler:
                    html += f'                <div class="installment-item">{inst.due_date.strftime("%d/%m/%Y")} - {format_currency(inst.amount)} TL</div>\n'
            else:
                html += '                <div class="installment-item">Yok</div>\n'

            html += f"""            </div>
        </div>
    </div>

    <div class="totals-section">
        <div class="total-row">
            <span>Geciken Toplam:</span>
            <span class="amount">{format_currency(geciken_total)} TL</span>
        </div>
        <div class="total-row">
            <span>Taksitler Toplam:</span>
            <span class="amount">{format_currency(taksitler_total)} TL</span>
        </div>
        <div class="total-row grand-total">
            <span>Genel Toplam:</span>
            <span class="amount">{format_currency(geciken_total + taksitler_total)} TL</span>
        </div>
    </div>
"""

        # Footer
        html += """
    <div class="footer">
        <div class="thank-you">Mağazamızdan yapmış olduğunuz alış verişten dolayı teşekkür ederiz</div>
        <div class="company-footer">ENES BEKO</div>
        <div class="legal-name">ENES EFY KARDEŞLER</div>
    </div>

    <script>
        window.onload = function() {
            window.print();
        }
    </script>
</body>
</html>
"""

    return html


def print_receipt(sale_id: int, company_name: str = "ENES BEKO") -> bool:
    """Generate receipt HTML and open in browser for printing."""
    try:
        html = generate_receipt_html(sale_id, company_name)

        # Create temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html',
                                        delete=False, encoding='utf-8') as f:
            f.write(html)
            temp_path = f.name

        # Open in default browser
        webbrowser.open('file://' + temp_path)
        return True

    except Exception as e:
        print(f"Error printing receipt: {e}")
        return False


def generate_payment_receipt_html(
    customer_id: int,
    year: int,
    month: int,
    company_name: str = "ENES BEKO",
) -> str:
    """Generate HTML for an installment payment receipt."""
    month_name = TURKISH_MONTHS[month] if 0 <= month < len(TURKISH_MONTHS) else str(month)

    with db.session() as s:
        customer_row = (
            s.query(db.Customer.id, db.Customer.name, db.Customer.address)
             .filter_by(id=customer_id)
             .first()
        )
        if not customer_row:
            raise ValueError(f"Müşteri {customer_id} bulunamadı")

        rows = [
            (due_date, amount, sale_id)
            for due_date, amount, sale_id in (
                s.query(
                    db.Installment.due_date,
                    db.Installment.amount,
                    db.Sale.id,
                )
                .join(db.Sale)
                .filter(
                    db.Sale.customer_id == customer_id,
                    func.strftime("%Y", db.Installment.due_date) == str(year),
                    func.strftime("%m", db.Installment.due_date) == f"{month:02d}",
                    db.Installment.paid == 1,
                )
                .order_by(db.Installment.due_date)
                .all()
            )
        ]

    if not rows:
        raise ValueError("Bu ay için ödenmiş taksit bulunamadı.")

    customer_id, customer_name, customer_address = customer_row
    total_paid = sum(amount for _, amount, _ in rows)
    now = datetime.now()
    tarih = now.strftime("%d/%m/%Y")
    saat = now.strftime("%H:%M")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Ödeme Makbuzu - {customer_name}</title>
    <style>
        @media print {{
            @page {{
                margin: 0;
                size: A4;
            }}
            body {{ margin: 0; }}
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            max-width: 21cm;
            margin: 0 auto;
            padding: 1.5cm 1.5cm;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 12px;
        }}
        .company-name {{
            font-size: 18pt;
            font-weight: bold;
            color: #1a1a1a;
            margin-bottom: 6px;
        }}
        .company-info {{
            font-size: 9pt;
            color: #444;
            line-height: 1.3;
        }}
        .title {{
            font-size: 13pt;
            font-weight: bold;
            margin: 18px 0 12px 0;
            text-align: center;
            color: #1a1a1a;
        }}
        .info-row {{
            margin: 4px 0;
        }}
        .label {{
            font-weight: 600;
            color: #333;
            min-width: 110px;
            display: inline-block;
        }}
        .table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}
        .table th, .table td {{
            border: 1px solid #ccc;
            padding: 6px 8px;
            font-size: 9pt;
            text-align: left;
        }}
        .table th {{
            background: #f2f4f7;
            font-weight: 600;
        }}
        .total {{
            margin-top: 12px;
            text-align: right;
            font-weight: bold;
            font-size: 11pt;
        }}
        .footer {{
            margin-top: 25px;
            text-align: center;
            border-top: 2px solid #333;
            padding-top: 15px;
        }}
        .thank-you {{
            font-size: 10pt;
            color: #333;
            margin-bottom: 8px;
        }}
        .company-footer {{
            font-weight: bold;
            font-size: 11pt;
            color: #1a1a1a;
        }}
        .legal-name {{
            font-size: 9pt;
            color: #666;
            margin-top: 8px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="company-name">{company_name}</div>
        <div class="company-info">
            KOZAN CD. PTT EVLERİ KAVŞAĞI NO: 689, ADANA<br>
            Telefon: (0322) 329 92 32 | Web: https://enesbeko.com
        </div>
    </div>

    <div class="title">{month_name} {year} Taksit Ödemesi</div>

    <div class="info-row"><span class="label">Tarih:</span> {tarih}</div>
    <div class="info-row"><span class="label">Saat:</span> {saat}</div>
    <div class="info-row"><span class="label">Hesap No:</span> {customer_id}</div>
    <div class="info-row"><span class="label">Müşteri:</span> {customer_name}</div>
    <div class="info-row"><span class="label">Adres:</span> {customer_address or ""}</div>

    <table class="table">
        <thead>
            <tr>
                <th>Taksit Tarihi</th>
                <th>Tutar</th>
                <th>Satış No</th>
            </tr>
        </thead>
        <tbody>"""

    for due_date, amount, sale_id in rows:
        html += f"""
            <tr>
                <td>{due_date.strftime("%d/%m/%Y")}</td>
                <td>{format_currency(amount)} TL</td>
                <td>{sale_id}</td>
            </tr>"""

    html += f"""
        </tbody>
    </table>

    <div class="total">Toplam Ödenen: {format_currency(total_paid)} TL</div>

    <div class="footer">
        <div class="thank-you">Mağazamızdan yapmış olduğunuz ödeme için teşekkür ederiz</div>
        <div class="company-footer">{company_name}</div>
        <div class="legal-name">ENES EFY KARDEŞLER</div>
    </div>

    <script>
        window.onload = function() {{
            window.print();
        }}
    </script>
</body>
</html>"""
    return html


def print_payment_receipt(customer_id: int, year: int, month: int, company_name: str = "ENES BEKO") -> bool:
    """Generate payment receipt HTML and open in browser for printing."""
    try:
        html = generate_payment_receipt_html(customer_id, year, month, company_name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            temp_path = f.name
        webbrowser.open("file://" + temp_path)
        return True
    except Exception as e:
        print(f"Error printing payment receipt: {e}")
        return False
