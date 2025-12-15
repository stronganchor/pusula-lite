# customer_form.py
# “Müşteri Tanıtım Bilgileri” tab, for both new and existing customers,
# now switches to sale tab after saving.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from sqlalchemy import func

import db


class AddCustomerFrame(ttk.Frame):
    """“Müşteri Tanıtım Bilgileri” tab, for both new and existing customers."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)

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

        # Layout: scrollable form so buttons stay reachable on small screens
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        style = ttk.Style(self)
        # Button styles with a clearer focus outline
        style.configure("Form.TButton", padding=(10, 6))
        style.configure("FormFocus.TButton", padding=(10, 6), relief="solid", borderwidth=2)
        bg = style.lookup("TFrame", "background")
        if not bg:
            try:
                bg = self.winfo_toplevel().cget("background")
            except Exception:
                bg = "#0f141e"

        self._canvas = tk.Canvas(
            container,
            highlightthickness=0,
            background=bg,
        )
        vscroll = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vscroll.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")

        self._form = ttk.Frame(self._canvas, padding=8)
        self._form_window = self._canvas.create_window((0, 0), window=self._form, anchor="nw")
        self._form.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(
                self._form_window,
                width=e.width,
                height=max(self._form.winfo_reqheight(), e.height),
            ),
        )
        self._form.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+"))
        self._form.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

        pad = {"padx": 8}
        field_gap = (0, 12)
        first_field_gap = (12, 12)

        self._form.columnconfigure(0, weight=1)
        self._form.columnconfigure(1, weight=1)
        self._form.rowconfigure(2, weight=1)
        self._form.rowconfigure(3, weight=1)

        # --- Müşteri No + Kayıt Tarihi (spans both columns) ---
        header = ttk.Frame(self._form)
        header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ttk.Label(header, text="Müşteri No:").grid(row=0, column=0, sticky="e", **pad)
        entry_id = ttk.Entry(header, textvariable=self.var_id, width=10)
        entry_id.grid(row=0, column=1, sticky="w", **pad)
        entry_id.bind("<FocusOut>", lambda e: self.load_customer())

        ttk.Label(header, text="Kayıt Tarihi:").grid(row=0, column=2, sticky="e", **pad)
        ttk.Label(header, textvariable=self.var_reg_date).grid(
            row=0, column=3, sticky="w", **pad
        )

        ttk.Separator(self._form, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=pad["padx"], pady=(4, 14)
        )

        # --- Left column: primary info ---
        left = ttk.Frame(self._form)
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(1, weight=1)
        row_left = 0

        ttk.Label(left, text="Adı Soyadı *").grid(row=row_left, column=0, sticky="e", pady=first_field_gap, padx=pad["padx"])
        ttk.Entry(left, textvariable=self.var_name, width=40).grid(
            row=row_left, column=1, sticky="ew", pady=first_field_gap, padx=pad["padx"]
        )
        row_left += 1

        ttk.Label(left, text="Telefon").grid(row=row_left, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(left, textvariable=self.var_phone, width=25).grid(
            row=row_left, column=1, sticky="w", pady=field_gap, padx=pad["padx"]
        )
        row_left += 1

        ttk.Label(left, text="Ev Adresi").grid(row=row_left, column=0, sticky="ne", pady=field_gap, padx=pad["padx"])
        ttk.Entry(left, textvariable=self.var_address, width=60).grid(
            row=row_left, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_left += 1

        ttk.Label(left, text="İş Adresi").grid(row=row_left, column=0, sticky="ne", pady=field_gap, padx=pad["padx"])
        ttk.Entry(left, textvariable=self.var_work_address, width=60).grid(
            row=row_left, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_left += 1

        ttk.Label(left, text="Notlar").grid(row=row_left, column=0, sticky="ne", pady=field_gap, padx=pad["padx"])
        left.rowconfigure(row_left, weight=1)
        self._notes_text = tk.Text(left, height=8, wrap="word")
        self._notes_text.grid(
            row=row_left, column=1, sticky="nsew", pady=field_gap, padx=pad["padx"]
        )
        self._notes_text.bind("<Tab>", lambda e: self._focus_next_widget(self._notes_text))
        self._notes_text.bind("<Shift-Tab>", lambda e: self._focus_next_widget(self._notes_text, reverse=True))

        # --- Right column: Ek Kişi sections ---
        right = ttk.Frame(self._form)
        right.grid(row=2, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)
        row_right = 0

        ttk.Label(right, text="Ek Kişi 1").grid(row=row_right, column=0, columnspan=2, sticky="w", pady=first_field_gap, padx=pad["padx"])
        row_right += 1
        ttk.Label(right, text="Adı Soyadı").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c1_name, width=30).grid(
            row=row_right, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1
        ttk.Label(right, text="Telefon").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c1_phone, width=25).grid(
            row=row_right, column=1, sticky="w", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1
        ttk.Label(right, text="Ev Adresi").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c1_home, width=60).grid(
            row=row_right, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1
        ttk.Label(right, text="İş Adresi").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c1_work, width=60).grid(
            row=row_right, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1

        ttk.Label(right, text="Ek Kişi 2").grid(row=row_right, column=0, columnspan=2, sticky="w", pady=first_field_gap, padx=pad["padx"])
        row_right += 1
        ttk.Label(right, text="Adı Soyadı").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c2_name, width=30).grid(
            row=row_right, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1
        ttk.Label(right, text="Telefon").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c2_phone, width=25).grid(
            row=row_right, column=1, sticky="w", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1
        ttk.Label(right, text="Ev Adresi").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c2_home, width=60).grid(
            row=row_right, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )
        row_right += 1
        ttk.Label(right, text="İş Adresi").grid(row=row_right, column=0, sticky="e", pady=field_gap, padx=pad["padx"])
        ttk.Entry(right, textvariable=self.c2_work, width=60).grid(
            row=row_right, column=1, sticky="ew", pady=field_gap, padx=pad["padx"]
        )

        # Spacer to push buttons down when there is extra room
        ttk.Frame(self._form).grid(row=3, column=0, columnspan=2, sticky="nsew")

        # --- Action buttons ---
        buttons = ttk.Frame(self._form)
        buttons.grid(row=4, column=0, columnspan=2, sticky="se", padx=pad["padx"], pady=(16, 8))
        self.save_btn = ttk.Button(buttons, text="Kaydet (F10)", command=self.save, style="Form.TButton", takefocus=True)
        self.save_btn.grid(row=0, column=0, sticky="e", padx=(0, 8))
        self.cancel_btn = ttk.Button(buttons, text="Vazgeç", command=self.cancel, style="Form.TButton", takefocus=True)
        self.cancel_btn.grid(row=0, column=1, sticky="w")
        for btn in (self.save_btn, self.cancel_btn):
            btn.bind("<FocusIn>", lambda e, b=btn: b.configure(style="FormFocus.TButton"))
            btn.bind("<FocusOut>", lambda e, b=btn: b.configure(style="Form.TButton"))
            self._activate_on_enter(btn)
        self.bind_all("<F10>", self._on_f10, add="+")

        # Initialize as “new customer”
        self._new_customer_defaults()

    def _set_notes_text(self, value: str) -> None:
        """Sync the notes text widget and backing var."""
        self.var_notes.set(value or "")
        self._notes_text.delete("1.0", "end")
        if value:
            self._notes_text.insert("1.0", value)

    def _get_notes_text(self) -> str:
        """Return trimmed notes from text widget and update backing var."""
        val = self._notes_text.get("1.0", "end").strip()
        self.var_notes.set(val)
        return val

    def _focus_next_widget(self, widget: tk.Widget, reverse: bool = False) -> str:
        """Move focus forward/backward instead of inserting tabs in text widgets."""
        next_widget = widget.tk_focusPrev() if reverse else widget.tk_focusNext()
        if next_widget:
            next_widget.focus_set()
        return "break"

    def _activate_on_enter(self, button: ttk.Button) -> None:
        """Bind Enter to invoke button (space already works by default)."""
        def _activate(_: tk.Event) -> str:
            button.invoke()
            return "break"
        button.bind("<Return>", _activate, add="+")

    def _new_customer_defaults(self) -> None:
        """Set the next free ID and today’s date as defaults."""
        with db.session() as s:
            last = s.query(func.max(db.Customer.id)).scalar() or 0
        self._default_id   = str(last + 1)
        self._default_date = date.today().strftime("%Y-%m-%d")

        self.var_id.set(self._default_id)
        self.var_reg_date.set(self._default_date)
        self._set_notes_text("")

    def load_customer(self) -> None:
        """Load an existing customer when you tab away from Müşteri No."""
        raw = self.var_id.get().strip()

        # Skip lookup if still the untouched default and no edits
        if raw == getattr(self, "_default_id", None) and not self.var_name.get().strip():
            return
        if not raw.isdigit():
            return

        cid = int(raw)
        with db.session() as s:
            cust = s.get(db.Customer, cid)
            if not cust:
                messagebox.showwarning("Bulunamadı", f"{cid} numaralı müşteri yok.")
                return

            # Populate header + main fields
            self.var_reg_date.set(cust.registration_date.strftime("%Y-%m-%d"))
            self.var_name.set(cust.name or "")
            self.var_phone.set(cust.phone or "")
            self.var_address.set(cust.address or "")
            self.var_work_address.set(cust.work_address or "")
            self._set_notes_text(cust.notes or "")

            # Load up to two existing contacts
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
        """Insert a new customer or update an existing one, then switch to sale tab."""
        name = self.var_name.get().strip()
        if not name:
            messagebox.showwarning("Eksik Bilgi", "Adı Soyadı zorunludur.")
            return

        raw = self.var_id.get().strip()
        cid = int(raw) if raw.isdigit() else None

        with db.session() as s:
            cust = s.get(db.Customer, cid) if cid else None

            if cust:
                # Update existing
                cust.name           = name
                cust.phone          = self.var_phone.get().strip()
                cust.address        = self.var_address.get().strip()
                cust.work_address   = self.var_work_address.get().strip()
                cust.notes          = self._get_notes_text()
            else:
                # Create new record
                today = date.today()
                cust = db.Customer(
                    id=cid,
                    name=name,
                    phone=self.var_phone.get().strip(),
                    address=self.var_address.get().strip(),
                    work_address=self.var_work_address.get().strip(),
                    notes=self._get_notes_text(),
                    registration_date=today,
                )
                s.add(cust)
                s.flush()
                cid = cust.id
                self.var_id.set(str(cid))
                self.var_reg_date.set(cust.registration_date.strftime("%Y-%m-%d"))

            # Replace both contacts
            s.query(db.Contact).filter_by(customer_id=cid).delete()
            for vars in [
                (self.c1_name, self.c1_phone, self.c1_home, self.c1_work),
                (self.c2_name, self.c2_phone, self.c2_home, self.c2_work),
            ]:
                nm, ph, hm, wk = (v.get().strip() for v in vars)
                if nm or ph or hm or wk:
                    s.add(db.Contact(
                        customer_id=cid,
                        name=nm,
                        phone=ph,
                        home_address=hm,
                        work_address=wk,
                    ))

        # ** New: after saving, switch to Satış Kaydet tab with this customer **
        self.sale_frame.select_customer(cid)
        self.master.select(self.sale_frame)

        # Reset for next entry
        self.clear_all()

    def clear_all(self) -> None:
        """Reset all fields and restore defaults for a new customer."""
        for var in [
            self.var_id, self.var_reg_date,
            self.var_name, self.var_phone,
            self.var_address, self.var_work_address,
            self.var_notes,
            self.c1_name, self.c1_phone, self.c1_home, self.c1_work,
            self.c2_name, self.c2_phone, self.c2_home, self.c2_work,
        ]:
            var.set("")
        self._set_notes_text("")
        self._new_customer_defaults()
        
    def cancel(self) -> None:
        """Cancel and return to customer search tab."""
        self.clear_all()
        self.master.select(self.search_frame)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Scroll the form when the mouse wheel moves."""
        delta = -1 * int(event.delta / 120)
        self._canvas.yview_scroll(delta, "units")

    def _on_f10(self, event: tk.Event) -> str | None:
        """Fire save only when this tab is active."""
        if self.master.select() != str(self):
            return None
        self.save()
        return "break"
