"""Catatan SQLite (output/photobooth.db) untuk statistik & ekspor.

File di output/sessions/*/meta.json tetap sumber utama. Database ini hanya indeks tambahan:
kalau dihapus, otomatis dibangun ulang dari meta.json saat server menyala.
"""
import json
import os
import sqlite3
import threading

import paths as P

BASE = P.BASE
DB_PATH = os.path.join(P.OUT, "photobooth.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    event         TEXT NOT NULL DEFAULT '',
    number        INTEGER,
    time          INTEGER,
    template      TEXT,
    layout        TEXT,
    style         TEXT,
    caption       TEXT,
    lucky         TEXT,
    copies        INTEGER DEFAULT 1,
    host_copy     INTEGER DEFAULT 0,
    guest_name    TEXT,
    guest_message TEXT,
    has_signature INTEGER DEFAULT 0,
    poses         TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_event_time ON sessions(event, time);

CREATE TABLE IF NOT EXISTS draws (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    event   TEXT NOT NULL,
    lucky   TEXT NOT NULL,
    session TEXT,
    time    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_draws_event ON draws(event);
"""


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)


def add_session(m):
    """m: isi meta.json (+ style, copies, host_copy)."""
    gb = m.get("guestbook") or {}
    row = (m["id"], m.get("event", ""), m.get("number"), m.get("time"), m.get("template"), m.get("layout"),
           m.get("style"), m.get("caption"), m.get("lucky"), int(m.get("copies") or 1), int(bool(m.get("host_copy"))),
           gb.get("name"), gb.get("message"), int(bool(gb.get("signature"))),
           json.dumps(m.get("poses") or [], ensure_ascii=False))
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)


def add_draw(event, lucky, session, t):
    with _lock, _conn() as c:
        c.execute("INSERT INTO draws(event, lucky, session, time) VALUES (?,?,?,?)", (event, lucky, session, t))


def reset_draws(event):
    with _lock, _conn() as c:
        c.execute("DELETE FROM draws WHERE event=?", (event,))


def backfill(sessions_root):
    """Masukkan sesi lama (meta.json) yang belum ada di database."""
    if not os.path.isdir(sessions_root):
        return 0
    with _conn() as c:
        known = {r[0] for r in c.execute("SELECT id FROM sessions")}
    n = 0
    for sid in os.listdir(sessions_root):
        mp = os.path.join(sessions_root, sid, "meta.json")
        if sid in known or not os.path.exists(mp):
            continue
        try:
            with open(mp, encoding="utf-8") as f:
                add_session(json.load(f))
            n += 1
        except (OSError, ValueError, KeyError):
            continue
    return n


def stats(event):
    with _conn() as c:
        q = lambda sql, *a: c.execute(sql, (event, *a))  # noqa: E731
        tot = q("""SELECT COUNT(*) n, COALESCE(SUM(copies),0) + COALESCE(SUM(host_copy),0) prints,
                   SUM(guest_message IS NOT NULL AND guest_message != '') gb, SUM(lucky IS NOT NULL) lucky,
                   MIN(time) first, MAX(time) last FROM sessions WHERE event=?""").fetchone()
        tpl = q("SELECT template, COUNT(*) n FROM sessions WHERE event=? GROUP BY template ORDER BY n DESC").fetchall()
        lay = q("SELECT layout, COUNT(*) n FROM sessions WHERE event=? GROUP BY layout ORDER BY n DESC").fetchall()
        sty = q("SELECT style, COUNT(*) n FROM sessions WHERE event=? GROUP BY style ORDER BY n DESC").fetchall()
        hrs = q("""SELECT strftime('%H', time, 'unixepoch', 'localtime') h, COUNT(*) n FROM sessions
                   WHERE event=? GROUP BY h ORDER BY h""").fetchall()
        drw = q("SELECT COUNT(*) FROM draws WHERE event=?").fetchone()[0]
    return {
        "sessions": tot["n"], "prints": tot["prints"], "guestbook": tot["gb"] or 0, "lucky": tot["lucky"] or 0,
        "draws": drw, "first": tot["first"], "last": tot["last"],
        "templates": [dict(r) for r in tpl], "layouts": [dict(r) for r in lay],
        "styles": [dict(r) for r in sty], "hours": [dict(r) for r in hrs],
    }


def export_rows(event):
    with _conn() as c:
        cur = c.execute("""SELECT number, datetime(time, 'unixepoch', 'localtime') waktu, template, layout, style,
                           caption, lucky, copies, host_copy, guest_name, guest_message, has_signature, id
                           FROM sessions WHERE event=? ORDER BY time""", (event,))
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()
