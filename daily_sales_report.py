# daily_sales_report.py
# Daily sales report with date filtering and summary statistics

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
import decimal

from sqlalchemy import func

import db
from date_utils import format_date_tr, parse_date_tr, today_str_tr


def format_currency(amount: decimal.Decimal) -> str:
    """Format a Decimal into Turkish currency, e.g. 1.000.000,00₺."""
    s = f"{amount:,.2f}"
    integer, dec = s.split(".")
    integer = integer.replace(",", ".")
    return f"{integer},{dec}₺"


class DailySalesReportFrame(ttk.Frame):
    """Daily sales report with date range filtering."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # Variables
        self.var_start_date = tk.StringVar(value=today_str_tr())
        self.var_end_date = tk.StringVar(value=today_str_tr())
        self.var_total_sales = tk.StringVar(value="0,00₺")
        self.var_num_sales = tk.StringVar(value="0")

        pad = {"padx": 8, "pady": 4}
        row = 0

        # --- Date Range Selection ---
        filter_frame = ttk.LabelFrame(self, text="Tarih Seçimi", padding=8)
        filter_frame.grid(row=row, column=0, columnspan=4, sticky="ew", **pad)

        ttk.Label(filter_frame, text="Başlangıç:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(filter_frame, textvariable=self.var_start_date, width=12).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(filter_frame, text="Bitiş:").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        ttk.Entry(filter_frame, textvariable=self.var_end_date, width=12).grid(
            row=0, column=3, sticky="w", padx=4, pady=2
        )

        ttk.Button(filter_frame, text="Raporla", command=self.load_report).grid(
            row=0, column=4, padx=8, pady=2
        )

        # Quick date buttons
        ttk.Button(filter_frame, text="Bugün", command=self.set_today).grid(
            row=0, column=5, padx=2, pady=2
        )
        ttk.Button(filter_frame, text="Bu Hafta", command=self.set_this_week).grid(
            row=0, column=6, padx=2, pady=2
        )
        ttk.Button(filter_frame, text="Bu Ay", command=self.set_this_month).grid(
            row=0, column=7, padx=2, pady=2
        )

        row += 1

        # --- Summary Statistics ---
        summary_frame = ttk.LabelFrame(self, text="Özet", padding=8)
        summary_frame.grid(row=row, column=0, columnspan=4, sticky="ew", **pad)

        ttk.Label(summary_frame, text="Toplam Satış Tutarı:").grid(
            row=0, column=0, sticky="e", padx=4, pady=2
        )
        ttk.Label(summary_frame, textvariable=self.var_total_sales, font="TkHeadingFont").grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(summary_frame, text="Satış Sayısı:").grid(
            row=0, column=2, sticky="e", padx=12, pady=2
        )
        ttk.Label(summary_frame, textvariable=self.var_num_sales, font="TkHeadingFont").grid(
            row=0, column=3, sticky="w", padx=4, pady=2
        )

        row += 1

        # --- Sales Table ---
        cols = ("sale_id", "customer_name", "date", "total", "description")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        headings = ("No", "Müşteri", "Tarih", "Tutar", "Açıklama")
        widths = (60, 180, 100, 120, 280)

        for col, txt, w in zip(cols, headings, widths):
            anchor = "center" if col in ("sale_id", "date", "total") else "w"
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=anchor)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=row, column=0, columnspan=4, sticky="nsew", **pad)
        sb.grid(row=row, column=4, sticky="ns")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(row, weight=1)

        # Load initial report
        self.load_report()

    def set_today(self) -> None:
        """Set date range to today."""
        today = today_str_tr()
        self.var_start_date.set(today)
        self.var_end_date.set(today)
        self.load_report()

    def set_this_week(self) -> None:
        """Set date range to current week (Monday to Sunday)."""
        today = date.today()
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        self.var_start_date.set(format_date_tr(start))
        self.var_end_date.set(format_date_tr(end))
        self.load_report()

    def set_this_month(self) -> None:
        """Set date range to current month."""
        today = date.today()
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(day=31)
        else:
            end = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        self.var_start_date.set(format_date_tr(start))
        self.var_end_date.set(format_date_tr(end))
        self.load_report()

    def load_report(self) -> None:
        """Load sales for the selected date range."""
        try:
            start = parse_date_tr(self.var_start_date.get())
            end = parse_date_tr(self.var_end_date.get())
        except ValueError:
            self.var_total_sales.set("0,00₺")
            self.var_num_sales.set("0")
            self.tree.delete(*self.tree.get_children())
            return

        with db.session() as s:
            sales = (
                s.query(
                    db.Sale.id,
                    db.Customer.name,
                    db.Sale.date,
                    db.Sale.total,
                    db.Sale.description
                )
                .join(db.Customer)
                .filter(db.Sale.date >= start, db.Sale.date <= end)
                .order_by(db.Sale.date.desc(), db.Sale.id.desc())
                .all()
            )

        # Update summary
        total_amount = sum(s.total for s in sales)
        self.var_total_sales.set(format_currency(total_amount))
        self.var_num_sales.set(str(len(sales)))

        # Populate tree
        self.tree.delete(*self.tree.get_children())
        for sale_id, cust_name, sale_date, total, desc in sales:
            self.tree.insert(
                "",
                "end",
                values=(
                    sale_id,
                    cust_name,
                    format_date_tr(sale_date),
                    format_currency(total),
                    desc or ""
                ),
            )
