# main.py
# Pusula-Lite — single-store instalment-sales app
# Windows UI version (Tkinter) — now single window with tabs

import tkinter as tk
from tkinter import ttk, messagebox

import db
from customer_form import AddCustomerFrame
from customer_search import CustomerSearchFrame
from sale_form import SaleFrame


class PusulaLiteApp(tk.Tk):
    """Root window with three tabs instead of pop-ups."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Pusula Lite")
        self.geometry("800x600")
        self.minsize(640, 480)

        # Create / migrate database
        db.init_db()

        # Notebook (tabs)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Instantiate each form as a Frame
        self.tab_search = CustomerSearchFrame(notebook)
        self.tab_add    = AddCustomerFrame(notebook)
        self.tab_sale   = SaleFrame(notebook)

        notebook.add(self.tab_search, text="Müşteri Arama (F1)")
        notebook.add(self.tab_add,    text="Yeni Müşteri (F2)")
        notebook.add(self.tab_sale,   text="Satış Kaydet (F3)")

        # Global key bindings to switch tabs
        self.bind_all("<F1>", lambda e: notebook.select(self.tab_search))
        self.bind_all("<F2>", lambda e: notebook.select(self.tab_add))
        self.bind_all("<F3>", lambda e: notebook.select(self.tab_sale))
        self.bind_all("<Escape>", lambda e: self.quit())


if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
