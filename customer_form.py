# customer_form.py
# “Müşteri Tanıtım Bilgileri” tab (add or edit)

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox

import db


class AddCustomerFrame(ttk.Frame):
    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # --- Variables ---
        self.var_id             = tk.StringVar()
        self.var_reg_date       = tk.StringVar()
        self.var_name           = tk.StringVar()
        self.var_phone          = tk.StringVar()
        self.var_address        = tk.StringVar()
        self.var_work_address   = tk.StringVar()
        self.var_notes          = tk.StringVar()
        # Ek Kişi 1
        self.c1_name            = tk.StringVar()
        self.c1_phone           = tk.StringVar()
        self.c1_home            = tk.StringVar()
        self.c1_work            = tk.StringVar()
        # Ek Kişi 2
        self.c2_name            = tk.StringVar()
        self.c2_phone           = tk.StringVar()
        self.c2_home            = tk.StringVar()
        self.c2_work            = tk.StringVar()

        pad = {"padx": 8, "pady": 4}
        row = 0

        # --- Customer No + Kayıt Tarihi ---
        ttk.Label(self, text="Müşteri No:").grid(row=row, column=0, sticky="e", **pad)
        entry_id = ttk.Entry(self, textvariable=self.var_id, width=10)
        entry_id.grid( row=row, column=1, sticky="w", **pad)
        entry_id.bind("<FocusOut>", lambda e: self.load_customer())

        ttk.Label(self, text="Kayıt Tarihi:").grid(row=row, column=2, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_reg_date).grid(row=row, column=3, sticky="w", **pad)
        row += 1

        # --- Adı Soyadı + Telefon ---
        ttk.Label(self, text="Adı Soyadı *").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_name, width=40).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_phone, width=25).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Separator(self, orient="horizontal")\
            .grid(row=row, column=0, columnspan=4, sticky="ew", **pad)
        row += 1

        # --- Adresler + Özel Notu ---
        ttk.Label(self, text="Ev Adresi").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_address, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="İş Adresi").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_work_address, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Özel Notu").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_notes, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Separator(self, orient="horizontal")\
            .grid(row=row, column=0, columnspan=4, sticky="ew", **pad)
        row += 1

        # --- Ek Kişi 1 ---
        ttk.Label(self, text="Ek Kişi 1").grid(row=row, column=0, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Adı Soyadı").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_name, width=30).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1
        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_phone, width=25).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1
        ttk.Label(self, text="Ev Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_home, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1
        ttk.Label(self, text="İş Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_work, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Separator(self, orient="horizontal")\
            .grid(row=row, column=0, columnspan=4, sticky="ew", **pad)
        row += 1

        # --- Ek Kişi 2 ---
        ttk.Label(self, text="Ek Kişi 2").grid(row=row, column=0, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Adı Soyadı").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_name, width=30).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1
        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_phone, width=25).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1
        ttk.Label(self, text="Ev Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_home, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1
        ttk.Label(self, text="İş Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_work, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        # --- Action buttons ---
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=2, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç", command=self.clear_all).grid(
            row=row, column=3, sticky="w", **pad
        )
        self.bind_all("<F10>", lambda e: self.save())

    def load_customer(self) -> None:
        """When you tab away from Müşteri No, load that record if it exists."""
        cid = self.var_id.get().strip()
        if not cid.isdigit():
            return
        with db.session() as s:
            cust = s.get(db.Customer, int(cid))
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
                return

            # Populate header + main fields
            self.var_reg_date.set(cust.registration_date.strftime("%Y-%m-%d"))
            self.var_name.set(cust.name)
            self.var_phone.set(cust.phone or "")
            self.var_address.set(cust.address or "")
            self.var_work_address.set(cust.work_address or "")
            self.var_notes.set(cust.notes or "")

            # Pull up to two existing contacts
            contacts = (
                s.query(db.Contact)
                 .filter_by(customer_id=cust.id)
                 .order_by(db.Contact.id)
                 .limit(2)
                 .all()
            )

        # Fill section 1 & 2
        for idx, (name, phone, home, work) in enumerate([
            (self.c1_name, self.c1_phone, self.c1_home, self.c1_work),
            (self.c2_name, self.c2_phone, self.c2_home, self.c2_work),
        ]):
            if idx < len(contacts):
                c = contacts[idx]
                name.set(c.name or "")
                phone.set(c.phone or "")
                home.set(c.home_address or "")
                work.set(c.work_address or "")
            else:
                name.set("")
                phone.set("")
                home.set("")
                work.set("")

    def save(self) -> None:
        """Insert a brand new customer or update an existing one."""
        name = self.var_name.get().strip()
        if not name:
            messagebox.showwarning("Eksik Bilgi", "Adı Soyadı zorunludur.")
            return

        # Determine if we’re updating
        cid = None
        raw = self.var_id.get().strip()
        if raw.isdigit():
            cid = int(raw)

        with db.session() as s:
            if cid:
                cust = s.get(db.Customer, cid)
                if cust:
                    # Update existing
                    cust.name = name
                    cust.phone = self.var_phone.get().strip()
                    cust.address = self.var_address.get().strip()
                    cust.work_address = self.var_work_address.get().strip()
                    cust.notes = self.var_notes.get().strip()
                else:
                    cid = None  # fallback to create
            if not cid:
                # New record
                cust = db.Customer(
                    name=name,
                    phone=self.var_phone.get().strip(),
                    address=self.var_address.get().strip(),
                    work_address=self.var_work_address.get().strip(),
                    notes=self.var_notes.get().strip(),
                )
                s.add(cust)
                s.flush()
                cid = cust.id
                self.var_id.set(str(cid))
                self.var_reg_date.set(cust.registration_date.strftime("%Y-%m-%d"))

            # Replace contacts 1 & 2
            s.query(db.Contact).filter_by(customer_id=cid).delete()
            for name_var, phone_var, home_var, work_var in [
                (self.c1_name, self.c1_phone, self.c1_home, self.c1_work),
                (self.c2_name, self.c2_phone, self.c2_home, self.c2_work),
            ]:
                nm   = name_var.get().strip()
                ph   = phone_var.get().strip()
                home = home_var.get().strip()
                work = work_var.get().strip()
                if nm or ph or home or work:
                    s.add(db.Contact(
                        customer_id=cid,
                        name=nm,
                        phone=ph,
                        home_address=home,
                        work_address=work,
                    ))

        messagebox.showinfo("Başarılı", "Müşteri kaydedildi.")
        self.clear_all()

    def clear_all(self) -> None:
        """Reset all fields to blank."""
        for var in [
            self.var_id, self.var_reg_date,
            self.var_name, self.var_phone,
            self.var_address, self.var_work_address,
            self.var_notes,
            self.c1_name, self.c1_phone, self.c1_home, self.c1_work,
            self.c2_name, self.c2_phone, self.c2_home, self.c2_work,
        ]:
            var.set("")
