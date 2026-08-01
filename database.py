"""
database.py — слой работы с SQLite3.

Хранит напоминания и предоставляет CRUD-операции.
При инициализации создаёт таблицы, если их нет.
"""

import sqlite3
from datetime import datetime

DB_PATH = "reminders.db"

VALID_STATUSES = ("Ожидает", "Готово", "Просрочено", "Отменено")


class Database:
    """Инкапсулирует все операции с базой данных напоминаний."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        # check_same_thread=False — чтобы фоновый поток мог читать БД
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    # Инициализация схемы
    # ------------------------------------------------------------------
    def _create_tables(self) -> None:
        """Создаёт таблицу reminders, если она не существует."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                trigger_at  TEXT    NOT NULL,   -- ISO-8601: '2026-08-01 14:30'
                status      TEXT    NOT NULL DEFAULT 'Ожидает',
                notified    INTEGER NOT NULL DEFAULT 0   -- 0/1: показано ли уведомление
            )
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add_reminder(self, title: str, description: str, trigger_at: str) -> int:
        """Добавляет новое напоминание со статусом 'Ожидает'. Возвращает id."""
        cur = self.conn.execute(
            "INSERT INTO reminders (title, description, trigger_at, status) "
            "VALUES (?, ?, ?, 'Ожидает')",
            (title, description, trigger_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_reminder(self, reminder_id: int) -> None:
        """Удаляет напоминание по id."""
        self.conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.conn.commit()

    def update_status(self, reminder_id: int, status: str) -> None:
        """Меняет статус напоминания. Статус должен быть из VALID_STATUSES."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Недопустимый статус: {status}")
        self.conn.execute(
            "UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id)
        )
        self.conn.commit()

    def mark_notified(self, reminder_id: int) -> None:
        """Отмечает, что уведомление для напоминания уже показано."""
        self.conn.execute(
            "UPDATE reminders SET notified = 1 WHERE id = ?", (reminder_id,)
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Запросы
    # ------------------------------------------------------------------
    def get_all(self, status_filter: str | None = None) -> list[dict]:
        """
        Возвращает список всех напоминаний.
        Если status_filter задан — только напоминания с этим статусом.
        Сортировка: по дате срабатывания (ближайшие — первыми).
        """
        if status_filter and status_filter != "Все":
            rows = self.conn.execute(
                "SELECT * FROM reminders WHERE status = ? ORDER BY trigger_at",
                (status_filter,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM reminders ORDER BY trigger_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_due_reminders(self) -> list[dict]:
        """
        Возвращает напоминания со статусом 'Ожидает', время которых наступило
        и уведомление ещё не было показано.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows = self.conn.execute(
            "SELECT * FROM reminders "
            "WHERE status = 'Ожидает' AND trigger_at <= ? AND notified = 0 "
            "ORDER BY trigger_at",
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Автоматическое обновление статусов
    # ------------------------------------------------------------------
    def mark_overdue(self) -> int:
        """
        Переводит все напоминания со статусом 'Ожидает', время которых прошло,
        в статус 'Просрочено'. Возвращает количество обновлённых записей.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = self.conn.execute(
            "UPDATE reminders SET status = 'Просрочено' "
            "WHERE status = 'Ожидает' AND trigger_at < ?",
            (now_iso,),
        )
        self.conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self.conn.close()
