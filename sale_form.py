# sale_form.py
# Record a sale and automatically create an instalment plan.

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import ttk, messagebox

import db
from customer_search import CustomerSearchWindow  # re-use existing search


class SaleWindow(tk.Toplevel):
    """Dialog for recording a new sale with equal instalments."""

    def __init__(self, master: tk.Misc | None = None, customer_id: int | None = None):
        super().__init__(master)
        self.title("Satış Kaydet")
        self.grab_set()
        self.resizable(False, False)

        # ---------------------------------------------------------------- #
        #  State variables                                                 #
        # ---------------------------------------------------------------- #
        self.customer_id: int | None = customer_id
        self.var_cust_name = tk.StringVar(value="(seçilmedi)")
        self.var_date = tk.StringVar(value=dt.date.today().strftime("%Y-%m-%d"))
        self.var_total = tk.StringVar()
        self.var_down = tk.StringVar(value="0")
        self.var_n_inst = tk.StringVar(value="1")

        pad = {"padx": 8, "pady": 4}
        row = 0

        # Customer selector
        ttk.Label(self, text="Müşteri *").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(
            self,
            textvariable=self.var_cust_name,
            state="readonly",
            width=40,
        ).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Müşteri Seç", command=self.choose_customer).grid(
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
        ttk.Label(self, text="Toplam Tutar *").grid(row=row, column=0, sticky="e", **pad)
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

        # Buttons
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=1, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç", command=self.destroy).grid(
            row=row, column=2, sticky="w", **pad
        )

        self.bind("<F10>", lambda *_: self.save())

        # If customer id given, load its name
        if self.customer_id:
            self.load_customer_name()

    # ------------------------------------------------------------------ #
    #  Customer handling                                                 #
    # ------------------------------------------------------------------ #
    def choose_customer(self) -> None:
        """Open search window and retrieve selected customer ID."""
        win = CustomerSearchWindow(self)
        # Temporarily override its on_choose to intercept the selection
        def handle_pick(_ev=None):
            item = win.tree.focus()
            if not item:
                return
            row = win.tree.item(item)["values"]
            if row:
                self.customer_id = int(row[0])
                self.var_cust_name.set(row[1])
                win.destroy()

        win.tree.bind("<Double-1>", handle_pick)
        win.tree.bind("<Return>", handle_pick)

    def load_customer_name(self) -> None:
        """Populate the readonly entry with the customer's name."""
        with db.session() as s:
            cust = s.get(db.Customer, self.customer_id)
            if cust:
                self.var_cust_name.set(cust.name)

    # ------------------------------------------------------------------ #
    #  Save routine                                                      #
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        """Validate fields, write sale + instalments to DB."""
        # Validate customer
        if not self.customer_id:
            messagebox.showwarning("Eksik Bilgi", "Lütfen müşteri seçiniz.")
            return

        # Validate date
        try:
            sale_date = dt.date.fromisoformat(self.var_date.get())
        except ValueError:
            messagebox.showwarning("Hatalı Tarih", "Tarih formatı YYYY-MM-DD olmalıdır.")
            return

        # Validate numbers
        try:
            total = Decimal(self.var_total.get())
            down = Decimal(self.var_down.get())
            n_inst = int(self.var_n_inst.get())
            if total <= 0 or n_inst < 1 or down < 0 or down > total:
                raise ValueError
        except (InvalidOperation, ValueError):
            messagebox.showwarning("Hatalı Giriş", "Tutarlar geçerli sayı olmalıdır.")
            return

        # Compute instalment amount (equal split)
        remaining = total - down
        inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))

        # ---------------------------------------------------------------- #
        #  DB write                                                        #
        # ---------------------------------------------------------------- #
        with db.session() as s:
            sale = db.Sale(
                date=sale_date,
                customer_id=self.customer_id,
                total=total,
            )
            s.add(sale)
            s.flush()  # get sale.id

            # Peşinat isn't stored as Installment (unless you prefer); skip if 0
            for i in range(1, n_inst + 1):
                due = sale_date + dt.timedelta(days=30 * i)
                inst = db.Installment(
                    sale_id=sale.id,
                    due_date=due,
                    amount=inst_amount,
                    paid=0,
                )
                s.add(inst)

        messagebox.showinfo("Başarılı", "Satış ve taksitler kaydedildi.")
        self.destroy()
