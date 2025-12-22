# sale_form.py
# Record a sale and automatically create an instalment plan,
# now with editable Müşteri No, non-editable name label,
# and added 'Açıklama' Text field plus select_customer().

from __future__ import annotations
import datetime as dt
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import ttk, messagebox
import updater

import app_state
import receipt_printer
import remote_api
from date_utils import format_date_tr, parse_date_tr, today_str_tr

class SaleFrame(ttk.Frame):
    """Embedded form for recording a new sale with equal instalments."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # State variables
        self.var_customer_id   = tk.StringVar()
        self.var_customer_name = tk.StringVar(value="(seçilmedi)")
        self.var_date          = tk.StringVar(value=today_str_tr())
        self.var_total         = tk.StringVar()
        self.var_down          = tk.StringVar(value="0")
        self.var_n_inst        = tk.StringVar(value="1")
        self.var_due_day       = tk.StringVar(value=str(min(dt.date.today().day, 28)))

        # Preview variables
        self.var_preview_amount = tk.StringVar(value="—")
        self.var_preview_last_date = tk.StringVar(value="—")

        pad = {"padx": 8, "pady": 4}

        # Layout: two columns (left inputs, right description)
        self.columnconfigure(0, weight=1, uniform="form")
        self.columnconfigure(1, weight=1, uniform="form")
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 4))
        left.columnconfigure(1, weight=1)
        left.columnconfigure(3, weight=1)

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 4))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        row = 0

        # Customer selector
        ttk.Label(left, text="Müşteri No *").grid(row=row, column=0, sticky="e", **pad)
        ent_id = ttk.Entry(left, textvariable=self.var_customer_id, width=10)
        ent_id.grid(row=row, column=1, sticky="w", **pad)
        ent_id.bind("<FocusOut>", self.load_customer)
        ttk.Label(left, text="Adı Soyadı:").grid(row=row, column=2, sticky="e", **pad)
        ttk.Label(left, textvariable=self.var_customer_name).grid(
            row=row, column=3, sticky="w", **pad
        )
        row += 1

        # Date
        ttk.Label(left, text="Tarih (GG-AA-YYYY)").grid(row=row, column=0, sticky="e", **pad)
        ent_date = ttk.Entry(left, textvariable=self.var_date, width=15)
        ent_date.grid(row=row, column=1, sticky="w", **pad)
        ent_date.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        # Amounts
        ttk.Label(left, text="Toplam Tutar *").grid(row=row, column=0, sticky="e", **pad)
        ent_total = ttk.Entry(left, textvariable=self.var_total, width=15)
        ent_total.grid(row=row, column=1, sticky="w", **pad)
        ent_total.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        ttk.Label(left, text="Peşinat").grid(row=row, column=0, sticky="e", **pad)
        ent_down = ttk.Entry(left, textvariable=self.var_down, width=15)
        ent_down.grid(row=row, column=1, sticky="w", **pad)
        ent_down.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        ttk.Label(left, text="Taksit Sayısı *").grid(row=row, column=0, sticky="e", **pad)
        ent_n_inst = ttk.Entry(left, textvariable=self.var_n_inst, width=5)
        ent_n_inst.grid(row=row, column=1, sticky="w", **pad)
        ent_n_inst.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        ttk.Label(left, text="Ödeme Günü (1-28)").grid(row=row, column=0, sticky="e", **pad)
        ent_due_day = ttk.Entry(left, textvariable=self.var_due_day, width=5)
        ent_due_day.grid(row=row, column=1, sticky="w", **pad)
        ent_due_day.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        # Açıklama (right column, tall with scrollbar)
        ttk.Label(right, text="Açıklama").grid(row=0, column=0, sticky="w", **pad)
        self.txt_description = tk.Text(right, width=60, height=20, wrap="word")
        self.txt_description.grid(row=1, column=0, sticky="nsew", **pad)
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.txt_description.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=pad["pady"])
        self.txt_description.configure(yscrollcommand=scroll.set)

        # Preview section
        ttk.Separator(self, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", **pad
        )

        preview = ttk.Frame(self)
        preview.grid(row=2, column=0, columnspan=2, sticky="ew")
        preview.columnconfigure(1, weight=1)

        prow = 0
        ttk.Label(preview, text="Önizleme", font="TkHeadingFont").grid(
            row=prow, column=0, columnspan=2, sticky="w", **pad
        )
        prow += 1

        ttk.Label(preview, text="Her Taksit Tutarı:").grid(row=prow, column=0, sticky="e", **pad)
        ttk.Label(preview, textvariable=self.var_preview_amount, style="PreviewValue.TLabel").grid(
            row=prow, column=1, sticky="w", **pad
        )
        prow += 1

        ttk.Label(preview, text="Son Taksit Tarihi:").grid(row=prow, column=0, sticky="e", **pad)
        ttk.Label(preview, textvariable=self.var_preview_last_date, style="PreviewValue.TLabel").grid(
            row=prow, column=1, sticky="w", **pad
        )

        ttk.Separator(self, orient="horizontal").grid(
            row=3, column=0, columnspan=2, sticky="ew", **pad
        )

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, sticky="e", pady=(0, 4))
        ttk.Button(btn_frame, text="Kaydet (F10)", command=self.save).grid(row=0, column=0, **pad)
        ttk.Button(btn_frame, text="Vazgeç", command=self.clear_all).grid(row=0, column=1, **pad)
        self.bind_all("<F10>", self._on_f10, add="+")

        # Load default customer
        self.load_customer()

    def load_customer(self, event=None) -> None:
        """Load by ID or fallback to last/newest."""
        raw = self.var_customer_id.get().strip()
        if raw.isdigit():
            cid = int(raw)
        else:
            cid = app_state.last_customer_id
            if cid is None:
                try:
                    customers = remote_api.list_customers(limit=1)
                    cid = max(int(c.get("id")) for c in customers) if customers else None
                except Exception:
                    cid = None

        if cid is None:
            self.var_customer_name.set("(seçilmedi)")
            return

        try:
            cust = remote_api.get_customer(cid)
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            return
        if not cust:
            messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
            name = "(seçilmedi)"
        else:
            name = cust.get("name")
            app_state.last_customer_id = cid

        self.var_customer_id.set(str(cid))
        self.var_customer_name.set(name)

    def update_preview(self) -> None:
        """Calculate and display preview of installment amount and last due date."""
        try:
            total = Decimal(self.var_total.get())
            down = Decimal(self.var_down.get())
            n_inst = int(self.var_n_inst.get())
            sale_date = parse_date_tr(self.var_date.get())
            due_day = int(self.var_due_day.get())

            if (
                total <= 0
                or n_inst < 1
                or down < 0
                or down > total
                or not (1 <= due_day <= 28)
            ):
                raise ValueError

            remaining = total - down
            inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))
            last_date = self._compute_due_date(sale_date, due_day, n_inst)

            self.var_preview_amount.set(f"{inst_amount:,.2f} ₺")
            self.var_preview_last_date.set(format_date_tr(last_date))

        except (InvalidOperation, ValueError):
            self.var_preview_amount.set("—")
            self.var_preview_last_date.set("—")

    def _compute_due_date(self, sale_date: dt.date, due_day: int, month_offset: int) -> dt.date:
        """Return the due date `month_offset` months after sale_date on the given day."""
        month_index = (sale_date.month - 1) + month_offset
        year = sale_date.year + month_index // 12
        month = (month_index % 12) + 1
        return dt.date(year, month, due_day)

    def save(self) -> None:
        """Validate inputs, save sale + installments + açıklama."""
        raw = self.var_customer_id.get().strip()
        if not raw.isdigit():
            messagebox.showwarning("Eksik Bilgi", "Geçerli müşteri numarası giriniz.")
            return
        cust_id = int(raw)
    
        try:
            cust = remote_api.get_customer(cust_id)
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            return
        if not cust:
            messagebox.showwarning("Bulunamadı", f"{cust_id} numaralı müşteri yok.")
            return
    
        try:
            sale_date = parse_date_tr(self.var_date.get())
        except ValueError:
            messagebox.showwarning("Hatalı Tarih", "Tarih formatı GG-AA-YYYY olmalıdır.")
            return
    
        try:
            total = Decimal(self.var_total.get())
            down = Decimal(self.var_down.get())
            n_inst = int(self.var_n_inst.get())
            due_day = int(self.var_due_day.get())
            if (
                total <= 0
                or n_inst < 1
                or down < 0
                or down > total
                or not (1 <= due_day <= 28)
            ):
                raise ValueError
        except (InvalidOperation, ValueError):
            messagebox.showwarning(
                "Hatalı Giriş",
                "Tutarlar geçerli sayı olmalıdır ve ödeme günü 1-28 arasında olmalıdır.",
            )
            return
    
        remaining = total - down
        inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))
    
        # Save sale
        desc = self.txt_description.get("1.0", tk.END).strip()
        try:
            sale_id = remote_api.save_sale(
                {
                    "customer_id": cust_id,
                    "date": sale_date.isoformat(),
                    "total": float(total),
                    "description": desc,
                }
            )
            for i in range(1, n_inst + 1):
                due = self._compute_due_date(sale_date, due_day, i)
                remote_api.save_installment(
                    {
                        "sale_id": sale_id,
                        "due_date": due.isoformat(),
                        "amount": float(inst_amount),
                        "paid": 0,
                    }
                )
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            return

        # Ask if user wants to print receipt
        dialog = updater.ConfirmDialog(
            self.winfo_toplevel(),
            "Başarılı",
            "Satış ve taksitler kaydedildi.\n\nSatış makbuzunu yazdırmak ister misiniz?"
        )
        self.wait_window(dialog)
    
        if dialog.result:
            receipt_printer.print_receipt(sale_id)
    
        app_state.last_customer_id = cust_id
        self.clear_all()
        self.load_customer()

    def clear_all(self) -> None:
        """Reset sale-specific fields (keep customer)."""
        self.var_date.set(today_str_tr())
        self.var_total.set("")
        self.var_down.set("0")
        self.var_n_inst.set("1")
        self.var_due_day.set(str(min(dt.date.today().day, 28)))
        self.txt_description.delete("1.0", tk.END)
        self.var_preview_amount.set("—")
        self.var_preview_last_date.set("—")

    def select_customer(self, cid: int) -> None:
        """Called by customer_form: set and load given customer."""
        self.var_customer_id.set(str(cid))
        self.load_customer()

    def _on_f10(self, event: tk.Event) -> str | None:
        """Fire save only when this tab is active."""
        if self.master.select() != str(self):
            return None
        self.save()
        return "break"
