# sale_form.py
# Record a sale and automatically create an instalment plan,
# now with editable Müşteri No and non-editable name label.

from __future__ import annotations
import datetime as dt
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import ttk, messagebox

import db
import app_state


class SaleFrame(ttk.Frame):
    """Embedded form for recording a new sale with equal instalments."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # State variables
        self.var_customer_id   = tk.StringVar()
        self.var_customer_name = tk.StringVar(value="(seçilmedi)")
        self.var_date          = tk.StringVar(value=dt.date.today().isoformat())
        self.var_total         = tk.StringVar()
        self.var_down          = tk.StringVar(value="0")
        self.var_n_inst        = tk.StringVar(value="1")

        pad = {"padx": 8, "pady": 4}
        row = 0

        # --- Customer selector via ID entry + name label ---
        ttk.Label(self, text="Müşteri No *").grid(
            row=row, column=0, sticky="e", **pad
        )
        ent_id = ttk.Entry(self, textvariable=self.var_customer_id, width=10)
        ent_id.grid(row=row, column=1, sticky="w", **pad)
        ent_id.bind("<FocusOut>", lambda e: self.load_customer())

        ttk.Label(self, text="Adı Soyadı:").grid(
            row=row, column=2, sticky="e", **pad
        )
        ttk.Label(self, textvariable=self.var_customer_name).grid(
            row=row, column=3, sticky="w", **pad
        )
        row += 1

        # --- Date ---
        ttk.Label(self, text="Tarih (YYYY-MM-DD)").grid(
            row=row, column=0, sticky="e", **pad
        )
        ttk.Entry(self, textvariable=self.var_date, width=15).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # --- Amounts ---
        ttk.Label(self, text="Toplam Tutar *").grid(
            row=row, column=0, sticky="e", **pad
        )
        ttk.Entry(self, textvariable=self.var_total, width=15).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Peşinat").grid(
            row=row, column=0, sticky="e", **pad
        )
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

        # --- Action buttons ---
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=1, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç", command=self.clear_all).grid(
            row=row, column=2, sticky="w", **pad
        )
        self.bind_all("<F10>", lambda e: self.save())

        # On init, auto-load the last-selected or most recent customer
        self.load_customer()


    def load_customer(self, cid: int | None = None) -> None:
        """Load the customer by ID (or last-selected / newest if None)."""
        # Determine which ID to load
        if cid is None:
            cid = app_state.last_customer_id
        if cid is None:
            with db.session() as s:
                rec = s.query(db.Customer.id).order_by(db.Customer.id.desc()).first()
                cid = rec[0] if rec else None
        if cid is None:
            return

        # Fetch and display
        self.var_customer_id.set(str(cid))
        with db.session() as s:
            cust = s.get(db.Customer, cid)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
                self.var_customer_name.set("(seçilmedi)")
                return
            self.var_customer_name.set(cust.name)


    def save(self) -> None:
        """Validate fields, persist sale + instalments, and update last-customer."""
        # Validate customer ID
        raw = self.var_customer_id.get().strip()
        if not raw.isdigit():
            messagebox.showwarning("Eksik Bilgi", "Geçerli müşteri numarası giriniz.")
            return
        cust_id = int(raw)

        with db.session() as s:
            cust = s.get(db.Customer, cust_id)
        if not cust:
            messagebox.showwarning("Bulunamadı", f"{cust_id} numaralı müşteri yok.")
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

        # Compute instalment amount
        remaining = total - down
        inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))

        # Persist sale + installments
        with db.session() as s:
            sale = db.Sale(date=sale_date, customer_id=cust_id, total=total)
            s.add(sale)
            s.flush()
            for i in range(1, n_inst + 1):
                due = sale_date + dt.timedelta(days=30 * i)
                s.add(
                    db.Installment(
                        sale_id=sale.id,
                        due_date=due,
                        amount=inst_amount,
                        paid=0,
                    )
                )

        # Success: update global state & clear inputs
        messagebox.showinfo("Başarılı", "Satış ve taksitler kaydedildi.")
        app_state.last_customer_id = cust_id
        self.load_customer(cust_id)
        self.clear_all()


    def clear_all(self) -> None:
        """Reset only the sale-specific fields (keep customer loaded)."""
        self.var_date.set(dt.date.today().isoformat())
        self.var_total.set("")
        self.var_down.set("0")
        self.var_n_inst.set("1")
