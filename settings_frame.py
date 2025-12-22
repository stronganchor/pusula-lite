"""Settings tab for configuring the WordPress API URL and key."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import remote_api


class SettingsFrame(ttk.Frame):
    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master, padding=12)

        self.var_url = tk.StringVar()
        self.var_key = tk.StringVar()

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="API URL").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Entry(self, textvariable=self.var_url).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(self, text="API Anahtarı").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Entry(self, textvariable=self.var_key, show="*").grid(row=1, column=1, sticky="ew", pady=4)

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Kaydet", command=self.save).pack(side="right", padx=4)
        ttk.Button(btns, text="Bağlantıyı Test Et", command=self.test_connection).pack(side="right", padx=4)

        self.load()

    def load(self) -> None:
        settings = remote_api.load_settings()
        self.var_url.set(settings.get("base_url", ""))
        self.var_key.set(settings.get("api_key", ""))

    def save(self) -> None:
        url = self.var_url.get().strip()
        key = self.var_key.get().strip()
        if not url or not key:
            messagebox.showwarning("Eksik Bilgi", "API URL ve Anahtar gereklidir.")
            return
        remote_api.save_settings(url, key)
        messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi.")

    def test_connection(self) -> None:
        try:
            self.save()
            remote_api.test_connection()
            messagebox.showinfo("Başarılı", "API bağlantısı başarılı.")
        except remote_api.ApiError as e:
            messagebox.showerror("Bağlantı Hatası", f"{e.status}: {e.message}")
