# customer_search.py
# Search / filter customers (Tkinter Treeview)

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import db


class CustomerSearchWindow(tk.Toplevel):
    """Popup window that lists customers and supports text filtering."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("Müşteri Arama")
        self.geometry("700x450")
        self.resizable(True, True)

        # Build UI
        self.configure_grid()
        self.create_widgets()
        self.load_all_rows()

        # Focus on search box immediately
        self.search_var.trace_add("write", self.on_filter_change)
        self.entry_search.focus()

    # ------------------------------------------------------------------ #
    #  Layout helpers                                                    #
    # ------------------------------------------------------------------ #

    def configure_grid(self) -> None:
        """Give the single Treeview row/col weight so it expands."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def create_widgets(self) -> None:
        """Top line search-entry + filter label, and the Treeview."""
        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="ew", pady=8, padx=8)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Ara (isim / telefon / adres):").grid(row=0, column=0)
        self.search_var = tk.StringVar()
        self.entry_search = ttk.Entry(frm, textvariable=self.search_var)
        self.entry_search.grid(row=0, column=1, sticky="ew")

        # Treeview
        cols = ("id", "name", "phone", "address")
        self.tree = ttk.Treeview(
            self,
            columns=cols,
            show="headings",
            height=20,
        )
        self.tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Configure headings (Turkish)
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="İsim")
        self.tree.heading("phone", text="Telefon")
        self.tree.heading("address", text="Adres")

        # Column widths
        self.tree.column("id", width=60, anchor=tk.CENTER)
        self.tree.column("name", width=180)
        self.tree.column("phone", width=120)
        self.tree.column("address", width=280)

        # Scrollbar
        sb_y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb_y.set)
        sb_y.grid(row=1, column=1, sticky="ns")  # right side of Treeview

        # Bind selection keys
        self.tree.bind("<Double-1>", self.on_choose)
        self.tree.bind("<Return>", self.on_choose)

    # ------------------------------------------------------------------ #
    #  Data handling                                                     #
    # ------------------------------------------------------------------ #

    def load_all_rows(self) -> None:
        """Fetch all customers from DB into the Treeview."""
        self.tree.delete(*self.tree.get_children())
        with db.session() as s:
            rows = (
                s.query(db.Customer.id, db.Customer.name,
                        db.Customer.phone, db.Customer.address)
                .order_by(db.Customer.name)
                .all()
            )
            for r in rows:
                self.tree.insert("", "end", values=tuple(r))

    def on_filter_change(self, *_args) -> None:
        """Filter rows in memory (simple case-insensitive substring match)."""
        term = self.search_var.get().lower().strip()

        # Clear current rows
        self.tree.delete(*self.tree.get_children())

        if not term:
            # If search box empty, reload all
            self.load_all_rows()
            return

        with db.session() as s:
            rows = (
                s.query(db.Customer.id, db.Customer.name,
                        db.Customer.phone, db.Customer.address)
                .filter(
                    (db.Customer.name.ilike(f"%{term}%"))
                    | (db.Customer.phone.ilike(f"%{term}%"))
                    | (db.Customer.address.ilike(f"%{term}%"))
                )
                .order_by(db.Customer.name)
                .all()
            )
            for r in rows:
                self.tree.insert("", "end", values=tuple(r))

    # ------------------------------------------------------------------ #
    #  Selection event                                                   #
    # ------------------------------------------------------------------ #

    def on_choose(self, _event=None) -> None:
        """Handle double-click / Enter on a row."""
        item = self.tree.focus()
        if not item:
            return
        row = self.tree.item(item)["values"]
        if row:
            customer_id = row[0]
            print(f"Seçilen müşteri ID: {customer_id}")
            # TODO: you can call SaleWindow directly, e.g.
            # from sale_form import SaleWindow
            # SaleWindow(self.master, customer_id)
            # For now we just close:
            self.destroy()
