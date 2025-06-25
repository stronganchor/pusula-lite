# customer_detail.py
# Static "Taksitli Satış Kayıt Bilgisi" tab — load/edit by customer number,
# with lower-half report of installments by month/year.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import calendar
from datetime import date

from sqlalchemy import func

import db
import app_state

import decimal

# Turkish month names, index 1–12
TURKISH_MONTHS = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]


class CustomerDetailFrame(ttk.Frame):
    """Shows header info + sales list for a customer.
    Upper half: list of sales. Lower half: installment report by year/month."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # Header variables
        self.var_id      = tk.StringVar()
        self.var_name    = tk.StringVar()
        self.var_phone   = tk.StringVar()
        self.var_address = tk.StringVar()

        # Report variables
        self.report_year_var = tk.StringVar()

        pad = {"padx": 8, "pady": 4}
        row = 0

        # — Müşteri No entry —
        ttk.Label(self, text="Müşteri No:").grid(row=row, column=0, sticky="e", **pad)
        ent_id = ttk.Entry(self, textvariable=self.var_id, width=10)
        ent_id.grid(row=row, column=1, sticky="w", **pad)
        ent_id.bind("<FocusOut>", self.load_customer)
        row += 1

        # — Header info —
        ttk.Label(self, text="Adı Soyadı:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_name).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="Telefon:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_phone).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="Adres:").grid(row=row, column=0, sticky="ne", **pad)
        lbl_addr = ttk.Label(
            self, textvariable=self.var_address, wraplength=400, justify="left"
        )
        lbl_addr.grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1

        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", **pad
        )
        row += 1

        # — Sales table (upper half) —
        cols = ("sale_id", "tarih", "tutar", "aciklama")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for col, txt, w in zip(
            cols,
            ("ID", "Tarih", "Toplam Tutar", "Açıklama"),
            (60, 100, 120, 300),
        ):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center")

        self.tree.grid(row=row, column=0, columnspan=3, sticky="nsew", **pad)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(row, weight=1)
        row += 1

        # — Separator to report —
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", **pad
        )
        row += 1

        # — Report controls —
        ttk.Label(self, text="Yıl:").grid(row=row, column=0, sticky="e", **pad)
        self.cmb_year = ttk.Combobox(
            self,
            textvariable=self.report_year_var,
            state="readonly",
            width=6
        )
        self.cmb_year.grid(row=row, column=1, sticky="w", **pad)
        self.cmb_year.bind("<<ComboboxSelected>>", lambda e: self.load_report())
        row += 1

        # — Installment report table (lower half) —
        rep_cols = ("month", "amount", "paid")
        self.report_tree = ttk.Treeview(self, columns=rep_cols, show="headings", height=8)
        for col, txt, w in zip(
            rep_cols,
            ("Ay", "Tutar", "Ödendi"),
            (150, 100, 80),
        ):
            self.report_tree.heading(col, text=txt)
            self.report_tree.column(col, width=w, anchor="center")

        self.report_tree.grid(row=row, column=0, columnspan=3, sticky="nsew", **pad)
        self.rowconfigure(row, weight=1)

        # Initial load
        self.load_customer()

    def load_customer(self, event=None) -> None:
        """Load header + sales for a given customer,
        then populate year list and report."""
        raw = self.var_id.get().strip()
        if raw.isdigit():
            cust_id = int(raw)
        else:
            cust_id = app_state.last_customer_id
            if cust_id is None:
                with db.session() as s:
                    rec = s.query(db.Customer.id).order_by(db.Customer.id.desc()).first()
                    cust_id = rec[0] if rec else None

        if cust_id is None:
            return

        with db.session() as s:
            cust = s.get(db.Customer, cust_id)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cust_id} numaralı müşteri yok.")
                return

            name  = cust.name or ""
            phone = cust.phone or ""
            addr  = cust.address or ""
            sales = (
                s.query(
                    db.Sale.id,
                    db.Sale.date,
                    db.Sale.total,
                    db.Sale.description,
                )
                .filter_by(customer_id=cust_id)
                .order_by(db.Sale.date)
                .all()
            )

        self.var_id.set(str(cust_id))
        self.var_name.set(name)
        self.var_phone.set(phone)
        self.var_address.set(addr)
        app_state.last_customer_id = cust_id

        self.tree.delete(*self.tree.get_children())
        for sid, dt_, tot, desc in sales:
            self.tree.insert(
                "",
                "end",
                values=(sid, dt_.strftime("%Y-%m-%d"), f"{tot:.2f}", desc or "")
            )

        self.populate_years(cust_id)
        self.load_report()

    def populate_years(self, cust_id: int) -> None:
        """Fill the year Combobox based on installments for this customer."""
        this_year = date.today().year
        with db.session() as s:
            years = {
                inst.due_date.year
                for sale in s.query(db.Sale).filter_by(customer_id=cust_id).all()
                for inst in sale.installments
            }
        if not years:
            years = {this_year}
        sorted_years = sorted(years)
        self.cmb_year["values"] = sorted_years
        default = this_year if this_year in sorted_years else sorted_years[-1]
        self.report_year_var.set(str(default))

    def load_report(self) -> None:
        """Load a combined monthly installment report for the selected customer and year."""
        cust_id = int(self.var_id.get())
        year = int(self.report_year_var.get())

        # fetch raw due_date, amount, paid for every installment in that year
        with db.session() as s:
            rows = (
                s.query(
                    db.Installment.due_date,
                    db.Installment.amount,
                    db.Installment.paid,
                )
                .join(db.Sale)
                .filter(
                    db.Sale.customer_id == cust_id,
                    func.strftime("%Y", db.Installment.due_date) == str(year)
                )
                .order_by(db.Installment.due_date)
                .all()
            )

        # group by month
        grouped: dict[int, dict[str, decimal.Decimal | bool]] = {}
        for due_date, amount, paid in rows:
            m = due_date.month
            if m not in grouped:
                grouped[m] = {"total": decimal.Decimal("0.00"), "all_paid": True}
            grouped[m]["total"] += amount
            if not paid:
                grouped[m]["all_paid"] = False

        # repopulate the tree
        self.report_tree.delete(*self.report_tree.get_children())
        for m in sorted(grouped):
            total = grouped[m]["total"]
            paid_str = "Evet" if grouped[m]["all_paid"] else "Hayır"
            self.report_tree.insert(
                "",
                "end",
                values=(
                    TURKISH_MONTHS[m],
                    f"{total:.2f}",
                    paid_str
                )
            )
