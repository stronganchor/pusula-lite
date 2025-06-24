# customer_detail.py
# Detail‐view tab for a single customer (header + sales list)

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import db


class CustomerDetailFrame(ttk.Frame):
    """Shows header info (ID, name, address, phone) + sales table."""

    def __init__(self,
                 master: tk.Misc,
                 *,
                 customer_id: int) -> None:
        super().__init__(master, padding=8)
        self.customer_id = customer_id

        # Build UI
        pad = {"padx": 8, "pady": 4}
        # Header labels
        ttk.Label(self, text="Müşteri No:").grid(row=0, column=0, sticky="e", **pad)
        self.lbl_id = ttk.Label(self, text="")
        self.lbl_id.grid( row=0, column=1, sticky="w", **pad)

        ttk.Label(self, text="Adı Soyadı:").grid(row=0, column=2, sticky="e", **pad)
        self.lbl_name = ttk.Label(self, text="")
        self.lbl_name.grid( row=0, column=3, sticky="w", **pad)

        ttk.Label(self, text="Adres:").grid(row=1, column=0, sticky="ne", **pad)
        self.lbl_address = ttk.Label(self, text="", wraplength=400, justify="left")
        self.lbl_address.grid(    row=1, column=1, columnspan=3, sticky="w", **pad)

        ttk.Label(self, text="Telefon:").grid(row=2, column=0, sticky="e", **pad)
        self.lbl_phone = ttk.Label(self, text="")
        self.lbl_phone.grid( row=2, column=1, columnspan=3, sticky="w", **pad)

        # Separator
        ttk.Separator(self, orient="horizontal")\
            .grid(row=3, column=0, columnspan=4, sticky="ew", **pad)

        # Sales table
        cols = ("sale_id", "tarih", "tutar")
        self.tree = ttk.Treeview(self,
                                 columns=cols,
                                 show="headings",
                                 height=10)
        for col, txt, w in zip(cols,
                               ("ID", "Tarih", "Toplam Tutar"),
                               (60, 100, 120)):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center")

        self.tree.grid(row=4, column=0, columnspan=4, sticky="nsew", **pad)
        # allow expansion
        self.columnconfigure(3, weight=1)
        self.rowconfigure(4, weight=1)

        # Load data
        self._load_data()

    def _load_data(self) -> None:
        with db.session() as s:
            cust = s.get(db.Customer, self.customer_id)
            if not cust:
                messagebox.showerror("Hata", "Müşteri bulunamadı.")
                return

            self.lbl_id.config(     text=str(cust.id))
            self.lbl_name.config(   text=cust.name)
            self.lbl_address.config(text=cust.address or "")
            self.lbl_phone.config(  text=cust.phone   or "")

            # Populate sales
            for sale in (
                s.query(db.Sale.id,
                        db.Sale.date,
                        db.Sale.total)
                 .filter_by(customer_id=cust.id)
                 .order_by(db.Sale.date)
                 .all()
            ):
                sid, dt_, tot = sale
                self.tree.insert(
                    "", "end",
                    values=(sid, dt_.strftime("%Y-%m-%d"), f"{tot:.2f}")
                )
