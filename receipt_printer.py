# receipt_printer.py
# Generate and print sales receipts (satış makbuzu) for A4 paper

from __future__ import annotations
import tempfile
import webbrowser
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import db


def format_currency(amount: Decimal) -> str:
    """Format amount as Turkish Lira, e.g., 1.000,00"""
    s = f"{amount:,.2f}"
    integer, dec = s.split(".")
    integer = integer.replace(",", ".")
    return f"{integer},{dec}"


def generate_receipt_html(sale_id: int, company_name: str = "ENES TİCARET") -> str:
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
            @page {{ margin: 1cm; }}
            body {{ margin: 0; }}
        }}
        body {{
            font-family: 'Courier New', monospace;
            font-size: 12pt;
            line-height: 1.4;
            max-width: 21cm;
            margin: 0 auto;
            padding: 1cm;
        }}
        .center {{ text-align: center; }}
        .header {{ margin-bottom: 20px; }}
        .title {{
            font-weight: bold;
            margin: 20px 0;
            text-align: center;
        }}
        .separator {{
            border-top: 1px dashed #000;
            margin: 10px 0;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
        }}
        .row {{ margin: 5px 0; }}
        .installment-section {{
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        td {{
            padding: 5px;
        }}
        .right {{ text-align: right; }}
    </style>
</head>
<body>
    <div class="header center">
        <div><strong>{company_name}</strong></div>
        <div>KOZAN CD. PTT EVLERİ</div>
        <div>KAVŞAĞı NO: 689                      ADANA</div>
        <div>Telefon: 3299231 - 3299232</div>
    </div>

    <div class="row">Tarih : {tarih}</div>
    <div class="row">Saat  : {saat}</div>

    <div class="title">
        {"Satış Makbuzu" if is_pesin else "Taksitli Alışveriş - Satış Makbuzu"}
    </div>

    <div class="row">Hesap No: {customer.id}</div>
    <div class="row">Sayın: {customer.name}</div>
    <div class="row">Adres: {customer.address or ""}</div>
"""

        # Sale details
        html += f"""
    <div class="separator"></div>

    <div class="row">{sale.date.strftime("%d/%m/%Y")} Tarihinde {format_currency(sale.total):>15} TL. Alışveriş Yapılıp</div>
    <div class="row">{format_currency(down_payment):>47} TL {"Peşinat Alınmıştır" if not is_pesin else "Ödenmiştir"}</div>
"""

        # If installment sale, show installment details
        if not is_pesin:
            # Separate overdue and upcoming installments
            today = datetime.now().date()
            geciken = [inst for inst in installments if inst.due_date < today and not inst.paid]
            taksitler = [inst for inst in installments if inst.due_date >= today and not inst.paid]

            geciken_total = sum(inst.amount for inst in geciken)
            taksitler_total = sum(inst.amount for inst in taksitler)

            html += f"""
    <div class="separator"></div>

    <div class="installment-section">
        <table>
            <tr>
                <td style="width: 50%;">
                    <strong>Geciken</strong><br>
"""
            for inst in geciken:
                html += f"                    {inst.due_date.strftime('%d/%m/%Y')} - {format_currency(inst.amount)} TL<br>\n"

            html += f"""                </td>
                <td style="width: 50%;">
                    <strong>Taksitler</strong><br>
"""
            for inst in taksitler:
                html += f"                    {inst.due_date.strftime('%d/%m/%Y')} - {format_currency(inst.amount)} TL<br>\n"

            html += f"""                </td>
            </tr>
        </table>
        <div class="separator"></div>
        <table>
            <tr>
                <td style="width: 50%;">Toplam : {format_currency(geciken_total)} TL</td>
                <td style="width: 50%;">Toplam : {format_currency(taksitler_total)} TL</td>
            </tr>
        </table>
        <div class="separator"></div>
        <div class="row">Genel Toplam : {format_currency(geciken_total + taksitler_total)} TL</div>
    </div>
"""

        # Footer
        html += """
    <div class="separator"></div>

    <div class="footer">
        <p>MAĞAZAMIZDAN YAPMIŞ OLDUĞUNUZ ALIŞ VERİŞTEN DOLAYI TEŞEKKÜR EDERİZ</p>
        <p><strong>ENES EFY KARDEŞLER</strong></p>
        <p style="font-size: 10pt; margin-top: 20px;">Pusula Yazılım (322-4570411-4582410 Adana)</p>
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


def print_receipt(sale_id: int, company_name: str = "ENES TİCARET") -> bool:
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
