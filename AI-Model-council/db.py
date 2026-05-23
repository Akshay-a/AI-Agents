import json
import sqlite3
from pathlib import Path


DB_PATH = Path("council.db")
EMPTY_HISTORIES = [[], [], [], []]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            create table if not exists chats (
                id integer primary key autoincrement,
                title text not null,
                chat_history text not null,
                persona_histories text not null,
                created_at text default current_timestamp,
                updated_at text default current_timestamp
            )
            """
        )


def create_chat(title: str = "New chat") -> int:
    with connect() as conn:
        cur = conn.execute(
            "insert into chats(title, chat_history, persona_histories) values (?, ?, ?)",
            (title, "[]", json.dumps(EMPTY_HISTORIES)),
        )
        return int(cur.lastrowid)


def list_chats() -> list[tuple[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            "select id, title from chats order by updated_at desc, id desc"
        ).fetchall()
    return [(row["title"], str(row["id"])) for row in rows]


def load_chat(chat_id: str | int) -> tuple[list[dict], list[list[dict]]]:
    with connect() as conn:
        row = conn.execute(
            "select chat_history, persona_histories from chats where id = ?",
            (chat_id,),
        ).fetchone()
    if not row:
        return [], [history[:] for history in EMPTY_HISTORIES]
    return json.loads(row["chat_history"]), json.loads(row["persona_histories"])


def save_chat(
    chat_id: str | int,
    chat_history: list[dict],
    persona_histories: list[list[dict]],
    title: str | None = None,
) -> None:
    final_title = title or derive_title(chat_history)
    with connect() as conn:
        conn.execute(
            """
            update chats
            set title = ?, chat_history = ?, persona_histories = ?, updated_at = current_timestamp
            where id = ?
            """,
            (final_title, json.dumps(chat_history), json.dumps(persona_histories), chat_id),
        )


def derive_title(chat_history: list[dict]) -> str:
    first_user = next((m["content"] for m in chat_history if m["role"] == "user"), "New chat")
    return first_user.strip().splitlines()[0][:40] or "New chat"


def ensure_chat() -> tuple[str, list[tuple[str, str]], list[dict], list[list[dict]]]:
    init_db()
    chats = list_chats()
    if not chats:
        create_chat()
        chats = list_chats()
    chat_id = chats[0][1]
    chat_history, persona_histories = load_chat(chat_id)
    return chat_id, chats, chat_history, persona_histories
