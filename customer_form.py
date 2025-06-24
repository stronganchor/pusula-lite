# customer_form.py
# Converted AddCustomerWindow → AddCustomerFrame

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import db


class AddCustomerFrame(ttk.Frame):
    """Form to create a new customer with optional alternate contacts."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=8)
        # ---------------------------------------------------------------- #
        #  Variables                                                      #
        # ---------------------------------------------------------------- #
        self.var_name         = tk.StringVar()
        self.var_phone        = tk.StringVar()
        self.var_address      = tk.StringVar()       # Ev adresi
        self.var_work_address = tk.StringVar()       # İş adresi
        self.var_notes        = tk.StringVar()

        # Each contact: (name, phone, home_address, work_address)
        self.contacts: list[tuple[str, str, str, str]] = []

        # ---------------------------------------------------------------- #
        #  Layout                                                          #
        # ---------------------------------------------------------------- #
        pad = {"padx": 8, "pady": 4}
        row = 0

        # — Main customer fields —
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

        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

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

        ttk.Label(self, text="Notlar").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_notes, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        # — Alternate contacts —
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", **pad
        )
        row += 1

        ttk.Label(self, text="Ek Kişiler (Kefil / Diğer)").grid(
            row=row, column=0, sticky="ne", **pad
        )
        frm = ttk.Frame(self)
        frm.grid(row=row, column=1, columnspan=3, sticky="w", **pad)

        # Contact entry vars
        self.contact_name  = tk.StringVar()
        self.contact_phone = tk.StringVar()
        self.contact_home  = tk.StringVar()
        self.contact_work  = tk.StringVar()

        # Row 0: Name
        ttk.Label(frm, text="Adı Soyadı").grid(row=0, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.contact_name, width=25).grid(
            row=0, column=1, columnspan=3, sticky="w", **pad
        )
        # Row 1: Phone
        ttk.Label(frm, text="Telefon").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.contact_phone, width=25).grid(
            row=1, column=1, columnspan=3, sticky="w", **pad
        )
        # Row 2: Home Address
        ttk.Label(frm, text="Ev Adresi").grid(row=2, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.contact_home, width=50).grid(
            row=2, column=1, columnspan=3, sticky="w", **pad
        )
        # Row 3: Work Address + Button
        ttk.Label(frm, text="İş Adresi").grid(row=3, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.contact_work, width=50).grid(
            row=3, column=1, columnspan=2, sticky="w", **pad
        )
        ttk.Button(frm, text="Kişi Ekle", command=self.add_contact).grid(
            row=3, column=3, sticky="w", **pad
        )
        # Row 4: Listbox
        self.list_contacts = tk.Listbox(frm, height=4, width=70)
        self.list_contacts.grid(row=4, column=0, columnspan=4, sticky="w", **pad)

        row += 1

        # — Action buttons —
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=2, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç",       command=self.clear_all).grid(
            row=row, column=3, sticky="w", **pad
        )

        # F10 to trigger save
        self.bind_all("<F10>", lambda e: self.save())

    def add_contact(self) -> None:
        name = self.contact_name.get().strip()
        if not name:
            return
        phone = self.contact_phone.get().strip()
        home  = self.contact_home.get().strip()
        work  = self.contact_work.get().strip()

        self.contacts.append((name, phone, home, work))
        self.list_contacts.insert(tk.END, f"{name} — {phone}")

        # clear
        for var in (self.contact_name, self.contact_phone, self.contact_home, self.contact_work):
            var.set("")

    def save(self) -> None:
        name = self.var_name.get().strip()
        if not name:
            messagebox.showwarning("Eksik Bilgi", "Adı Soyadı zorunludur.")
            return

        with db.session() as s:
            cust = db.Customer(
                name=name,
                phone=self.var_phone.get().strip(),
                address=self.var_address.get().strip(),
                work_address=self.var_work_address.get().strip(),
                notes=self.var_notes.get().strip(),
            )
            s.add(cust); s.flush()
            for cname, cphone, chome, cwork in self.contacts:
                s.add(db.Contact(
                    customer_id=cust.id,
                    name=cname, phone=cphone,
                    home_address=chome, work_address=cwork,
                ))

        messagebox.showinfo("Başarılı", "Müşteri kaydedildi.")
        self.clear_all()

    def clear_all(self) -> None:
        for var in (self.var_name, self.var_phone,
                    self.var_address, self.var_work_address,
                    self.var_notes):
            var.set("")
        self.contacts.clear()
        self.list_contacts.delete(0, tk.END)
