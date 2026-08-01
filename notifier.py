"""
notifier.py — логика уведомлений.

При наступлении времени напоминания показывается:
  1. Системное toast-уведомление Windows 11 (через plyer).
  2. Popup-окно tkinter поверх всех окон.
Уведомления работают даже если главное окно свёрнуто.
"""

import threading
import tkinter as tk
from tkinter import ttk

try:
    from plyer import notification as _toast
    _TOAST_AVAILABLE = True
except Exception:
    _TOAST_AVAILABLE = False


class Notifier:
    """Показывает уведомления о напоминаниях."""

    TOAST_APP_NAME = "Напоминалка"

    # ------------------------------------------------------------------
    # Системное toast-уведомление (Windows 11)
    # ------------------------------------------------------------------
    @staticmethod
    def show_toast(title: str, message: str) -> None:
        """Показывает системное уведомление Windows через plyer."""
        if not _TOAST_AVAILABLE:
            return
        try:
            _toast.notify(
                title=title,
                message=message,
                app_name=Notifier.TOAST_APP_NAME,
                timeout=10,
            )
        except Exception:
            # toast может не сработать на некоторых сборках Windows —
            # popup-окно всё равно покажется, поэтому просто игнорируем.
            pass

    # ------------------------------------------------------------------
    # Popup-окно поверх всех окон
    # ------------------------------------------------------------------
    @staticmethod
    def show_popup(reminder: dict, on_done=None, on_cancel=None) -> None:
        """
        Показывает всплывающее окно поверх всех окон.

        Параметры:
            reminder   — словарь с ключами id, title, description, trigger_at
            on_done    — callback(reminder_id), вызывается при нажатии 'Готово'
            on_cancel  — callback(reminder_id), вызывается при нажатии 'Отменено'
        """
        # Окно создаётся в отдельном потоке, поэтому нужен свой Tk-инстанс.
        popup = tk.Tk()
        popup.title("Напоминание")
        popup.attributes("-topmost", True)          # поверх всех окон
        popup.geometry("420x220+{}+{}".format(
            popup.winfo_screenwidth() // 2 - 210,
            popup.winfo_screenheight() // 2 - 110,
        ))
        popup.resizable(False, False)
        popup.configure(bg="#1e1e2e")

        # --- Заголовок ---
        lbl_title = tk.Label(
            popup,
            text=reminder["title"],
            font=("Segoe UI", 14, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
            wraplength=380,
            justify="center",
        )
        lbl_title.pack(pady=(20, 8))

        # --- Время ---
        lbl_time = tk.Label(
            popup,
            text=f"⏰ {reminder['trigger_at']}",
            font=("Segoe UI", 10),
            fg="#a6adc8",
            bg="#1e1e2e",
        )
        lbl_time.pack(pady=(0, 8))

        # --- Описание ---
        lbl_desc = tk.Label(
            popup,
            text=reminder.get("description", "") or "Без описания",
            font=("Segoe UI", 11),
            fg="#bac2de",
            bg="#1e1e2e",
            wraplength=380,
            justify="center",
        )
        lbl_desc.pack(pady=(0, 16), fill="x", padx=20)

        # --- Кнопки ---
        btn_frame = tk.Frame(popup, bg="#1e1e2e")
        btn_frame.pack(pady=(0, 16))

        def _done():
            if on_done:
                on_done(reminder["id"])
            popup.destroy()

        def _cancel():
            if on_cancel:
                on_cancel(reminder["id"])
            popup.destroy()

        btn_done = tk.Button(
            btn_frame, text="✓ Готово", font=("Segoe UI", 10, "bold"),
            bg="#a6e3a1", fg="#1e1e2e", relief="flat",
            padx=16, pady=6, cursor="hand2", command=_done,
        )
        btn_done.pack(side="left", padx=8)

        btn_cancel = tk.Button(
            btn_frame, text="✕ Отменено", font=("Segoe UI", 10, "bold"),
            bg="#f38ba8", fg="#1e1e2e", relief="flat",
            padx=16, pady=6, cursor="hand2", command=_cancel,
        )
        btn_cancel.pack(side="left", padx=8)

        btn_close = tk.Button(
            btn_frame, text="Закрыть", font=("Segoe UI", 10),
            bg="#45475a", fg="#cdd6f4", relief="flat",
            padx=16, pady=6, cursor="hand2", command=popup.destroy,
        )
        btn_close.pack(side="left", padx=8)

        # Звуковой сигнал
        popup.bell()
        popup.mainloop()

    # ------------------------------------------------------------------
    # Комбинированный запуск: toast + popup в отдельном потоке
    # ------------------------------------------------------------------
    @staticmethod
    def notify(reminder: dict, on_done=None, on_cancel=None) -> None:
        """
        Показывает toast-уведомление и popup-окно.
        Popup запускается в отдельном потоке, чтобы не блокировать
        главный цикл приложения.
        """
        title = reminder.get("title", "Напоминание")
        desc = reminder.get("description", "")

        # 1. Toast — быстро, не блокирует
        Notifier.show_toast(title, desc)

        # 2. Popup — в отдельном потоке
        thread = threading.Thread(
            target=Notifier.show_popup,
            args=(reminder, on_done, on_cancel),
            daemon=True,
        )
        thread.start()
