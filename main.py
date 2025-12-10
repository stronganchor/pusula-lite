# main.py
# Pusula-Lite — single-window, tabbed UI with search, add, sale, and detail
# Repo URL: https://github.com/stronganchor/pusula-lite

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import sys
import ctypes

import updater
import db
import app_state
from customer_form import AddCustomerFrame
from customer_search import CustomerSearchFrame
from sale_form import SaleFrame
from customer_detail import CustomerDetailFrame
from daily_sales_report import DailySalesReportFrame

class PusulaLiteApp(tk.Tk):
    """Root window with four always-available tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Pusula Lite")
        self.geometry("800x600")
        self.state('zoomed')
        self.minsize(640, 480)

        # Global fonts + theme
        self._configure_fonts()
        self._apply_dark_theme()
        self.after(0, self._set_dark_titlebar)

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
        self.tab_report = DailySalesReportFrame(self.notebook)
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
        self.notebook.add(self.tab_report, text="Günlük Satış Raporu")

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

    def _configure_fonts(self) -> None:
        """Raise default font sizes for readability."""
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(size=13)
        self.option_add("*Font", base)

        tkfont.nametofont("TkTextFont").configure(size=13)
        tkfont.nametofont("TkFixedFont").configure(size=13)
        tkfont.nametofont("TkHeadingFont").configure(size=15, weight="bold")

    def _apply_dark_theme(self) -> None:
        """Apply a dark palette and ttk styling across the app."""
        colors = {
            "bg": "#0f141e",
            "surface": "#181f2c",
            "panel": "#1f2838",
            "panel_hover": "#283345",
            "border": "#2f3a4f",
            "fg": "#e6ecf3",
            "muted": "#c0cad8",
            "accent": "#88b7c9",       # soft teal-blue to reduce eye strain
            "accent_soft": "#577487",  # muted accent for selections
            "accent_warm": "#f0d7a7",  # gentle highlight for preview values
        }

        self.configure(bg=colors["bg"])
        self.tk_setPalette(
            background=colors["bg"],
            foreground=colors["fg"],
            activeBackground=colors["accent"],
            activeForeground=colors["bg"],
            highlightColor=colors["accent"],
            selectColor=colors["accent"],
            selectBackground=colors["accent_soft"],
            selectForeground=colors["bg"],
        )
        self.option_add("*Background", colors["bg"])
        self.option_add("*Foreground", colors["fg"])
        self.option_add("*Entry.Background", colors["surface"])
        self.option_add("*Entry.Foreground", colors["fg"])
        self.option_add("*Text.background", colors["surface"])
        self.option_add("*Text.foreground", colors["fg"])
        self.option_add("*Text.insertBackground", colors["accent"])
        self.option_add("*Text.selectBackground", colors["accent_soft"])
        self.option_add("*TCombobox*Listbox*background", colors["surface"])
        self.option_add("*TCombobox*Listbox*foreground", colors["fg"])
        self.option_add("*TCombobox*Listbox*selectBackground", colors["accent_soft"])
        self.option_add("*TCombobox*Listbox*selectForeground", colors["bg"])

        style = ttk.Style(self)
        style.theme_use("clam")

        heading_font = tkfont.nametofont("TkHeadingFont")

        style.configure(".", background=colors["bg"], foreground=colors["fg"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabelframe", background=colors["bg"], foreground=colors["muted"], bordercolor=colors["border"])
        style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["muted"], font=heading_font)
        style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        style.configure(
            "TEntry",
            fieldbackground=colors["surface"],
            foreground=colors["fg"],
            bordercolor=colors["border"],
            lightcolor=colors["accent"],
            darkcolor=colors["border"],
            insertcolor=colors["fg"],
            padding=6,
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", colors["panel"])],
            foreground=[("disabled", colors["muted"])],
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["surface"],
            background=colors["surface"],
            foreground=colors["fg"],
            bordercolor=colors["border"],
            lightcolor=colors["accent"],
            darkcolor=colors["border"],
            arrowcolor=colors["fg"],
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[
                ("pressed", colors["surface"]),
                ("active", colors["surface"]),
                ("readonly", colors["surface"]),
                ("!disabled", colors["surface"]),
            ],
            background=[
                ("pressed", colors["surface"]),
                ("active", colors["surface"]),
                ("readonly", colors["surface"]),
                ("!disabled", colors["surface"]),
            ],
            foreground=[
                ("disabled", colors["muted"]),
                ("readonly", colors["fg"]),
            ],
            arrowcolor=[
                ("disabled", colors["muted"]),
                ("pressed", colors["fg"]),
                ("active", colors["fg"]),
                ("readonly", colors["fg"]),
                ("!disabled", colors["fg"]),
            ],
        )

        style.configure(
            "TButton",
            background=colors["panel"],
            foreground=colors["fg"],
            padding=(12, 8),
            bordercolor=colors["border"],
            focusthickness=2,
            focuscolor=colors["accent"],
        )
        style.map(
            "TButton",
            background=[
                ("active", colors["accent"]),
                ("pressed", colors["accent"]),
                ("disabled", colors["panel"]),
            ],
            foreground=[
                ("active", colors["bg"]),
                ("pressed", colors["bg"]),
                ("disabled", colors["muted"]),
            ],
        )

        style.configure("TNotebook", background=colors["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=colors["panel"],
            foreground=colors["muted"],
            padding=(16, 12),
            borderwidth=0,
            font=heading_font,
        )
        style.map(
            "TNotebook.Tab",
            padding=[
                ("selected", (16, 12)),
                ("active", (16, 12)),
            ],
            background=[
                ("selected", colors["surface"]),
                ("active", colors["panel_hover"]),
            ],
            foreground=[("selected", colors["fg"])],
        )

        style.configure(
            "Treeview",
            background=colors["surface"],
            fieldbackground=colors["surface"],
            foreground=colors["fg"],
            bordercolor=colors["border"],
            rowheight=28,
        )
        style.map(
            "Treeview",
            background=[("selected", colors["accent_soft"])],
            foreground=[("selected", colors["bg"])],
            bordercolor=[("selected", colors["accent"])],
        )
        style.configure(
            "Treeview.Heading",
            background=colors["panel"],
            foreground=colors["fg"],
            bordercolor=colors["border"],
            relief="flat",
            font=heading_font,
        )
        style.map(
            "Treeview.Heading",
            background=[("active", colors["panel_hover"])],
            foreground=[("active", colors["fg"])],
        )

        style.configure(
            "TProgressbar",
            troughcolor=colors["panel"],
            bordercolor=colors["border"],
            background=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
        )
        style.configure("TScrollbar", troughcolor=colors["panel"], bordercolor=colors["border"], background=colors["panel"])
        style.map("TScrollbar", background=[("active", colors["accent"])], arrowcolor=[("active", colors["bg"])])
        style.configure("TSeparator", background=colors["border"])
        style.configure(
            "PreviewValue.TLabel",
            background=colors["bg"],
            foreground=colors["accent_warm"],
        )

    def _set_dark_titlebar(self) -> None:
        """On Windows, request a dark title bar to match the theme."""
        if sys.platform != "win32":
            return
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            applied = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if applied != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd),
                    19,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception:
            # If the platform does not support dark title bars, ignore.
            pass

if __name__ == "__main__":
    app = PusulaLiteApp()
    app.mainloop()
