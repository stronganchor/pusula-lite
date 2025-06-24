# customer_search.py
# Embedded list & filter of customers; shows most-recently created/selected first,
# includes Kayıt Tarihi column, and filters on search.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import db
import app_state


class CustomerSearchFrame(ttk.Frame):
    """List + filter customers; double-click or Enter loads the selected record
    into the detail tab."""

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

        # Make the Treeview expand
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

        # Columns: ID, İsim, Telefon, Kayıt Tarihi, Adres
        cols = ("id", "name", "phone", "reg_date", "address")
        self.tree = ttk.Treeview(
            self,
            columns=cols,
            show="headings",
            height=20,
        )
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        # Configure headings & column widths
        headings = ("ID", "İsim", "Telefon", "Kayıt Tarihi", "Adres")
        widths   = (60, 180, 120, 100, 240)
        for col, txt, w in zip(cols, headings, widths):
            anchor = "center" if col in ("id", "reg_date") else "w"
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=anchor)

        # Vertical scrollbar
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")

        # Bind double-click / Enter to load detail
        self.tree.bind("<Double-1>", self._load_detail)
        self.tree.bind("<Return>", self._load_detail)

        # Initial load
        self._load_all()

    def _load_all(self) -> None:
        """Load all customers, sorted newest first, with last-selected at the very top."""
        with db.session() as s:
            rows = (
                s.query(
                    db.Customer.id,
                    db.Customer.name,
                    db.Customer.phone,
                    db.Customer.registration_date,
                    db.Customer.address,
                )
                .order_by(
                    db.Customer.registration_date.desc(),
                    db.Customer.id.desc(),
                )
                .all()
            )

        # Reorder so last-selected (if any) appears first
        last = app_state.last_customer_id
        if last is not None:
            # find and move it to front
            selected = [r for r in rows if r.id == last]
            others   = [r for r in rows if r.id != last]
            rows = selected + others

        # Populate the tree
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            reg_str = r.registration_date.strftime("%Y-%m-%d")
            self.tree.insert(
                "",
                "end",
                values=(r.id, r.name, r.phone or "", reg_str, r.address or ""),
            )

    def _on_filter(self, *_args) -> None:
        """Show only customers matching the search term, sorted newest first."""
        term = self.search_var.get().lower().strip()
        with db.session() as s:
            q = s.query(
                db.Customer.id,
                db.Customer.name,
                db.Customer.phone,
                db.Customer.registration_date,
                db.Customer.address,
            )
            if term:
                like = f"%{term}%"
                q = q.filter(
                    (db.Customer.name.ilike(like))
                    | (db.Customer.phone.ilike(like))
                    | (db.Customer.address.ilike(like))
                )
            rows = (
                q.order_by(
                    db.Customer.registration_date.desc(),
                    db.Customer.id.desc(),
                )
                .all()
            )

        # Populate filtered tree
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            reg_str = r.registration_date.strftime("%Y-%m-%d")
            self.tree.insert(
                "",
                "end",
                values=(r.id, r.name, r.phone or "", reg_str, r.address or ""),
            )

    def _load_detail(self, event=None) -> None:
        """Fetch the selected customer ID, store it globally, and load detail."""
        item = self.tree.focus()
        if not item:
            return
        cid = self.tree.item(item)["values"][0]

        # Remember last selected
        app_state.last_customer_id = cid

        # Load into detail_frame and switch tab
        self.detail_frame.load_customer(cid)
        self.notebook.select(self.detail_frame)
