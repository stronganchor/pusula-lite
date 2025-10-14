# updater.py
# Automatic update checker and installer with Turkish UI

import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

class UpdateDialog(tk.Toplevel):
    """Turkish progress dialog for updates."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Güncelleme")
        self.geometry("400x150")
        self.resizable(False, False)

        # Center on screen
        self.transient(parent)
        self.grab_set()

        # Status label
        self.status_label = ttk.Label(
            self,
            text="Güncelleme kontrol ediliyor...",
            font=("", 10)
        )
        self.status_label.pack(pady=20)

        # Progress bar
        self.progress = ttk.Progressbar(
            self,
            mode='indeterminate',
            length=350
        )
        self.progress.pack(pady=10)
        self.progress.start(10)

        # Detail label
        self.detail_label = ttk.Label(self, text="", font=("", 8))
        self.detail_label.pack(pady=5)

        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Disable close

    def update_status(self, message, detail=""):
        """Update the status message."""
        self.status_label.config(text=message)
        self.detail_label.config(text=detail)
        self.update()

    def finish(self, success=True, message=""):
        """Finish the update process."""
        self.progress.stop()
        if success:
            self.progress.config(mode='determinate', value=100)
        self.update_status(message)
        self.after(2000, self.destroy)


def run_command(cmd, cwd=None):
    """Run a command without showing console window."""
    startupinfo = None
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def get_current_branch():
    """Get the current Git branch name."""
    repo_dir = Path(__file__).parent
    success, stdout, stderr = run_command(
        ["git", "branch", "--show-current"],
        cwd=repo_dir
    )
    if success and stdout.strip():
        return stdout.strip()
    return None


def check_for_updates():
    """Check if updates are available from Git."""
    repo_dir = Path(__file__).parent

    try:
        # Get current branch
        branch = get_current_branch()
        if not branch:
            # Fallback: try to get branch from git status
            success, stdout, stderr = run_command(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_dir
            )
            if success and stdout.strip():
                branch = stdout.strip()
            else:
                branch = "main"  # default fallback

        # Fetch latest from remote
        success, stdout, stderr = run_command(
            ["git", "fetch", "origin", branch],
            cwd=repo_dir
        )

        if not success:
            return False, f"Git fetch başarısız: {stderr[:50]}"

        # Check if local is behind remote
        success, stdout, stderr = run_command(
            ["git", "rev-list", f"HEAD..origin/{branch}", "--count"],
            cwd=repo_dir
        )

        if success and stdout.strip() and int(stdout.strip()) > 0:
            return True, f"{stdout.strip()} güncelleme mevcut"

        return False, "Güncelleme yok"

    except Exception as e:
        return False, f"Hata: {str(e)}"

def perform_update(dialog):
    """Perform the actual update."""
    repo_dir = Path(__file__).parent

    # Get current branch
    branch = get_current_branch()
    if not branch:
        success, stdout, stderr = run_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_dir
        )
        if success and stdout.strip():
            branch = stdout.strip()
        else:
            branch = "main"

    # Step 1: Git pull with explicit remote and branch
    dialog.update_status("Güncellemeler indiriliyor...", "Git pull çalışıyor")
    success, stdout, stderr = run_command(
        ["git", "pull", "origin", branch, "--ff-only"],
        cwd=repo_dir
    )

    if not success:
        # If ff-only fails, try regular pull
        success, stdout, stderr = run_command(
            ["git", "pull", "origin", branch],
            cwd=repo_dir
        )

        if not success:
            dialog.finish(False, f"Git pull başarısız: {stderr[:100]}")
            return False

    # Step 2: Update Python packages if requirements.txt exists
    req_file = repo_dir / "requirements.txt"
    if req_file.exists():
        dialog.update_status("Python paketleri güncelleniyor...", "pip install çalışıyor")
        success, stdout, stderr = run_command(
            [sys.executable, "-m", "pip", "install", "--upgrade", "-r", "requirements.txt"],
            cwd=repo_dir
        )

        if not success:
            dialog.finish(False, f"Paket güncellemesi başarısız: {stderr[:100]}")
            return False

    dialog.finish(True, "Güncelleme tamamlandı! Uygulama yeniden başlatılacak.")
    return True

def check_and_update(parent_window):
    """Check for updates and prompt user to install."""

    try:
        # Check if Git is available
        success, _, _ = run_command(["git", "--version"])
        if not success:
            return  # Silently skip if Git is not installed

        # Check for updates
        has_updates, message = check_for_updates()

        if not has_updates:
            return  # No updates, continue normally

        # Ask user if they want to update
        response = messagebox.askyesno(
            "Güncelleme Mevcut",
            f"{message}\n\nŞimdi güncellemek ister misiniz?",
            parent=parent_window
        )

        if not response:
            return  # User declined

        # Show progress dialog
        dialog = UpdateDialog(parent_window)

        def update_thread():
            success = perform_update(dialog)
            if success:
                parent_window.after(2500, lambda: restart_application(parent_window))

        threading.Thread(target=update_thread, daemon=True).start()

        # Wait for dialog to close
        parent_window.wait_window(dialog)

    except Exception as e:
        # Show any errors that occur
        messagebox.showerror(
            "Güncelleme Hatası",
            f"Güncelleme kontrolü sırasında hata oluştu:\n\n{str(e)}",
            parent=parent_window
        )

def update_thread():
    success = perform_update(dialog)
    if success:
        parent_window.after(2500, lambda: restart_application(parent_window))

    threading.Thread(target=update_thread, daemon=True).start()

    # Wait for dialog to close
    parent_window.wait_window(dialog)


def restart_application(parent_window):
    """Restart the application after update."""
    response = messagebox.askyesno(
        "Yeniden Başlat",
        "Güncellemeler uygulandı. Uygulamayı şimdi yeniden başlatmak ister misiniz?",
        parent=parent_window
    )

    if response:
        python = sys.executable
        script = Path(__file__).parent / "main.py"
        subprocess.Popen([python, str(script)])
        parent_window.quit()
