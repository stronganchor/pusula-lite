# main.py
# Pusula-Lite — single-window, tabbed UI with search, add, sale, and detail

import tkinter as tk
from tkinter import ttk

import db
import app_state
from customer_form import AddCustomerFrame
from customer_search import CustomerSearchFrame
from sale_form import SaleFrame
from customer_detail import CustomerDetailFrame

class PusulaLiteApp(tk.Tk):
    """Root window with four always-available tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Pusula Lite")
        self.geometry("800x600")
        self.minsize(640, 480)

        # Ensure database and tables exist
        db.init_db()

        # Notebook container
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # Instantiate each tab frame
        self.tab_search = CustomerSearchFrame(
            self.notebook,
            notebook=self.notebook,
            detail_frame=None  # will be wired below
        )
        self.tab_add    = AddCustomerFrame(self.notebook)
        self.tab_sale   = SaleFrame(self.notebook)
        self.tab_detail = CustomerDetailFrame(self.notebook)

        # Wire cross-tab references
        self.tab_search.detail_frame = self.tab_detail
        self.tab_add.sale_frame      = self.tab_sale

        # Add tabs in order
        self.notebook.add(self.tab_search, text="Müşteri Arama (F1)")
        self.notebook.add(self.tab_add,    text="Müşteri Tanıtım Bilgileri (F2)")
        self.notebook.add(self.tab_sale,   text="Satış Kaydet (F3)")
        self.notebook.add(self.tab_detail, text="Taksitli Satış Kayıt Bilgisi")

        # REMOVE: F1/F2/F3 shortcuts for now
        # self.bind_all("<F1>", lambda e: self.notebook.select(self.tab_search))
        # self.bind_all("<F2>", lambda e: self.notebook.select(self.tab_add))
        # self.bind_all("<F3>", lambda e: self.notebook.select(self.tab_sale))
        # Keep Escape to quit
        self.bind_all("<Escape>", lambda e: self.quit())

        # On startup, load detail for last‐selected or newest customer
        self.tab_detail.load_customer()


if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
