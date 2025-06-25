# customer_search.py
# Embedded list & filter of customers; shows most-recently created/selected first,
# split vertically, with bottom nav buttons to switch to other tabs,
# buttons disabled until a row is selected.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import db
import app_state

class CustomerSearchFrame(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        notebook: ttk.Notebook,
        detail_frame: ttk.Frame,
    ) -> None:
        super().__init__(master, padding=8)
        self.notebook     = notebook
        self.detail_frame = detail_frame

        # layout config…
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Top: search bar…
        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="ew", pady=4)
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text="Ara (isim/telefon/adres):").grid(row=0, column=0)
        self.search_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.search_var).grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self._on_filter)

        # Treeview columns
        cols = ("id", "name", "phone", "reg_date", "address")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        # Changed "ID" → "No"
        headings = ("No", "İsim", "Telefon", "Kayıt Tarihi", "Adres")
        widths   = (60,   180,     120,       100,           240)
        for col, txt, w in zip(cols, headings, widths):
            anchor = "center" if col in ("id", "reg_date") else "w"
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=anchor)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        sb.grid(row=1, column=1, sticky="ns")

        # Bind selection and double-click/Enter
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_nav_buttons())
        self.tree.bind("<Double-1>", self._load_detail)
        self.tree.bind("<Return>", self._load_detail)

        # --- Bottom: Navigation buttons ---
        nav = ttk.Frame(self)
        nav.grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        for idx in range(3):
            nav.columnconfigure(idx, weight=1)

        self.btn_edit = ttk.Button(
            nav,
            text="Müşteri Bilgilerini Düzelt",
            command=self.go_to_edit,
            state="disabled"
        )
        self.btn_edit.grid(row=0, column=0, sticky="ew", padx=4)

        self.btn_sale = ttk.Button(
            nav,
            text="Satış Kaydet",
            command=self.go_to_sale,
            state="disabled"
        )
        self.btn_sale.grid(row=0, column=1, sticky="ew", padx=4)

        self.btn_detail = ttk.Button(
            nav,
            text="Taksitli Satış Kayıt Bilgisi",
            command=self.go_to_detail,
            state="disabled"
        )
        self.btn_detail.grid(row=0, column=2, sticky="ew", padx=4)

        # Now that buttons exist, load initial data
        self._load_all()

    def _load_all(self) -> None:
        """Load all customers, newest first, with last-selected on top."""
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

        last = app_state.last_customer_id
        if last is not None:
            sel = [r for r in rows if r.id == last]
            oth = [r for r in rows if r.id != last]
            rows = sel + oth

        self.tree.delete(*self.tree.get_children())
        for r in rows:
            reg_str = r.registration_date.strftime("%Y-%m-%d")
            self.tree.insert(
                "", "end",
                values=(r.id, r.name, r.phone or "", reg_str, r.address or "")
            )

        # Enable/disable nav buttons
        self.update_nav_buttons()

    def _on_filter(self, *_args) -> None:
        """Filter customers by search term."""
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

        self.tree.delete(*self.tree.get_children())
        for r in rows:
            reg_str = r.registration_date.strftime("%Y-%m-%d")
            self.tree.insert(
                "", "end",
                values=(r.id, r.name, r.phone or "", reg_str, r.address or "")
            )
        self.update_nav_buttons()

    def update_nav_buttons(self) -> None:
        """Enable nav buttons only if a customer row is selected."""
        has_sel = bool(self.tree.selection())
        state = "normal" if has_sel else "disabled"
        for btn in (self.btn_edit, self.btn_sale, self.btn_detail):
            btn.config(state=state)

    def _get_selected_cid(self) -> int | None:
        """Return the customer ID of the selected row, or None."""
        sel = self.tree.focus()
        if not sel:
            return None
        return self.tree.item(sel)["values"][0]

    def _load_detail(self, event=None) -> None:
        """Double-click or Enter: load into detail tab."""
        cid = self._get_selected_cid()
        if cid is None:
            return
        # set the ID in the detail frame, then reload
        self.detail_frame.var_id.set(str(cid))
        self.detail_frame.load_customer()
        self.notebook.select(self.detail_frame)

    def go_to_edit(self) -> None:
        """Load selected customer into AddCustomerFrame and switch tab."""
        cid = self._get_selected_cid()
        if cid is None:
            return
        self.add_frame.var_id.set(str(cid))
        self.add_frame.load_customer()
        self.notebook.select(self.add_frame)

    def go_to_sale(self) -> None:
        """Load selected customer into SaleFrame and switch tab."""
        cid = self._get_selected_cid()
        if cid is None:
            return
        self.sale_frame.select_customer(cid)
        self.notebook.select(self.sale_frame)

    def go_to_detail(self) -> None:
        """Load selected customer into CustomerDetailFrame and switch tab."""
        cid = self._get_selected_cid()
        if cid is None:
            return
        # same approach as above
        self.detail_frame.var_id.set(str(cid))
        self.detail_frame.load_customer()
        self.notebook.select(self.detail_frame)
