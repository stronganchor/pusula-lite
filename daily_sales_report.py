# daily_sales_report.py
# Daily sales report with date filtering and summary statistics

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
import decimal

import remote_api
from customer_detail import SaleEditDialog
from date_utils import format_date_tr, parse_date_tr, today_str_tr


def format_currency(amount: decimal.Decimal) -> str:
    """Format a Decimal into Turkish currency, e.g. 1.000.000,00₺."""
    s = f"{amount:,.2f}"
    integer, dec = s.split(".")
    integer = integer.replace(",", ".")
    return f"{integer},{dec}₺"


class DailySalesReportFrame(ttk.Frame):
    """Daily sales report with date range filtering."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # Variables
        self.var_start_date = tk.StringVar(value=today_str_tr())
        self.var_end_date = tk.StringVar(value=today_str_tr())
        self.var_total_sales = tk.StringVar(value="0,00₺")
        self.var_num_sales = tk.StringVar(value="0")

        pad = {"padx": 8, "pady": 4}
        row = 0

        # --- Date Range Selection ---
        filter_frame = ttk.LabelFrame(self, text="Tarih Seçimi", padding=8)
        filter_frame.grid(row=row, column=0, columnspan=4, sticky="ew", **pad)

        ttk.Label(filter_frame, text="Başlangıç:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(filter_frame, textvariable=self.var_start_date, width=12).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(filter_frame, text="Bitiş:").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        ttk.Entry(filter_frame, textvariable=self.var_end_date, width=12).grid(
            row=0, column=3, sticky="w", padx=4, pady=2
        )

        ttk.Button(filter_frame, text="Raporla", command=self.load_report).grid(
            row=0, column=4, padx=8, pady=2
        )

        # Quick date buttons
        ttk.Button(filter_frame, text="Bugün", command=self.set_today).grid(
            row=0, column=5, padx=2, pady=2
        )
        ttk.Button(filter_frame, text="Bu Hafta", command=self.set_this_week).grid(
            row=0, column=6, padx=2, pady=2
        )
        ttk.Button(filter_frame, text="Bu Ay", command=self.set_this_month).grid(
            row=0, column=7, padx=2, pady=2
        )

        row += 1

        # --- Summary Statistics ---
        summary_frame = ttk.LabelFrame(self, text="Özet", padding=8)
        summary_frame.grid(row=row, column=0, columnspan=4, sticky="ew", **pad)

        ttk.Label(summary_frame, text="Toplam Satış Tutarı:").grid(
            row=0, column=0, sticky="e", padx=4, pady=2
        )
        ttk.Label(summary_frame, textvariable=self.var_total_sales, font="TkHeadingFont").grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(summary_frame, text="Satış Sayısı:").grid(
            row=0, column=2, sticky="e", padx=12, pady=2
        )
        ttk.Label(summary_frame, textvariable=self.var_num_sales, font="TkHeadingFont").grid(
            row=0, column=3, sticky="w", padx=4, pady=2
        )

        row += 1

        # --- Sales Table ---
        cols = ("sale_id", "customer_name", "date", "total", "description")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        headings = ("No", "Müşteri", "Tarih", "Tutar", "Açıklama")
        widths = (60, 180, 100, 120, 280)

        for col, txt, w in zip(cols, headings, widths):
            anchor = "center" if col in ("sale_id", "date", "total") else "w"
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=anchor)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=row, column=0, columnspan=4, sticky="nsew", **pad)
        sb.grid(row=row, column=4, sticky="ns")

        # Enable double-click edit and track selection for the button state
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_edit_button())
        self.tree.bind("<Double-1>", lambda e: self.edit_selected_sale())

        self.columnconfigure(0, weight=1)
        self.rowconfigure(row, weight=1)

        row += 1

        # Actions
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=4, sticky="e", padx=8, pady=(0, 4))
        self.btn_edit_sale = ttk.Button(
            btn_frame,
            text="Satışı Düzelt",
            command=self.edit_selected_sale,
            state="disabled",
        )
        self.btn_edit_sale.pack(side="right", padx=4)

        # Load initial report
        self.load_report()

    def set_today(self) -> None:
        """Set date range to today."""
        today = today_str_tr()
        self.var_start_date.set(today)
        self.var_end_date.set(today)
        self.load_report()

    def set_this_week(self) -> None:
        """Set date range to current week (Monday to Sunday)."""
        today = date.today()
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        self.var_start_date.set(format_date_tr(start))
        self.var_end_date.set(format_date_tr(end))
        self.load_report()

    def set_this_month(self) -> None:
        """Set date range to current month."""
        today = date.today()
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(day=31)
        else:
            end = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        self.var_start_date.set(format_date_tr(start))
        self.var_end_date.set(format_date_tr(end))
        self.load_report()

    def load_report(self) -> None:
        """Load sales for the selected date range."""
        try:
            start = parse_date_tr(self.var_start_date.get())
            end = parse_date_tr(self.var_end_date.get())
        except ValueError:
            self.var_total_sales.set("0,00₺")
            self.var_num_sales.set("0")
            self.tree.delete(*self.tree.get_children())
            return

        try:
            sales = remote_api.list_sales(start=start.isoformat(), end=end.isoformat())
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            sales = []

        # Update summary
        total_amount = sum(decimal.Decimal(str(s.get("total", "0") or "0")) for s in sales)
        self.var_total_sales.set(format_currency(total_amount))
        self.var_num_sales.set(str(len(sales)))

        # Populate tree
        self.tree.delete(*self.tree.get_children())
        for sale in sales:
            sale_id = sale.get("id")
            cust_name = sale.get("customer_name", "")
            sale_date = sale.get("date")
            try:
                sale_date_obj = date.fromisoformat(sale_date) if sale_date else None
            except Exception:
                sale_date_obj = None
            total = decimal.Decimal(str(sale.get("total", "0") or "0"))
            desc = sale.get("description")
            self.tree.insert(
                "",
                "end",
                values=(
                    sale_id,
                    cust_name,
                    format_date_tr(sale_date_obj),
                    format_currency(total),
                    desc or ""
                ),
            )

        self.update_edit_button()

    def update_edit_button(self) -> None:
        """Enable/disable the edit button based on row selection."""
        state = "normal" if self.tree.selection() else "disabled"
        self.btn_edit_sale.config(state=state)

    def _select_sale_in_tree(self, sale_id: int) -> None:
        """Re-select a sale row by id after reload to keep context."""
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            if vals and int(vals[0]) == sale_id:
                self.tree.selection_set(item)
                self.tree.see(item)
                break
        self.update_edit_button()

    def edit_selected_sale(self) -> None:
        """Open the Satışı Düzelt dialog for the selected sale."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        sale_id = item["values"][0]

        # Fetch current sale data
        try:
            remote_api.acquire_lock("sale", int(sale_id), mode="write")
        except remote_api.ApiError as e:
            if e.status == 409:
                messagebox.showinfo("Kilitli", "Bu satış başka bir cihaz tarafından düzenleniyor.")
                return
            messagebox.showerror("API Hatası", e.message)
            return

        sale = remote_api.get_sale(int(sale_id))
        if not sale:
            messagebox.showerror("Hata", "Satış bulunamadı.")
            remote_api.release_lock("sale", int(sale_id))
            return

        current_date = date.fromisoformat(sale.get("date"))
        current_total = decimal.Decimal(str(sale.get("total", "0") or "0"))
        current_desc = sale.get("description") or ""

        installments = sale.get("installments") or []
        n_installments = len(installments)
        old_inst_sum = sum(decimal.Decimal(str(inst.get("amount", "0") or "0")) for inst in installments)

        # Open edit dialog (same as taksitli satış tab)
        dialog = SaleEditDialog(self, sale_id, current_date, current_total, current_desc)
        self.wait_window(dialog)

        if not dialog.result:
            remote_api.release_lock("sale", int(sale_id))
            return

        new_total = dialog.result["total"]

        # Calculate down payment (original total - sum of installments)
        down_payment = current_total - old_inst_sum

        # Calculate new installment amount
        if n_installments > 0:
            remaining = new_total - down_payment
            new_inst_amount = (remaining / n_installments).quantize(decimal.Decimal("0.01"))
        else:
            new_inst_amount = decimal.Decimal("0.00")

        # Update sale and installments in database
        try:
            remote_api.save_sale(
                {
                    "id": sale_id,
                    "date": dialog.result["date"].isoformat(),
                    "total": float(new_total),
                    "description": dialog.result["description"],
                }
            )
            for inst in installments:
                remote_api.save_installment(
                    {
                        "id": inst.get("id"),
                        "sale_id": sale_id,
                        "due_date": inst.get("due_date"),
                        "amount": float(new_inst_amount),
                        "paid": inst.get("paid", 0),
                    }
                )
        except remote_api.ApiError as e:
            messagebox.showerror("API Hatası", e.message)
            return
        finally:
            remote_api.release_lock("sale", int(sale_id))

        messagebox.showinfo("Başarılı", "Satış güncellendi.")
        self.load_report()
        self._select_sale_in_tree(sale_id)
