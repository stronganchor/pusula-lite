# main.py
# Pusula-Lite — single-window, tabbed UI with search, add, sale, and detail
# Repo URL: https://github.com/stronganchor/pusula-lite

import tkinter as tk
from tkinter import ttk

import updater
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
            detail_frame=None  # will wire below
        )
        self.tab_add    = AddCustomerFrame(self.notebook)
        self.tab_sale   = SaleFrame(self.notebook)
        self.tab_detail = CustomerDetailFrame(self.notebook)

        # Wire cross-tab references
        self.tab_search.detail_frame = self.tab_detail
        self.tab_search.add_frame    = self.tab_add
        self.tab_search.sale_frame   = self.tab_sale
        self.tab_add.sale_frame      = self.tab_sale
        self.tab_add.search_frame    = self.tab_search  
        self.tab_sale.search_frame   = self.tab_search 

        # Add tabs in order
        self.notebook.add(self.tab_search, text="Müşteri Arama")
        self.notebook.add(self.tab_add,    text="Müşteri Tanıtım Bilgileri")
        self.notebook.add(self.tab_sale,   text="Satış Kaydet")
        self.notebook.add(self.tab_detail, text="Taksitli Satış Kayıt Bilgisi")

        # Keep Escape to quit
        self.bind_all("<Escape>", lambda e: self.quit())

        # On startup, load detail for last‐selected or newest customer
        self.tab_detail.load_customer()

        # Whenever user switches tabs, refresh search/detail
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Check for updates on startup
        self.after(500, lambda: updater.check_and_update(self))

    def on_tab_changed(self, event) -> None:
        """Refresh the search list or detail view when its tab is selected."""
        current = self.notebook.nametowidget(self.notebook.select())
        if current is self.tab_search:
            self.tab_search._load_all()
        elif current is self.tab_detail:
            self.tab_detail.load_customer()


if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
