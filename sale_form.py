# sale_form.py
# Record a sale and automatically create an instalment plan,
# now with editable Müşteri No, non-editable name label,
# and added 'Açıklama' Text field plus select_customer().

from __future__ import annotations
import datetime as dt
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import ttk, messagebox

import db
import app_state
import receipt_printer

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

        # Preview variables
        self.var_preview_amount = tk.StringVar(value="—")
        self.var_preview_last_date = tk.StringVar(value="—")

        pad = {"padx": 8, "pady": 4}
        row = 0

        # Customer selector
        ttk.Label(self, text="Müşteri No *").grid(row=row, column=0, sticky="e", **pad)
        ent_id = ttk.Entry(self, textvariable=self.var_customer_id, width=10)
        ent_id.grid(row=row, column=1, sticky="w", **pad)
        ent_id.bind("<FocusOut>", self.load_customer)
        ttk.Label(self, text="Adı Soyadı:").grid(row=row, column=2, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_customer_name).grid(
            row=row, column=3, sticky="w", **pad
        )
        row += 1

        # Date
        ttk.Label(self, text="Tarih (YYYY-MM-DD)").grid(row=row, column=0, sticky="e", **pad)
        ent_date = ttk.Entry(self, textvariable=self.var_date, width=15)
        ent_date.grid(row=row, column=1, sticky="w", **pad)
        ent_date.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        # Amounts
        ttk.Label(self, text="Toplam Tutar *").grid(row=row, column=0, sticky="e", **pad)
        ent_total = ttk.Entry(self, textvariable=self.var_total, width=15)
        ent_total.grid(row=row, column=1, sticky="w", **pad)
        ent_total.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        ttk.Label(self, text="Peşinat").grid(row=row, column=0, sticky="e", **pad)
        ent_down = ttk.Entry(self, textvariable=self.var_down, width=15)
        ent_down.grid(row=row, column=1, sticky="w", **pad)
        ent_down.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        ttk.Label(self, text="Taksit Sayısı *").grid(row=row, column=0, sticky="e", **pad)
        ent_n_inst = ttk.Entry(self, textvariable=self.var_n_inst, width=5)
        ent_n_inst.grid(row=row, column=1, sticky="w", **pad)
        ent_n_inst.bind("<KeyRelease>", lambda e: self.update_preview())
        row += 1

        # Açıklama
        ttk.Label(self, text="Açıklama").grid(row=row, column=0, sticky="ne", **pad)
        self.txt_description = tk.Text(self, width=60, height=4, wrap="word")
        self.txt_description.grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        # Preview section
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

        ttk.Label(self, text="Önizleme", font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Her Taksit Tutarı:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_preview_amount, foreground="blue").grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Son Taksit Tarihi:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_preview_last_date, foreground="blue").grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

        # Buttons
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=1, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç", command=self.clear_all).grid(
            row=row, column=2, sticky="w", **pad
        )
        self.bind_all("<F10>", lambda e: self.save())

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
                with db.session() as s:
                    rec = s.query(db.Customer.id).order_by(db.Customer.id.desc()).first()
                    cid = rec[0] if rec else None

        if cid is None:
            self.var_customer_name.set("(seçilmedi)")
            return

        with db.session() as s:
            cust = s.get(db.Customer, cid)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
                name = "(seçilmedi)"
            else:
                name = cust.name
                app_state.last_customer_id = cid

        self.var_customer_id.set(str(cid))
        self.var_customer_name.set(name)

    def update_preview(self) -> None:
        """Calculate and display preview of installment amount and last due date."""
        try:
            total = Decimal(self.var_total.get())
            down = Decimal(self.var_down.get())
            n_inst = int(self.var_n_inst.get())
            sale_date = dt.date.fromisoformat(self.var_date.get())

            if total <= 0 or n_inst < 1 or down < 0 or down > total:
                raise ValueError

            remaining = total - down
            inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))
            last_date = sale_date + dt.timedelta(days=30 * n_inst)

            self.var_preview_amount.set(f"{inst_amount:,.2f} ₺")
            self.var_preview_last_date.set(last_date.strftime("%Y-%m-%d"))

        except (InvalidOperation, ValueError):
            self.var_preview_amount.set("—")
            self.var_preview_last_date.set("—")

    def save(self) -> None:
        """Validate inputs, save sale + installments + açıklama."""
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
    
        try:
            sale_date = dt.date.fromisoformat(self.var_date.get())
        except ValueError:
            messagebox.showwarning("Hatalı Tarih", "Tarih formatı YYYY-MM-DD olmalıdır.")
            return
    
        try:
            total = Decimal(self.var_total.get())
            down = Decimal(self.var_down.get())
            n_inst = int(self.var_n_inst.get())
            if total <= 0 or n_inst < 1 or down < 0 or down > total:
                raise ValueError
        except (InvalidOperation, ValueError):
            messagebox.showwarning("Hatalı Giriş", "Tutarlar geçerli sayı olmalıdır.")
            return
    
        remaining = total - down
        inst_amount = (remaining / n_inst).quantize(Decimal("0.01"))
    
        # Save sale
        with db.session() as s:
            desc = self.txt_description.get("1.0", tk.END).strip()
            sale = db.Sale(
                date=sale_date,
                customer_id=cust_id,
                total=total,
                description=desc
            )
            s.add(sale)
            s.flush()
            sale_id = sale.id
            for i in range(1, n_inst + 1):
                due = sale_date + dt.timedelta(days=30 * i)
                s.add(db.Installment(
                    sale_id=sale.id,
                    due_date=due,
                    amount=inst_amount,
                    paid=0
                ))
    
        # Ask if user wants to print receipt
        response = messagebox.askyesno(
            "Başarılı",
            "Satış ve taksitler kaydedildi.\n\nSatış makbuzunu yazdırmak ister misiniz?"
        )
    
        if response:
            receipt_printer.print_receipt(sale_id)
    
        app_state.last_customer_id = cust_id
        self.clear_all()
        self.load_customer()

    def clear_all(self) -> None:
        """Reset sale-specific fields (keep customer)."""
        self.var_date.set(dt.date.today().isoformat())
        self.var_total.set("")
        self.var_down.set("0")
        self.var_n_inst.set("1")
        self.txt_description.delete("1.0", tk.END)
        self.var_preview_amount.set("—")
        self.var_preview_last_date.set("—")

    def select_customer(self, cid: int) -> None:
        """Called by customer_form: set and load given customer."""
        self.var_customer_id.set(str(cid))
        self.load_customer()
