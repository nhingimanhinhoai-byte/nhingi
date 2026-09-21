"""Offline personal license manager desktop application.

Run with: python license_manager.py
All records are stored locally in ~/LicenseManager/license_manager.db.
"""

from __future__ import annotations

import json
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_DIR = Path.home() / "LicenseManager"
DB_PATH = APP_DIR / "license_manager.db"
DATE_FORMAT = "%Y-%m-%d"


class LicenseStore:
    """Small SQLite-backed repository used by the desktop interface."""

    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT NOT NULL,
                broker TEXT NOT NULL,
                start_date TEXT NOT NULL,
                days INTEGER NOT NULL,
                expiry_date TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def add(self, account: str, broker: str, start_date: str, days: int, note: str) -> int:
        expiry = (datetime.strptime(start_date, DATE_FORMAT).date() + timedelta(days=days)).isoformat()
        cursor = self.connection.execute(
            "INSERT INTO licenses (account, broker, start_date, days, expiry_date, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account, broker, start_date, days, expiry, note, datetime.now().isoformat(timespec="seconds")),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def summary(self) -> tuple[int, int, int]:
        row = self.connection.execute(
            "SELECT COUNT(DISTINCT account || char(31) || broker), COUNT(*), COALESCE(SUM(days), 0) FROM licenses"
        ).fetchone()
        return tuple(row)  # type: ignore[return-value]

    def customers(self, query: str = "") -> list[sqlite3.Row]:
        needle = f"%{query.strip()}%"
        return self.connection.execute(
            """SELECT account, broker, COUNT(*) AS grants, MAX(start_date) AS latest_start,
                      (SELECT expiry_date FROM licenses x WHERE x.account = l.account AND x.broker = l.broker
                       ORDER BY x.start_date DESC, x.id DESC LIMIT 1) AS current_expiry
               FROM licenses l
               WHERE account LIKE ? OR broker LIKE ?
               GROUP BY account, broker ORDER BY latest_start DESC""",
            (needle, needle),
        ).fetchall()

    def history(self, account: str, broker: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM licenses WHERE account = ? AND broker = ? ORDER BY start_date DESC, id DESC", (account, broker)
        ).fetchall()

    def backup_to(self, destination: Path) -> None:
        rows = [dict(row) for row in self.connection.execute("SELECT * FROM licenses ORDER BY id")]
        destination.write_text(json.dumps({"app": "License Manager", "records": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    def restore_from(self, source: Path) -> int:
        payload = json.loads(source.read_text(encoding="utf-8"))
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError("Tệp backup không đúng định dạng.")
        with self.connection:
            self.connection.execute("DELETE FROM licenses")
            for record in records:
                self.connection.execute(
                    "INSERT INTO licenses (account, broker, start_date, days, expiry_date, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (record["account"], record["broker"], record["start_date"], int(record["days"]), record["expiry_date"], record.get("note", ""), record.get("created_at", datetime.now().isoformat())),
                )
        return len(records)


def mql_license(account: str, broker: str, start_date: str, days: int) -> str:
    formatted = datetime.strptime(start_date, DATE_FORMAT).strftime("%Y.%m.%d")
    safe_broker = broker.replace('"', '\\"')
    return f'''#define LICENSE_ACCOUNT {account}
#define LICENSE_BROKER  "{safe_broker}"
#define LICENSE_START   D'{formatted} 00:00:00'
#define LICENSE_DAYS    {days}'''


def license_status(expiry_date: str) -> str:
    remaining = (datetime.strptime(expiry_date, DATE_FORMAT).date() - date.today()).days
    if remaining < 0:
        return "Hết hạn"
    if remaining <= 7:
        return "Sắp hết hạn"
    return "Đang hoạt động"


class LicenseManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("License Manager — Offline")
        self.minsize(970, 620)
        self.store = LicenseStore()
        self.account = tk.StringVar()
        self.broker = tk.StringVar()
        self.start_date = tk.StringVar(value=date.today().isoformat())
        self.days = tk.StringVar(value="30")
        self.search = tk.StringVar()
        self._configure_style()
        self._build()
        self.refresh()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Metric.TLabel", font=("Segoe UI", 18, "bold"), foreground="#087e8b")
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="License Manager", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Quản lý license cá nhân • chạy offline • dữ liệu chỉ nằm trên máy này").pack(anchor="w", pady=(2, 16))

        metrics = ttk.Frame(root)
        metrics.pack(fill="x", pady=(0, 14))
        self.metric_labels: list[ttk.Label] = []
        for title in ("Khách hàng", "License đã cấp", "Tổng số ngày"):
            box = ttk.LabelFrame(metrics, text=title, padding=(18, 8))
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            label = ttk.Label(box, text="0", style="Metric.TLabel")
            label.pack(anchor="w")
            self.metric_labels.append(label)

        content = ttk.Frame(root)
        content.pack(fill="both", expand=True)
        self._build_form(content)
        self._build_list(content)

    def _build_form(self, parent: ttk.Frame) -> None:
        form = ttk.LabelFrame(parent, text="Tạo license", padding=16)
        form.pack(side="left", fill="y", padx=(0, 16))
        for label, variable in (("MT5 Account", self.account), ("Broker", self.broker), ("Ngày bắt đầu (YYYY-MM-DD)", self.start_date)):
            ttk.Label(form, text=label).pack(anchor="w", pady=(0, 3))
            ttk.Entry(form, textvariable=variable, width=31).pack(fill="x", pady=(0, 10))
        ttk.Label(form, text="Số ngày").pack(anchor="w", pady=(0, 3))
        ttk.Combobox(form, textvariable=self.days, values=("1", "30", "90", "180", "365"), width=28, state="readonly").pack(fill="x", pady=(0, 10))
        ttk.Label(form, text="Ghi chú (tùy chọn)").pack(anchor="w", pady=(0, 3))
        self.note = tk.Text(form, height=4, width=30, font=("Segoe UI", 10))
        self.note.pack(fill="x", pady=(0, 12))
        ttk.Button(form, text="TẠO LICENSE", style="Accent.TButton", command=self.create_license).pack(fill="x")
        ttk.Button(form, text="COPY LICENSE", command=self.copy_license).pack(fill="x", pady=(8, 0))
        self.mql_output = tk.Text(form, height=8, width=30, font=("Consolas", 9), wrap="none")
        self.mql_output.pack(fill="both", pady=(14, 0))
        self._update_mql()
        for variable in (self.account, self.broker, self.start_date, self.days):
            variable.trace_add("write", lambda *_: self._update_mql())

    def _build_list(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Danh sách khách hàng", padding=12)
        panel.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(panel)
        top.pack(fill="x", pady=(0, 10))
        ttk.Entry(top, textvariable=self.search, width=36).pack(side="left")
        self.search.trace_add("write", lambda *_: self.refresh())
        ttk.Button(top, text="Backup", command=self.backup).pack(side="right")
        ttk.Button(top, text="Khôi phục", command=self.restore).pack(side="right", padx=(0, 7))
        columns = ("account", "broker", "grants", "latest", "expiry", "status")
        self.table = ttk.Treeview(panel, columns=columns, show="headings", selectmode="browse")
        headings = ("Account", "Broker", "Số lần cấp", "Lần gần nhất", "Hạn hiện tại", "Trạng thái")
        widths = (125, 120, 90, 105, 105, 115)
        for column, heading, width in zip(columns, headings, widths):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor="center" if column not in ("account", "broker") else "w")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<Double-1>", self.show_history)
        ttk.Label(panel, text="Nhấp đúp vào khách hàng để xem toàn bộ lịch sử cấp license.").pack(anchor="w", pady=(9, 0))

    def _update_mql(self) -> None:
        try:
            output = mql_license(self.account.get().strip() or "ACCOUNT", self.broker.get().strip() or "BROKER", self.start_date.get(), int(self.days.get()))
        except ValueError:
            output = "Ngày bắt đầu cần theo dạng YYYY-MM-DD"
        self.mql_output.delete("1.0", "end")
        self.mql_output.insert("1.0", output)

    def create_license(self) -> None:
        account, broker = self.account.get().strip(), self.broker.get().strip()
        try:
            datetime.strptime(self.start_date.get(), DATE_FORMAT)
            days = int(self.days.get())
        except ValueError:
            messagebox.showerror("Dữ liệu chưa đúng", "Ngày bắt đầu phải theo dạng YYYY-MM-DD và số ngày phải hợp lệ.")
            return
        if not account or not broker:
            messagebox.showerror("Thiếu thông tin", "Vui lòng nhập MT5 Account và Broker.")
            return
        self.store.add(account, broker, self.start_date.get(), days, self.note.get("1.0", "end").strip())
        self.note.delete("1.0", "end")
        self.refresh()
        messagebox.showinfo("Đã lưu", "License đã được lưu vào lịch sử khách hàng.")

    def copy_license(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.mql_output.get("1.0", "end").strip())
        self.update()
        messagebox.showinfo("Đã copy", "Đoạn MQL5 đã được copy vào clipboard.")

    def refresh(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)
        for row in self.store.customers(self.search.get()):
            self.table.insert("", "end", values=(row["account"], row["broker"], row["grants"], row["latest_start"], row["current_expiry"], license_status(row["current_expiry"])))
        for label, value in zip(self.metric_labels, self.store.summary()):
            label.configure(text=f"{value:,}")

    def show_history(self, _event: object = None) -> None:
        selected = self.table.selection()
        if not selected:
            return
        account, broker, *_ = self.table.item(selected[0], "values")
        window = tk.Toplevel(self)
        window.title(f"Lịch sử — {account}")
        window.geometry("690x360")
        ttk.Label(window, text=f"Account {account} • {broker}", style="Title.TLabel").pack(anchor="w", padx=18, pady=(16, 8))
        table = ttk.Treeview(window, columns=("number", "start", "days", "expiry", "status", "note"), show="headings")
        for column, heading, width in zip(("number", "start", "days", "expiry", "status", "note"), ("#", "Ngày cấp", "Số ngày", "Ngày hết hạn", "Trạng thái", "Ghi chú"), (45, 105, 80, 110, 115, 210)):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor="center" if column != "note" else "w")
        history = self.store.history(account, broker)
        for index, row in enumerate(reversed(history), start=1):
            table.insert("", "end", values=(index, row["start_date"], row["days"], row["expiry_date"], license_status(row["expiry_date"]), row["note"]))
        table.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def backup(self) -> None:
        filename = f"license-manager-backup-{date.today().isoformat()}.json"
        target = filedialog.asksaveasfilename(title="Lưu backup", defaultextension=".json", initialfile=filename, filetypes=[("JSON backup", "*.json")])
        if target:
            self.store.backup_to(Path(target))
            messagebox.showinfo("Đã backup", f"Đã lưu backup tại:\n{target}")

    def restore(self) -> None:
        target = filedialog.askopenfilename(title="Chọn file backup", filetypes=[("JSON backup", "*.json")])
        if not target or not messagebox.askyesno("Xác nhận khôi phục", "Dữ liệu hiện có sẽ bị thay thế. Tiếp tục?"):
            return
        try:
            count = self.store.restore_from(Path(target))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            messagebox.showerror("Không thể khôi phục", str(error))
            return
        self.refresh()
        messagebox.showinfo("Đã khôi phục", f"Đã khôi phục {count} lần cấp license.")


if __name__ == "__main__":
    LicenseManager().mainloop()
