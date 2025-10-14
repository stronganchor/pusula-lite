# customer_detail.py
# Static "Taksitli Satış Kayıt Bilgisi" tab – upper half: sales list;
# lower half: installment report + ödeme recording.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import calendar
from datetime import date, datetime
import decimal

from sqlalchemy import func

import db
import app_state

# Turkish month names, index 1–12
TURKISH_MONTHS = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

def format_currency(amount: decimal.Decimal) -> str:
    """Format a Decimal into Turkish currency, e.g. 1.000.000,00₺."""
    s = f"{amount:,.2f}"               # "1,000,000.00"
    integer, dec = s.split(".")        # ["1,000,000","00"]
    integer = integer.replace(",", ".")
    return f"{integer},{dec}₺"

def parse_currency(text: str) -> decimal.Decimal:
    """Parse Turkish currency format back to Decimal."""
    # Remove ₺ symbol and spaces
    text = text.replace("₺", "").replace(" ", "")
    # Replace . with nothing (thousands separator)
    text = text.replace(".", "")
    # Replace , with . (decimal separator)
    text = text.replace(",", ".")
    return decimal.Decimal(text)


class SaleEditDialog(tk.Toplevel):
    """Dialog for editing sale details."""

    def __init__(self, parent, sale_id: int, current_date: date, current_total: decimal.Decimal, current_desc: str):
        super().__init__(parent)
        self.title("Satışı Düzelt")
        self.geometry("500x250")
        self.resizable(False, False)

        self.result = None
        self.sale_id = sale_id

        pad = {"padx": 8, "pady": 4}

        # Date
        ttk.Label(self, text="Tarih (YYYY-MM-DD):").grid(row=0, column=0, sticky="e", **pad)
        self.var_date = tk.StringVar(value=current_date.strftime("%Y-%m-%d"))
        ttk.Entry(self, textvariable=self.var_date, width=15).grid(row=0, column=1, sticky="w", **pad)

        # Total
        ttk.Label(self, text="Toplam Tutar:").grid(row=1, column=0, sticky="e", **pad)
        self.var_total = tk.StringVar(value=str(current_total))
        ttk.Entry(self, textvariable=self.var_total, width=15).grid(row=1, column=1, sticky="w", **pad)

        # Description
        ttk.Label(self, text="Açıklama:").grid(row=2, column=0, sticky="ne", **pad)
        self.txt_desc = tk.Text(self, width=40, height=6, wrap="word")
        self.txt_desc.grid(row=2, column=1, sticky="w", **pad)
        if current_desc:
            self.txt_desc.insert("1.0", current_desc)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=16)
        ttk.Button(btn_frame, text="Kaydet", command=self.save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="İptal", command=self.cancel).pack(side="left", padx=4)

        # Make modal
        self.transient(parent)
        self.grab_set()

    def save(self):
        """Validate and save changes."""
        try:
            new_date = datetime.strptime(self.var_date.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showwarning("Hatalı Tarih", "Tarih formatı YYYY-MM-DD olmalıdır.", parent=self)
            return

        try:
            new_total = decimal.Decimal(self.var_total.get().strip())
            if new_total <= 0:
                raise ValueError
        except (decimal.InvalidOperation, ValueError):
            messagebox.showwarning("Hatalı Tutar", "Geçerli bir tutar giriniz.", parent=self)
            return

        new_desc = self.txt_desc.get("1.0", tk.END).strip()

        self.result = {
            "date": new_date,
            "total": new_total,
            "description": new_desc
        }
        self.destroy()

    def cancel(self):
        """Close without saving."""
        self.result = None
        self.destroy()


class CustomerDetailFrame(ttk.Frame):
    """Shows header info + sales list for a customer.
    Upper half: list of sales.
    Lower half: installment report by year/month, plus Ödeme on a single line."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # Header
        self.var_id      = tk.StringVar()
        self.var_name    = tk.StringVar()
        self.var_phone   = tk.StringVar()
        self.var_address = tk.StringVar()

        # Report
        self.report_year_var = tk.StringVar()
        self.var_total_debt  = tk.StringVar()

        # Ödeme
        self.payment_month_var  = tk.StringVar()
        self.payment_amount_var = tk.StringVar()

        pad = {"padx": 8, "pady": 4}
        row = 0

        # – Müşteri No entry –
        ttk.Label(self, text="Müşteri No:").grid(row=row, column=0, sticky="e", **pad)
        ent_id = ttk.Entry(self, textvariable=self.var_id, width=10)
        ent_id.grid(row=row, column=1, sticky="w", **pad)
        ent_id.bind("<FocusOut>", self.load_customer)
        row += 1

        # – Header info –
        ttk.Label(self, text="Adı Soyadı:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_name).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="Telefon:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_phone).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="Adres:").grid(row=row, column=0, sticky="ne", **pad)
        lbl_addr = ttk.Label(
            self, textvariable=self.var_address, wraplength=400, justify="left"
        )
        lbl_addr.grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

        # – Sales table (upper half, taller) –
        cols = ("sale_id", "tarih", "tutar", "aciklama")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        headings = ("No", "Tarih", "Toplam Tutar", "Açıklama")
        widths   = (60,    100,         120,            300)
        for col, txt, w in zip(cols, headings, widths):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center")
        self.tree.grid(row=row, column=0, columnspan=4, sticky="nsew", **pad)
        self.columnconfigure(3, weight=1)
        self.rowconfigure(row, weight=1)

        # Bind selection and double-click
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_sale_buttons())
        self.tree.bind("<Double-1>", lambda e: self.edit_sale())

        row += 1

        # – Sales action buttons –
        sale_btn_frame = ttk.Frame(self)
        sale_btn_frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(0, 4))

        self.btn_edit_sale = ttk.Button(
            sale_btn_frame,
            text="Düzelt",
            command=self.edit_sale,
            state="disabled"
        )
        self.btn_edit_sale.pack(side="left", padx=4)

        self.btn_delete_sale = ttk.Button(
            sale_btn_frame,
            text="Sil",
            command=self.delete_sale,
            state="disabled"
        )
        self.btn_delete_sale.pack(side="left", padx=4)

        row += 1

        # – Separator to report –
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

        # – Report controls –
        ttk.Label(self, text="Yıl:").grid(row=row, column=0, sticky="e", **pad)
        self.cmb_year = ttk.Combobox(
            self, textvariable=self.report_year_var, state="readonly", width=6
        )
        self.cmb_year.grid(row=row, column=1, sticky="w", **pad)
        self.cmb_year.bind("<<ComboboxSelected>>", lambda e: self.load_report())

        ttk.Label(self, text="Toplam Borç:").grid(row=row, column=2, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_total_debt).grid(
            row=row, column=3, sticky="w", **pad
        )
        row += 1

        # – Installment report table (lower half, taller) –
        rep_cols = ("month", "amount", "paid")
        self.report_tree = ttk.Treeview(self, columns=rep_cols, show="headings", height=10)
        rep_headings = ("Ay", "Tutar", "Ödendi")
        rep_widths   = (150,    100,     80)
        for col, txt, w in zip(rep_cols, rep_headings, rep_widths):
            self.report_tree.heading(col, text=txt)
            self.report_tree.column(col, width=w, anchor="center")
        self.report_tree.grid(row=row, column=0, columnspan=4, sticky="nsew", **pad)
        self.rowconfigure(row, weight=1)

        # Bind selection for undo payment button
        self.report_tree.bind("<<TreeviewSelect>>", lambda e: self.update_undo_button())

        row += 1

        # – Separator to Ödeme section –
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

        # – Ödeme section all on one line, tighter spacing –
        pay_frame = ttk.Frame(self)
        pay_frame.grid(row=row, column=0, columnspan=4, sticky="w", pady=(2,4))

        ttk.Label(pay_frame, text="Ödeme Ayı:").grid(row=0, column=0, padx=4, pady=2)
        self.cmb_pay_month = ttk.Combobox(
            pay_frame,
            textvariable=self.payment_month_var,
            values=TURKISH_MONTHS[1:],
            state="readonly",
            width=10
        )
        self.cmb_pay_month.grid(row=0, column=1, padx=4, pady=2)
        self.cmb_pay_month.bind("<<ComboboxSelected>>", lambda e: self.update_payment_amount())

        ttk.Label(pay_frame, text="Tutar:").grid(row=0, column=2, padx=4, pady=2)
        self.entry_pay_amount = ttk.Entry(
            pay_frame, textvariable=self.payment_amount_var, width=15
        )
        self.entry_pay_amount.grid(row=0, column=3, padx=4, pady=2)

        self.btn_save_payment = ttk.Button(
            pay_frame, text="Ödemeyi Kaydet", command=self.save_payment
        )
        self.btn_save_payment.grid(row=0, column=4, padx=4, pady=2)

        self.btn_undo_payment = ttk.Button(
            pay_frame, text="Ödemeyi Geri Al", command=self.undo_payment, state="disabled"
        )
        self.btn_undo_payment.grid(row=0, column=5, padx=4, pady=2)

        # Initial population
        self.load_customer()


    def load_customer(self, event=None) -> None:
        """
        Load header + sales for a given customer.
        If called with an integer 'event', use that as the ID.
        Otherwise, read from the entry or fall back to last-selected.
        """
        # Determine customer ID
        if isinstance(event, int):
            cust_id = event
        else:
            raw = self.var_id.get().strip()
            if raw.isdigit():
                cust_id = int(raw)
            else:
                cust_id = app_state.last_customer_id
                if cust_id is None:
                    with db.session() as s:
                        rec = s.query(db.Customer.id) \
                               .order_by(db.Customer.id.desc()) \
                               .first()
                        cust_id = rec[0] if rec else None

        if cust_id is None:
            return

        # Fetch customer + sales
        with db.session() as s:
            cust = s.get(db.Customer, cust_id)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cust_id} numaralı müşteri yok.")
                return

            name  = cust.name or ""
            phone = cust.phone or ""
            addr  = cust.address or ""
            sales = (
                s.query(db.Sale.id, db.Sale.date, db.Sale.total, db.Sale.description)
                 .filter_by(customer_id=cust_id)
                 .order_by(db.Sale.date)
                 .all()
            )

        # Update header + state
        self.var_id.set(str(cust_id))
        self.var_name.set(name)
        self.var_phone.set(phone)
        self.var_address.set(addr)
        app_state.last_customer_id = cust_id

        # Populate sales table
        self.tree.delete(*self.tree.get_children())
        for sid, dt_, tot, desc in sales:
            self.tree.insert(
                "",
                "end",
                values=(
                    sid,
                    dt_.strftime("%Y-%m-%d"),
                    format_currency(tot),
                    desc or ""
                ),
            )

        # Update button states
        self.update_sale_buttons()

        # Refresh report & payment section
        self.populate_years(cust_id)
        self.load_report()


    def update_sale_buttons(self) -> None:
        """Enable/disable sale edit/delete buttons based on selection."""
        has_selection = bool(self.tree.selection())
        state = "normal" if has_selection else "disabled"
        self.btn_edit_sale.config(state=state)
        self.btn_delete_sale.config(state=state)


    def edit_sale(self) -> None:
        """Open dialog to edit the selected sale."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        sale_id = item["values"][0]

        # Fetch current sale data
        with db.session() as s:
            sale = s.get(db.Sale, sale_id)
            if not sale:
                messagebox.showerror("Hata", "Satış bulunamadı.")
                return

            current_date = sale.date
            current_total = sale.total
            current_desc = sale.description or ""

        # Open edit dialog
        dialog = SaleEditDialog(self, sale_id, current_date, current_total, current_desc)
        self.wait_window(dialog)

        if dialog.result:
            # Update sale in database
            with db.session() as s:
                sale = s.get(db.Sale, sale_id)
                sale.date = dialog.result["date"]
                sale.total = dialog.result["total"]
                sale.description = dialog.result["description"]

            messagebox.showinfo("Başarılı", "Satış güncellendi.")
            self.load_customer()


    def delete_sale(self) -> None:
        """Delete the selected sale after confirmation."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        sale_id = item["values"][0]

        # Confirm deletion
        response = messagebox.askyesno(
            "Satışı Sil",
            "Bu satışı ve tüm taksitlerini silmek istediğinizden emin misiniz?",
            icon="warning"
        )

        if response:
            with db.session() as s:
                sale = s.get(db.Sale, sale_id)
                if sale:
                    s.delete(sale)

            messagebox.showinfo("Başarılı", "Satış silindi.")
            self.load_customer()


    def populate_years(self, cust_id: int) -> None:
        """Fill year list based on installments, default to current year."""
        this_year = date.today().year
        with db.session() as s:
            years = {
                inst.due_date.year
                for sale in s.query(db.Sale).filter_by(customer_id=cust_id)
                for inst in sale.installments
            }
        if not years:
            years = {this_year}
        vals = sorted(years)
        self.cmb_year["values"] = vals
        default = this_year if this_year in vals else vals[-1]
        self.report_year_var.set(str(default))


    def load_report(self) -> None:
        """Load combined monthly report, update toplam borç, and set ödeme defaults."""
        cust_id = int(self.var_id.get())
        year = int(self.report_year_var.get())

        with db.session() as s:
            rows = (
                s.query(db.Installment.due_date, db.Installment.amount, db.Installment.paid)
                 .join(db.Sale)
                 .filter(
                     db.Sale.customer_id == cust_id,
                     func.strftime("%Y", db.Installment.due_date) == str(year)
                 )
                 .order_by(db.Installment.due_date)
                 .all()
            )

        # Group by month
        grouped: dict[int, dict[str, decimal.Decimal | bool]] = {}
        for due_date, amount, paid in rows:
            m = due_date.month
            if m not in grouped:
                grouped[m] = {"total": decimal.Decimal("0.00"), "all_paid": True}
            grouped[m]["total"] += amount
            if not paid:
                grouped[m]["all_paid"] = False

        # Update toplam borç: sum of unpaid months
        total_debt = sum(v["total"] for v in grouped.values() if not v["all_paid"])
        self.var_total_debt.set(format_currency(total_debt))

        # Populate report tree
        self.report_tree.delete(*self.report_tree.get_children())
        for m in sorted(grouped):
            total = grouped[m]["total"]
            paid_str = "Evet" if grouped[m]["all_paid"] else "Hayır"
            self.report_tree.insert(
                "", "end",
                values=(TURKISH_MONTHS[m], format_currency(total), paid_str)
            )

        # Determine earliest unpaid month (if any)
        unpaid = [m for m, v in grouped.items() if not v["all_paid"]]
        if unpaid:
            m0 = min(unpaid)
            self.payment_month_var.set(TURKISH_MONTHS[m0])
            self.cmb_pay_month.config(state="readonly")
            self.entry_pay_amount.config(state="normal")
            self.payment_amount_var.set(format_currency(grouped[m0]["total"]))
            self.btn_save_payment.config(state="normal")
        else:
            # disable Ödeme section
            self.payment_month_var.set("")
            self.payment_amount_var.set("")
            self.cmb_pay_month.config(state="disabled")
            self.entry_pay_amount.config(state="disabled")
            self.btn_save_payment.config(state="disabled")

        # keep grouped for update_payment_amount
        self.current_grouped = grouped

        # Update undo button state
        self.update_undo_button()


    def update_payment_amount(self) -> None:
        """Update the Tutar field when the Ödeme Ayı changes."""
        month_name = self.payment_month_var.get()
        if not month_name or month_name not in TURKISH_MONTHS:
            return
        m = TURKISH_MONTHS.index(month_name)
        amt = self.current_grouped.get(m, {}).get("total", decimal.Decimal("0.00"))
        self.payment_amount_var.set(format_currency(amt))


    def update_undo_button(self) -> None:
        """Enable 'Ödemeyi Geri Al' button only if a paid month is selected."""
        selection = self.report_tree.selection()
        if not selection:
            self.btn_undo_payment.config(state="disabled")
            return

        item = self.report_tree.item(selection[0])
        paid_status = item["values"][2]  # "Evet" or "Hayır"

        if paid_status == "Evet":
            self.btn_undo_payment.config(state="normal")
        else:
            self.btn_undo_payment.config(state="disabled")


    def save_payment(self) -> None:
        """Mark all installments for the selected year+month as paid."""
        cust_id = int(self.var_id.get())
        year = int(self.report_year_var.get())
        month_name = self.payment_month_var.get()
        m = TURKISH_MONTHS.index(month_name)

        with db.session() as s:
            insts = (
                s.query(db.Installment)
                 .join(db.Sale)
                 .filter(
                     db.Sale.customer_id == cust_id,
                     func.strftime("%Y", db.Installment.due_date) == str(year),
                     func.strftime("%m", db.Installment.due_date) == f"{m:02d}"
                 )
                 .all()
            )
            for inst in insts:
                inst.paid = 1

        messagebox.showinfo("Ödeme Kaydedildi", f"{month_name} taksitleri ödendi.")
        self.load_report()


    def undo_payment(self) -> None:
        """Mark all installments for the selected month as unpaid."""
        selection = self.report_tree.selection()
        if not selection:
            return

        item = self.report_tree.item(selection[0])
        month_name = item["values"][0]

        # Confirm undo
        response = messagebox.askyesno(
            "Ödemeyi Geri Al",
            f"{month_name} ayı için yapılan ödemeyi geri almak istediğinizden emin misiniz?",
            icon="warning"
        )

        if not response:
            return

        m = TURKISH_MONTHS.index(month_name)
        cust_id = int(self.var_id.get())
        year = int(self.report_year_var.get())

        with db.session() as s:
            insts = (
                s.query(db.Installment)
                 .join(db.Sale)
                 .filter(
                     db.Sale.customer_id == cust_id,
                     func.strftime("%Y", db.Installment.due_date) == str(year),
                     func.strftime("%m", db.Installment.due_date) == f"{m:02d}"
                 )
                 .all()
            )
            for inst in insts:
                inst.paid = 0

        messagebox.showinfo("Geri Alındı", f"{month_name} ödemesi geri alındı.")
        self.load_report()
