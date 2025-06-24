# main.py
import tkinter as tk
from tkinter import ttk, messagebox

import db
from customer_form import AddCustomerFrame
from customer_search import CustomerSearchFrame
from sale_form import SaleFrame
from customer_detail import CustomerDetailFrame

class PusulaLiteApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pusula Lite")
        self.geometry("800x600")
        self.minsize(640, 480)

        db.init_db()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab_search = CustomerSearchFrame(self.notebook, notebook=self.notebook)
        self.tab_add    = AddCustomerFrame(  self.notebook)
        self.tab_sale   = SaleFrame(         self.notebook)

        self.notebook.add(self.tab_search, text="Müşteri Arama (F1)")
        self.notebook.add(self.tab_add,    text="Müşteri Tanıtım Bilgileri (F2)")
        self.notebook.add(self.tab_sale,   text="Satış Kaydet (F3)")

        self.bind_all("<F1>", lambda e: self.notebook.select(self.tab_search))
        self.bind_all("<F2>", lambda e: self.notebook.select(self.tab_add))
        self.bind_all("<F3>", lambda e: self.notebook.select(self.tab_sale))
        self.bind_all("<Escape>", lambda e: self.quit())


if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
