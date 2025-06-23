# customer_form.py
# Dialog for adding (or later editing) a customer record.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import db


class AddCustomerWindow(tk.Toplevel):
    """Form to create a new customer with optional alternate contacts."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("Yeni Müşteri")
        self.grab_set()            # make window modal
        self.resizable(False, False)

        # ---------------------------------------------------------------- #
        #  Variables                                                      #
        # ---------------------------------------------------------------- #
        self.var_name = tk.StringVar()
        self.var_phone = tk.StringVar()
        self.var_address = tk.StringVar()
        self.var_notes = tk.StringVar()

        # Contacts will be stored as list[tuple[str, str]]
        self.contacts: list[tuple[str, str]] = []

        # ---------------------------------------------------------------- #
        #  Layout                                                          #
        # ---------------------------------------------------------------- #
        pad = {"padx": 8, "pady": 4}
        row = 0

        ttk.Label(self, text="İsim *").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_name, width=40).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Telefon").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.var_phone, width=25).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Adres").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_address, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Label(self, text="Notlar").grid(row=row, column=0, sticky="ne", **pad)
        ttk.Entry(self, textvariable=self.var_notes, width=60).grid(
            row=row, column=1, columnspan=3, sticky="w", **pad
        )
        row += 1

        # --- Alternate contacts ---------------------------------------- #
        ttk.Label(self, text="Ek Kişiler").grid(row=row, column=0, sticky="ne", **pad)

        frm_contacts = ttk.Frame(self)
        frm_contacts.grid(row=row, column=1, columnspan=3, sticky="w", **pad)

        self.contact_name = tk.StringVar()
        self.contact_phone = tk.StringVar()

        ttk.Entry(frm_contacts, textvariable=self.contact_name, width=25).grid(
            row=0, column=0, **pad
        )
        ttk.Entry(frm_contacts, textvariable=self.contact_phone, width=20).grid(
            row=0, column=1, **pad
        )
        ttk.Button(
            frm_contacts, text="Kişi Ekle", command=self.add_contact
        ).grid(row=0, column=2, **pad)

        self.list_contacts = tk.Listbox(frm_contacts, height=4, width=50)
        self.list_contacts.grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        row += 1

        # --- Action buttons -------------------------------------------- #
        ttk.Button(self, text="Kaydet (F10)", command=self.save).grid(
            row=row, column=2, sticky="e", **pad
        )
        ttk.Button(self, text="Vazgeç", command=self.destroy).grid(
            row=row, column=3, sticky="w", **pad
        )

        # Allow F10 to trigger save
        self.bind("<F10>", lambda *_: self.save())

    # ------------------------------------------------------------------ #
    #  Contact handling                                                  #
    # ------------------------------------------------------------------ #
    def add_contact(self) -> None:
        """Add the current contact entry fields to the listbox + memory."""
        name = self.contact_name.get().strip()
        phone = self.contact_phone.get().strip()
        if not name and not phone:
            return
        self.contacts.append((name, phone))
        self.list_contacts.insert(tk.END, f"{name} — {phone}")
        self.contact_name.set("")
        self.contact_phone.set("")

    # ------------------------------------------------------------------ #
    #  Save routine                                                      #
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        """Validate and persist the customer + contacts."""
        name = self.var_name.get().strip()
        if not name:
            messagebox.showwarning("Eksik Bilgi", "İsim zorunludur.")
            return

        with db.session() as s:
            customer = db.Customer(
                name=name,
                phone=self.var_phone.get().strip(),
                address=self.var_address.get().strip(),
                notes=self.var_notes.get().strip(),
            )
            s.add(customer)
            s.flush()  # get generated ID for FK

            for cname, cphone in self.contacts:
                contact = db.Contact(
                    customer_id=customer.id,
                    name=cname,
                    phone=cphone,
                )
                s.add(contact)

        messagebox.showinfo("Başarılı", "Müşteri kaydedildi.")
        self.destroy()
