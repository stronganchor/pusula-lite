# sale_form.py
# Record a sale and automatically create an instalment plan, now embedded

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import ttk, messagebox

import db


class SaleFrame(ttk.Frame):
    """Embedded form for recording a new sale with equal instalments."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # State vars
        self.var_customer = tk.StringVar(value="(seçilmedi)")
        self.var_date     = tk.StringVar(value=dt.date.today().isoformat())
        self.var_total    = tk.StringVar()
        self.var_down     = tk.StringVar(value="0")
        self.var_n_inst   = tk.StringVar(value="1")

        # Map for combobox lookup
        self._cust_map: dict[str, int] = {}

        pad = {"padx": 8, "pady": 4}
        row = 0

        # Customer selector via Combobox
        ttk.Label(self, text="Müşteri *").grid(row=row, column=0, sticky="e", **pad)
        self.cmb_cust = ttk.Combobox(
            self, textvariable=self.var_customer, width=38, state="readonly"
        )
        self.cmb_cust.grid(row=row, column=1, **pad)
        ttk.Button(self, text="Yenile", command=self._load_customers).grid(
            row=row, column=2, **pad
        )
        row += 1

        # Date
        ttk.Label(self, text="Tarih (YYYY-MM-DD)").grid(
            row=row, column=0, sticky="e", **pad
        )
        ttk.Entry(self, textvariable=self.var_date, width=15).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # Amounts
        ttk.Label(self, text="Toplam Tutar *").grid(
            row=row, column=0, sticky="e", **pad
        )
        ttk.Entry(self, textvariable=self.var_total, width=15).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Peşinat").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_down, width=15).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Taksit Sayısı *").grid(
            row=row, column=0, sticky="e", **pad
        )
        ttk.Entry(self, textvariable=self.var_n_inst, width=5).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # Action buttons
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=1, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç", command=self.clear_all).grid(
            row=row, column=2, sticky="w", **pad
        )
        self.bind_all("<F10>", lambda e: self.save())

        # Load initial customer list
        self._load_customers()

    def _load_customers(self) -> None:
        """Populate combobox with names and keep id mapping."""
        with db.session() as s:
            rows = s.query(db.Customer.id, db.Customer.name).order_by(db.Customer.name).all()
        self._cust_map = {r[1]: r[0] for r in rows}
        self.cmb_cust["values"] = [r[1] for r in rows]

    def select_customer(self, cid: int) -> None:
        """Populate combobox and select the given customer."""
        self._load_customers()
        # Find the display name for this ID
        for name, id_ in self._cust_map.items():
            if id_ == cid:
                self.var_customer.set(name)
                break

    def save(self) -> None:
        """Validate fields, write sale + instalments to DB."""
        # Validate customer
        cname = self.var_customer.get()
        cust_id = self._cust_map.get(cname)
        if not cust_id:
            messagebox.showwarning("Eksik Bilgi", "Lütfen müşteri seçiniz.")
            return

        # Validate date
        try:
            sale_date = dt.date.fromisoformat(self.var_date.get())
        except ValueError:
            messagebox.showwarning(
                "Hatalı Tarih", "Tarih formatı YYYY-MM-DD olmalıdır."
            )
            return

        # Validate amounts
        try:
            total = Decimal(self.var_total.get())
            down = Decimal(self.var_down.get())
            n_inst = int(self.var_n_inst.get())
            if total <= 0 or n_inst < 1 or down < 0 or down > total:
                raise ValueError
        except (InvalidOperation, ValueError):
            messagebox.showwarning("Hatalı Giriş", "Tutarlar geçerli sayı olmalıdır.")
            return

        remaining = total - down
        inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))

        with db.session() as s:
            sale = db.Sale(date=sale_date, customer_id=cust_id, total=total)
            s.add(sale)
            s.flush()
            for i in range(1, n_inst + 1):
                due = sale_date + dt.timedelta(days=30 * i)
                s.add(
                    db.Installment(
                        sale_id=sale.id, due_date=due, amount=inst_amount, paid=0
                    )
                )

        messagebox.showinfo("Başarılı", "Satış ve taksitler kaydedildi.")
        self.clear_all()

    def clear_all(self) -> None:
        """Reset all sale fields."""
        for var in (
            self.var_customer,
            self.var_date,
            self.var_total,
            self.var_down,
            self.var_n_inst,
        ):
            var.set("")
        self._load_customers()
