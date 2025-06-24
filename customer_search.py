# customer_search.py
# Converted CustomerSearchWindow → CustomerSearchFrame

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import db


class CustomerSearchFrame(ttk.Frame):
    """Embedded list & filter of customers."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)
        self.configure_grid()
        self.create_widgets()
        self.load_all_rows()

    def configure_grid(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def create_widgets(self) -> None:
        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="ew", pady=4)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Ara (isim/telefon/adres):").grid(row=0, column=0)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(frm, textvariable=self.search_var)
        entry.grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self.on_filter_change)

        cols = ("id", "name", "phone", "address")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(4,0))
        for col, txt, w in zip(cols,
                               ("ID","İsim","Telefon","Adres"),
                               (60,180,120,280)):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=("center" if col=="id" else "w"))

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")

    def load_all_rows(self) -> None:
        self.tree.delete(*self.tree.get_children())
        with db.session() as s:
            for r in s.query(db.Customer.id, db.Customer.name,
                             db.Customer.phone, db.Customer.address).order_by(db.Customer.name):
                self.tree.insert("", "end", values=tuple(r))

    def on_filter_change(self, *_):
        term = self.search_var.get().lower().strip()
        self.tree.delete(*self.tree.get_children())
        with db.session() as s:
            q = s.query(db.Customer.id, db.Customer.name,
                        db.Customer.phone, db.Customer.address)
            if term:
                q = q.filter(
                    (db.Customer.name.ilike(f"%{term}%")) |
                    (db.Customer.phone.ilike(f"%{term}%")) |
                    (db.Customer.address.ilike(f"%{term}%"))
                )
            for r in q.order_by(db.Customer.name):
                self.tree.insert("", "end", values=tuple(r))
