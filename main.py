# main.py
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

        # Ensure DB exists
        db.init_db()

        # Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # Instantiate each tab
        self.tab_search = CustomerSearchFrame(
            self.notebook,
            notebook=self.notebook,
            detail_frame=None  # placeholder, will set after detail instantiation
        )
        self.tab_add    = AddCustomerFrame(self.notebook)
        self.tab_sale   = SaleFrame(self.notebook)
        self.tab_detail = CustomerDetailFrame(self.notebook)

        # Now wire the search tab to the detail tab
        self.tab_search.detail_frame = self.tab_detail

        # Add them in order
        self.notebook.add(self.tab_search, text="Müşteri Arama (F1)")
        self.notebook.add(self.tab_add,    text="Müşteri Tanıtım Bilgileri (F2)")
        self.notebook.add(self.tab_sale,   text="Satış Kaydet (F3)")
        self.notebook.add(self.tab_detail, text="Taksitli Satış Kayıt Bilgisi")

        # Key bindings
        self.bind_all("<F1>", lambda e: self.notebook.select(self.tab_search))
        self.bind_all("<F2>", lambda e: self.notebook.select(self.tab_add))
        self.bind_all("<F3>", lambda e: self.notebook.select(self.tab_sale))
        self.bind_all("<Escape>", lambda e: self.quit())

        # Load the detail tab on the last or most recent customer
        self.tab_detail.load_customer()


if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
