# customer_search.py
# Embedded list & filter of customers; shows most-recently created/selected first,
# split vertically, with bottom nav buttons to switch to other tabs,
# buttons disabled until a row is selected.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import app_state
import updater
import remote_api
from date_utils import format_date_tr

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
        # Give adres more space; keep müşteri no compact
        frm.columnconfigure(1, weight=1)  # müşteri no
        frm.columnconfigure(3, weight=2)  # isim
        frm.columnconfigure(5, weight=2)  # telefon
        frm.columnconfigure(7, weight=3)  # adres

        ttk.Label(frm, text="Müşteri No:").grid(row=0, column=0, padx=(0, 6))
        self.search_id_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.search_id_var, width=10).grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ttk.Label(frm, text="İsim:").grid(row=0, column=2, padx=(0, 6))
        self.search_name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.search_name_var).grid(row=0, column=3, sticky="ew", padx=(0, 12))

        ttk.Label(frm, text="Telefon:").grid(row=0, column=4, padx=(0, 6))
        self.search_phone_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.search_phone_var).grid(row=0, column=5, sticky="ew", padx=(0, 12))

        ttk.Label(frm, text="Adres:").grid(row=0, column=6, padx=(0, 6))
        self.search_address_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.search_address_var, width=30).grid(row=0, column=7, sticky="ew")

        for var in (
            self.search_id_var,
            self.search_name_var,
            self.search_phone_var,
            self.search_address_var,
        ):
            var.trace_add("write", self._on_filter)

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
        for idx in range(4):
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

        self.btn_delete = ttk.Button(
            nav,
            text="Müşteri Sil",
            command=self.delete_customer,
            state="disabled"
        )
        self.btn_delete.grid(row=0, column=3, sticky="ew", padx=4)

        # Now that buttons exist, load initial data
        self._load_all()

    def _load_all(self) -> None:
        """Load all customers, newest first, with last-selected on top."""
        try:
            rows = remote_api.list_customers(limit=100)
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            rows = []

        last = app_state.last_customer_id
        if last is not None and rows:
            sel = [r for r in rows if int(r.get("id")) == last]
            oth = [r for r in rows if int(r.get("id")) != last]
            rows = sel + oth

        self._render_rows(rows)

        # Enable/disable nav buttons
        self.update_nav_buttons()

    def _on_filter(self, *_args) -> None:
        """Filter customers by search term."""
        id_term      = self.search_id_var.get().strip()
        name_term    = self.search_name_var.get().strip()
        phone_term   = self.search_phone_var.get().strip()
        address_term = self.search_address_var.get().strip()
        cid = int(id_term) if id_term.isdigit() else None
        try:
            rows = remote_api.list_customers(
                cid=cid,
                name=name_term or None,
                phone=phone_term or None,
                address=address_term or None,
                limit=100,
            )
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            rows = []

        self._render_rows(rows)
        self.update_nav_buttons()

    def update_nav_buttons(self) -> None:
        """Enable nav buttons only if a customer row is selected."""
        has_sel = bool(self.tree.selection())
        state = "normal" if has_sel else "disabled"
        for btn in (self.btn_edit, self.btn_sale, self.btn_detail, self.btn_delete):
            btn.config(state=state)

    def _get_selected_cid(self) -> int | None:
        """Return the customer ID of the selected row, or None."""
        sel = self.tree.focus()
        if not sel:
            return None
        return self.tree.item(sel)["values"][0]

    def _render_rows(self, rows: list[dict]) -> None:
        """Render customers into the treeview."""
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            reg_date = r.get("registration_date")
            if isinstance(reg_date, str):
                try:
                    reg_date = datetime.fromisoformat(reg_date).date()
                except ValueError:
                    reg_date = None
            reg_str = format_date_tr(reg_date) if reg_date else ""
            self.tree.insert(
                "", "end",
                values=(
                    r.get("id"),
                    r.get("name", ""),
                    r.get("phone", "") or "",
                    reg_str,
                    r.get("address", "") or ""
                )
            )

    def _load_detail(self, event=None) -> None:
        """Double-click or Enter: load into detail tab using exact ID."""
        cid = self._get_selected_cid()
        if cid is None:
            return
        app_state.last_customer_id = cid
        # Pass the ID directly to load_customer
        self.detail_frame.load_customer(cid)
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
        """Button: switch to detail tab for the selected customer."""
        cid = self._get_selected_cid()
        if cid is None:
            return
        app_state.last_customer_id = cid
        self.detail_frame.load_customer(cid)
        self.notebook.select(self.detail_frame)

    def delete_customer(self) -> None:
        """Delete the selected customer after double confirmation."""
        cid = self._get_selected_cid()
        if cid is None:
            return

        try:
            cust = remote_api.get_customer(cid)
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            return
        if not cust:
            messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
            self._load_all()
            return
        name = cust.get("name", "")

        dialog = updater.ConfirmDialog(
            self.winfo_toplevel(),
            "Müşteri Sil",
            f"{cid} - {name} müşterisini silmek istediğinize emin misiniz?"
        )
        self.wait_window(dialog)
        if not dialog.result:
            return

        dialog = updater.ConfirmDialog(
            self.winfo_toplevel(),
            "Müşteri Sil",
            "Bu işlem müşteriye ait tüm satış, taksit ve ödeme kayıtlarını kalıcı olarak silecek.\n\nSilmek istediğinizden emin misiniz?"
        )
        self.wait_window(dialog)
        if not dialog.result:
            return

        try:
            remote_api.delete_customer(cid)
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            return

        if app_state.last_customer_id == cid:
            app_state.last_customer_id = None

        if getattr(self, "detail_frame", None):
            try:
                self.detail_frame.var_id.set("")
                self.detail_frame.load_customer()
            except Exception:
                pass

        self._load_all()
        messagebox.showinfo("Silindi", "Müşteri ve ilişkili tüm kayıtlar silindi.")
