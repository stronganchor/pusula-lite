# customer_search.py
# Embedded list & filter of customers; selecting one loads it into the detail tab

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import db


class CustomerSearchFrame(ttk.Frame):
    """List + filter customers; double-click or Enter loads the selected record
    into the provided detail_frame and switches to that tab."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        notebook: ttk.Notebook,
        detail_frame: ttk.Frame,  # will be CustomerDetailFrame
    ) -> None:
        super().__init__(master, padding=8)
        self.notebook = notebook
        self.detail_frame = detail_frame

        # Layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Search bar
        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="ew", pady=4)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Ara (isim/telefon/adres):").grid(row=0, column=0)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(frm, textvariable=self.search_var)
        entry.grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self._on_filter)

        # Treeview
        cols = ("id", "name", "phone", "address")
        self.tree = ttk.Treeview(
            self,
            columns=cols,
            show="headings",
            height=20,
        )
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        for col, txt, w in zip(cols, ("ID", "İsim", "Telefon", "Adres"), (60, 180, 120, 280)):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=("center" if col == "id" else "w"))

        # Scrollbar
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")

        # Bind to load detail
        self.tree.bind("<Double-1>", self._load_detail)
        self.tree.bind("<Return>", self._load_detail)

        # Initial load
        self._load_all()

    def _load_all(self) -> None:
        self.tree.delete(*self.tree.get_children())
        with db.session() as s:
            rows = (
                s.query(db.Customer.id, db.Customer.name, db.Customer.phone, db.Customer.address)
                 .order_by(db.Customer.name)
                 .all()
            )
        for r in rows:
            self.tree.insert("", "end", values=tuple(r))

    def _on_filter(self, *_args) -> None:
        term = self.search_var.get().lower().strip()
        self.tree.delete(*self.tree.get_children())
        with db.session() as s:
            q = s.query(db.Customer.id, db.Customer.name, db.Customer.phone, db.Customer.address)
            if term:
                q = q.filter(
                    (db.Customer.name.ilike(f"%{term}%")) |
                    (db.Customer.phone.ilike(f"%{term}%")) |
                    (db.Customer.address.ilike(f"%{term}%"))
                )
            rows = q.order_by(db.Customer.name).all()
        for r in rows:
            self.tree.insert("", "end", values=tuple(r))

    def _load_detail(self, event=None) -> None:
        """Fetch the selected customer ID and push it into the detail tab."""
        item = self.tree.focus()
        if not item:
            return
        cid = self.tree.item(item)["values"][0]
        # Call the detail_frame's loader
        self.detail_frame.load_customer(cid)
        # Switch to that tab
        self.notebook.select(self.detail_frame)
