"""
app.py — главное приложение (GUI на tkinter + фоновый планировщик).

Структура:
  - Класс ReminderApp — GUI, управление напоминаниями.
  - Фоновый поток-планировщик каждые 30 секунд проверяет,
    не наступило ли время напоминаний, и показывает уведомления.
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from database import Database, VALID_STATUSES
from notifier import Notifier

CHECK_INTERVAL = 30  # секунд между проверками напоминаний


class ReminderApp:
    """Главное окно приложения-напоминалки."""

    def __init__(self):
        self.db = Database()
        self.root = tk.Tk()
        self.root.title("Напоминалка")
        self.root.geometry("780x520")
        self.root.minsize(680, 420)
        self.root.configure(bg="#1e1e2e")

        # Текущий фильтр статуса
        self.status_filter = tk.StringVar(value="Все")

        self._build_ui()
        self._refresh_list()

        # Запуск фонового планировщика
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler, daemon=True)
        self._scheduler_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # ПОСТРОЕНИЕ ИНТЕРФЕЙСА
    # ==================================================================
    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background="#1e1e2e")
        style.configure("Dark.TLabel", background="#1e1e2e", foreground="#cdd6f4")
        style.configure(
            "Dark.TButton",
            background="#45475a", foreground="#cdd6f4",
            borderwidth=0, focusthickness=0,
        )
        style.map(
            "Dark.TButton",
            background=[("active", "#585b70")],
        )
        style.configure(
            "Treeview",
            background="#313244", foreground="#cdd6f4",
            fieldbackground="#313244", borderwidth=0, rowheight=28,
        )
        style.configure(
            "Treeview.Heading",
            background="#45475a", foreground="#cdd6f4",
            borderwidth=0, relief="flat",
        )
        style.configure(
            "Dark.TCombobox",
            fieldbackground="#313244", background="#45475a",
            foreground="#cdd6f4", selectbackground="#585b70",
        )

        # --- Заголовок ---
        header = tk.Label(
            self.root, text="📋 Напоминалка",
            font=("Segoe UI", 18, "bold"),
            fg="#cdd6f4", bg="#1e1e2e",
        )
        header.pack(pady=(16, 12))

        # --- Панель кнопок ---
        btn_frame = ttk.Frame(self.root, style="Dark.TFrame")
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))

        ttk.Button(btn_frame, text="+ Добавить", style="Dark.TButton",
                   command=self._open_add_dialog).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Удалить", style="Dark.TButton",
                   command=self._delete_selected).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="✓ Готово", style="Dark.TButton",
                   command=lambda: self._set_status("Готово")).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="✕ Отменено", style="Dark.TButton",
                   command=lambda: self._set_status("Отменено")).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="↻ Обновить", style="Dark.TButton",
                   command=self._refresh_list).pack(side="left", padx=8)

        # --- Фильтр ---
        filter_frame = ttk.Frame(self.root, style="Dark.TFrame")
        filter_frame.pack(fill="x", padx=20, pady=(0, 8))

        ttk.Label(filter_frame, text="Фильтр:", style="Dark.TLabel").pack(side="left")
        filter_values = ["Все"] + list(VALID_STATUSES)
        self.filter_combo = ttk.Combobox(
            filter_frame, textvariable=self.status_filter,
            values=filter_values, state="readonly", width=14,
        )
        self.filter_combo.pack(side="left", padx=(8, 0))
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        # --- Таблица ---
        columns = ("id", "title", "description", "trigger_at", "status")
        self.tree = ttk.Treeview(
            self.root, columns=columns, show="headings", style="Treeview"
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Заголовок")
        self.tree.heading("description", text="Описание")
        self.tree.heading("trigger_at", text="Дата и время")
        self.tree.heading("status", text="Статус")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("title", width=180)
        self.tree.column("description", width=250)
        self.tree.column("trigger_at", width=140, anchor="center")
        self.tree.column("status", width=100, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Теги для раскраски строк по статусу
        self.tree.tag_configure("Ожидает", foreground="#89b4fa")
        self.tree.tag_configure("Готово", foreground="#a6e3a1")
        self.tree.tag_configure("Просрочено", foreground="#f38ba8")
        self.tree.tag_configure("Отменено", foreground="#6c7086")

        # --- Статус-бар ---
        self.status_bar = tk.Label(
            self.root, text="Готово", anchor="w",
            font=("Segoe UI", 9), fg="#6c7086", bg="#1e1e2e",
        )
        self.status_bar.pack(fill="x", padx=20, pady=(0, 8))

    # ==================================================================
    # РАБОТА СО СПИСКОМ
    # ==================================================================
    def _refresh_list(self) -> None:
        """Обновляет таблицу напоминаний с учётом фильтра."""
        # Сначала переводим просроченные в нужный статус
        overdue_count = self.db.mark_overdue()

        for item in self.tree.get_children():
            self.tree.delete(item)

        filt = self.status_filter.get()
        reminders = self.db.get_all(filt)

        for r in reminders:
            self.tree.insert(
                "", "end",
                values=(r["id"], r["title"], r["description"],
                        r["trigger_at"], r["status"]),
                tags=(r["status"],),
            )

        if overdue_count > 0:
            self.status_bar.config(text=f"Переведено в «Просрочено»: {overdue_count}")
        else:
            self.status_bar.config(text=f"Всего записей: {len(reminders)}")

    def _selected_id(self) -> int | None:
        """Возвращает id выбранной в таблице строки или None."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите напоминание в списке.")
            return None
        return int(self.tree.item(sel[0])["values"][0])

    # ==================================================================
    # ДЕЙСТВИЯ
    # ==================================================================
    def _delete_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранное напоминание?"):
            self.db.delete_reminder(rid)
            self._refresh_list()

    def _set_status(self, status: str) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        self.db.update_status(rid, status)
        self._refresh_list()

    # ==================================================================
    # ДИАЛОГ ДОБАВЛЕНИЯ
    # ==================================================================
    def _open_add_dialog(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Новое напоминание")
        dlg.geometry("400x340")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg="#1e1e2e")

        # Заголовок
        tk.Label(dlg, text="Заголовок:", font=("Segoe UI", 11),
                fg="#cdd6f4", bg="#1e1e2e").pack(anchor="w", padx=20, pady=(20, 4))
        entry_title = tk.Entry(dlg, font=("Segoe UI", 11), width=40,
                               bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                               relief="flat")
        entry_title.pack(padx=20, pady=(0, 8))

        # Описание
        tk.Label(dlg, text="Описание:", font=("Segoe UI", 11),
                fg="#cdd6f4", bg="#1e1e2e").pack(anchor="w", padx=20, pady=(0, 4))
        text_desc = tk.Text(dlg, font=("Segoe UI", 11), width=40, height=4,
                            bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                            relief="flat")
        text_desc.pack(padx=20, pady=(0, 8))

        # Дата и время
        tk.Label(dlg, text="Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ):", font=("Segoe UI", 11),
                fg="#cdd6f4", bg="#1e1e2e").pack(anchor="w", padx=20, pady=(0, 4))

        now = datetime.now()
        default_dt = now.strftime("%Y-%m-%d %H:%M")
        entry_dt = tk.Entry(dlg, font=("Segoe UI", 11), width=40,
                            bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                            relief="flat")
        entry_dt.insert(0, default_dt)
        entry_dt.pack(padx=20, pady=(0, 16))

        # Кнопки
        btn_frame = tk.Frame(dlg, bg="#1e1e2e")
        btn_frame.pack(pady=(0, 16))

        def _save():
            title = entry_title.get().strip()
            desc = text_desc.get("1.0", "end").strip()
            dt_str = entry_dt.get().strip()

            if not title:
                messagebox.showwarning("Внимание", "Введите заголовок.", parent=dlg)
                return

            # Валидация формата даты
            try:
                parsed = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            except ValueError:
                messagebox.showerror(
                    "Ошибка",
                    "Неверный формат даты.\nИспользуйте: ГГГГ-ММ-ДД ЧЧ:ММ",
                    parent=dlg,
                )
                return

            self.db.add_reminder(title, desc, dt_str)
            self._refresh_list()
            dlg.destroy()

        tk.Button(btn_frame, text="Сохранить", font=("Segoe UI", 10, "bold"),
                  bg="#a6e3a1", fg="#1e1e2e", relief="flat", padx=20, pady=6,
                  cursor="hand2", command=_save).pack(side="left", padx=8)
        tk.Button(btn_frame, text="Отмена", font=("Segoe UI", 10),
                  bg="#45475a", fg="#cdd6f4", relief="flat", padx=20, pady=6,
                  cursor="hand2", command=dlg.destroy).pack(side="left", padx=8)

    # ==================================================================
    # ФОНОВЫЙ ПЛАНИРОВЩИК
    # ==================================================================
    def _scheduler(self) -> None:
        """
        Фоновый поток: каждые CHECK_INTERVAL секунд проверяет
        наступившие напоминания и показывает уведомления.
        Работает даже когда окно свёрнуто.
        """
        while self._running:
            try:
                # Обновляем просроченные
                self.db.mark_overdue()

                # Получаем наступившие напоминания
                due = self.db.get_due_reminders()

                for reminder in due:
                    # Отмечаем как уведомлённое ДО показа,
                    # чтобы не показать повторно
                    self.db.mark_notified(reminder["id"])

                    # Показываем уведомление
                    Notifier.notify(
                        reminder,
                        on_done=lambda rid: self.db.update_status(rid, "Готово"),
                        on_cancel=lambda rid: self.db.update_status(rid, "Отменено"),
                    )

                # Если были изменения — обновляем таблицу в главном потоке
                if due:
                    self.root.after(0, self._refresh_list)

            except Exception:
                pass

            # Спим CHECK_INTERVAL секунд маленькими порциями,
            # чтобы быстро реагировать на закрытие приложения
            for _ in range(CHECK_INTERVAL):
                if not self._running:
                    break
                threading.Event().wait(1)

    # ==================================================================
    # ЗАВЕРШЕНИЕ
    # ==================================================================
    def _on_close(self) -> None:
        self._running = False
        self.db.close()
        self.root.destroy()

    # ==================================================================
    # ЗАПУСК
    # ==================================================================
    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = ReminderApp()
    app.run()
