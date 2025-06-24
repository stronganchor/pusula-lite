# customer_form.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from sqlalchemy import func

import db


class AddCustomerFrame(ttk.Frame):
    """“Müşteri Tanıtım Bilgileri” tab, for both new and existing customers."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)

        # ---- Variables ----
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

        # --- Müşteri No + Kayıt Tarihi ---
        ttk.Label(self, text="Müşteri No:").grid(row=row, column=0, sticky="e", **pad)
        entry_id = ttk.Entry(self, textvariable=self.var_id, width=10)
        entry_id.grid(row=row, column=1, sticky="w", **pad)
        entry_id.bind("<FocusOut>", lambda e: self.load_customer())

        ttk.Label(self, text="Kayıt Tarihi:").grid(row=row, column=2, sticky="e", **pad)
        ttk.Label(self, textvariable=self.var_reg_date).grid(row=row, column=3, sticky="w", **pad)
        row += 1

        # --- Adı Soyadı + Telefon ---
        ttk.Label(self, text="Adı Soyadı *").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_name, width=40)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_phone, width=25)\
            .grid(row=row, column=1, sticky="w", **pad)
        row += 1

        ttk.Separator(self, orient="horizontal")\
            .grid(row=row, column=0, columnspan=4, sticky="ew", **pad)
        row += 1

        # --- Ev / İş Adresi + Özel Notu ---
        ttk.Label(self, text="Ev Adresi").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_address, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="İş Adresi").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_work_address, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        ttk.Label(self, text="Özel Notu").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_notes, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        ttk.Separator(self, orient="horizontal")\
            .grid(row=row, column=0, columnspan=4, sticky="ew", **pad)
        row += 1

        # --- Ek Kişi 1 ---
        ttk.Label(self, text="Ek Kişi 1").grid(row=row, column=0, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Adı Soyadı").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_name, width=30)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_phone, width=25)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Ev Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_home, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="İş Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c1_work, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        ttk.Separator(self, orient="horizontal")\
            .grid(row=row, column=0, columnspan=4, sticky="ew", **pad)
        row += 1

        # --- Ek Kişi 2 ---
        ttk.Label(self, text="Ek Kişi 2").grid(row=row, column=0, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Adı Soyadı").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_name, width=30)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_phone, width=25)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Ev Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_home, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="İş Adresi").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.c2_work, width=60)\
            .grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        row += 1

        # --- Action buttons ---
        ttk.Button(self, text="Kaydet (F10)", command=self.save)\
            .grid(row=row, column=2, sticky="e", **pad)
        ttk.Button(self, text="Vazgeç", command=self.clear_all)\
            .grid(row=row, column=3, sticky="w", **pad)

        # F10 → save
        self.bind_all("<F10>", lambda e: self.save())

        # Populate defaults for a "new" customer
        self._new_customer_defaults()


    def _new_customer_defaults(self) -> None:
        """Set var_id to next consecutive ID and date to today."""
        with db.session() as s:
            last = s.query(func.max(db.Customer.id)).scalar() or 0
        self.var_id.set(str(last + 1))
        self.var_reg_date.set(date.today().strftime("%Y-%m-%d"))


    def load_customer(self) -> None:
        """Load existing customer when you tab away from Müşteri No."""
        raw = self.var_id.get().strip()
        if not raw.isdigit():
            return
        cid = int(raw)
        with db.session() as s:
            cust = s.get(db.Customer, cid)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
                return

            # Populate header + main
            self.var_reg_date.set(cust.registration_date.strftime("%Y-%m-%d"))
            self.var_name.set(cust.name)
            self.var_phone.set(cust.phone or "")
            self.var_address.set(cust.address or "")
            self.var_work_address.set(cust.work_address or "")
            self.var_notes.set(cust.notes or "")

            # Load up to two contacts
            contacts = (
                s.query(db.Contact)
                 .filter_by(customer_id=cid)
                 .order_by(db.Contact.id)
                 .limit(2)
                 .all()
            )

        for slot, vars in enumerate([
            (self.c1_name, self.c1_phone, self.c1_home, self.c1_work),
            (self.c2_name, self.c2_phone, self.c2_home, self.c2_work),
        ]):
            name_v, phone_v, home_v, work_v = vars
            if slot < len(contacts):
                c = contacts[slot]
                name_v.set(c.name or "")
                phone_v.set(c.phone or "")
                home_v.set(c.home_address or "")
                work_v.set(c.work_address or "")
            else:
                name_v.set("")
                phone_v.set("")
                home_v.set("")
                work_v.set("")


    def save(self) -> None:
        """Insert or update customer + exactly two contacts."""
        name = self.var_name.get().strip()
        if not name:
            messagebox.showwarning("Eksik Bilgi", "Adı Soyadı zorunludur.")
            return

        raw = self.var_id.get().strip()
        cid = int(raw) if raw.isdigit() else None

        with db.session() as s:
            # Determine create vs update
            if cid:
                cust = s.get(db.Customer, cid)
            else:
                cust = None

            if cust:
                # update
                cust.name             = name
                cust.phone            = self.var_phone.get().strip()
                cust.address          = self.var_address.get().strip()
                cust.work_address     = self.var_work_address.get().strip()
                cust.notes            = self.var_notes.get().strip()
            else:
                # new
                today = date.today()
                cust = db.Customer(
                    id=cid,
                    name=name,
                    phone=self.var_phone.get().strip(),
                    address=self.var_address.get().strip(),
                    work_address=self.var_work_address.get().strip(),
                    notes=self.var_notes.get().strip(),
                    registration_date=today,
                )
                s.add(cust)
                s.flush()  # get auto‐ID if cid was None
                cid = cust.id
                self.var_id.set(str(cid))
                self.var_reg_date.set(cust.registration_date.strftime("%Y-%m-%d"))

            # replace contacts
            s.query(db.Contact).filter_by(customer_id=cid).delete()
            for vars in [
                (self.c1_name, self.c1_phone, self.c1_home, self.c1_work),
                (self.c2_name, self.c2_phone, self.c2_home, self.c2_work),
            ]:
                nm, ph, hm, wk = [v.get().strip() for v in vars]
                if nm or ph or hm or wk:
                    s.add(db.Contact(
                        customer_id=cid,
                        name=nm,
                        phone=ph,
                        home_address=hm,
                        work_address=wk,
                    ))

        messagebox.showinfo("Başarılı", "Müşteri kaydedildi.")
        self.clear_all()


    def clear_all(self) -> None:
        """Wipe all fields and reset to “new” defaults."""
        for var in [
            self.var_id, self.var_reg_date,
            self.var_name, self.var_phone,
            self.var_address, self.var_work_address,
            self.var_notes,
            self.c1_name, self.c1_phone, self.c1_home, self.c1_work,
            self.c2_name, self.c2_phone, self.c2_home, self.c2_work,
        ]:
            var.set("")
        self._new_customer_defaults()
