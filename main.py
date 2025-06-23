# main.py
# Pusula-Lite — single-store instalment-sales app
# Windows UI version (Tkinter)

import tkinter as tk
from tkinter import ttk, messagebox
import db  # local module that handles SQLite schema + migrations


class PusulaLiteApp(tk.Tk):
    """Root window that wires the whole program together."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Pusula Lite  ▸  F1:Arama  F2:Ekle  F3:Satış  Esc:Çıkış")
        self.geometry("800x600")
        self.minsize(640, 480)

        # Fill the grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Create / migrate database
        db.init_db()

        # Home-screen instructions (Turkish)
        info = (
            "F1   Müşteri Arama\n"
            "F2   Yeni Müşteri Ekle\n"
            "F3   Satış Kaydet\n"
            "Esc  Çıkış"
        )
        ttk.Label(
            self,
            text=info,
            justify="center",
            font=("Segoe UI", 16, "bold"),
        ).grid(sticky="nsew")

        # Global key bindings
        self.bind_all("<F1>", self.open_customer_search)
        self.bind_all("<F2>", self.open_add_customer)
        self.bind_all("<F3>", self.open_record_sale)
        self.bind_all("<Escape>", lambda _: self.quit())

    # ------------------------------------------------------------------ #
    #  Window launchers                                                   #
    # ------------------------------------------------------------------ #

    def open_customer_search(self, _=None) -> None:
        """Launch searchable customer list (F1)."""
        try:
            from customer_search import CustomerSearchWindow
            CustomerSearchWindow(self)
        except ImportError:
            messagebox.showinfo(
                "Eksik Modül",
                "customer_search.py dosyası bulunamadı."
            )

    def open_add_customer(self, _=None) -> None:
        """Launch 'add customer' dialog (F2)."""
        try:
            from customer_form import AddCustomerWindow
            AddCustomerWindow(self)
        except ImportError:
            messagebox.showinfo(
                "Eksik Modül",
                "customer_form.py dosyası bulunamadı."
            )

    def open_record_sale(self, _=None) -> None:
        """Launch sale-entry screen for a selected customer (F3)."""
        try:
            from sale_form import SaleWindow
            SaleWindow(self)
        except ImportError:
            messagebox.showinfo(
                "Eksik Modül",
                "sale_form.py dosyası bulunamadı."
            )


# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
