# customer_detail.py
# Static “Taksitli Satış Kayıt Bilgisi” tab — load/edit by customer number

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import db
import app_state


class CustomerDetailFrame(ttk.Frame):
    """Shows header info + sales list for a customer.
    Change the Müşteri No at the top to switch records in-place."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        self.var_id      = tk.StringVar()
        self.var_name    = tk.StringVar()
        self.var_phone   = tk.StringVar()
        self.var_address = tk.StringVar()

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

        # — Sales table —
        cols = ("sale_id", "tarih", "tutar")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for col, txt, w in zip(cols, ("ID", "Tarih", "Toplam Tutar"), (60, 100, 120)):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center")

        self.tree.grid(row=row, column=0, columnspan=3, sticky="nsew", **pad)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(row, weight=1)

        # On init, load last‐selected or newest
        self.load_customer()

    def load_customer(self, event=None) -> None:
        """Load data for typed or last‐selected customer."""
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

        # Fetch inside session, copy before commit
        with db.session() as s:
            cust = s.get(db.Customer, cust_id)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cust_id} numaralı müşteri yok.")
                return
            name = cust.name or ""
            phone = cust.phone or ""
            addr = cust.address or ""
            # Query sales
            sales = (
                s.query(db.Sale.id, db.Sale.date, db.Sale.total)
                 .filter_by(customer_id=cust.id)
                 .order_by(db.Sale.date)
                 .all()
            )

        # Update header + global state
        self.var_id.set(str(cust_id))
        self.var_name.set(name)
        self.var_phone.set(phone)
        self.var_address.set(addr)
        app_state.last_customer_id = cust_id

        # Populate sales table
        self.tree.delete(*self.tree.get_children())
        for sid, dt_, tot in sales:
            self.tree.insert(
                "", "end", values=(sid, dt_.strftime("%Y-%m-%d"), f"{tot:.2f}")
            )
