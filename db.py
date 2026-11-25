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
    id             TEXT PRIMARY KEY,
    event          TEXT NOT NULL DEFAULT '',
    number         INTEGER,
    time           INTEGER,
    template       TEXT,
    layout         TEXT,
    style          TEXT,
    caption        TEXT,
    lucky          TEXT,
    copies         INTEGER DEFAULT 1,
    host_copy      INTEGER DEFAULT 0,
    guest_name     TEXT,
    guest_message  TEXT,
    has_signature  INTEGER DEFAULT 0,
    poses          TEXT,
    is_demo        INTEGER DEFAULT 0,
    payment_amount INTEGER DEFAULT 0,
    payment_method TEXT DEFAULT '',
    payment_status TEXT DEFAULT ''
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
        # Migrasi kolom tambahan jika tabel sessions sudah ada sebelumnya
        cols = {r[1] for r in c.execute("PRAGMA table_info(sessions)").fetchall()}
        if "is_demo" not in cols:
            c.execute("ALTER TABLE sessions ADD COLUMN is_demo INTEGER DEFAULT 0")
        if "payment_amount" not in cols:
            c.execute("ALTER TABLE sessions ADD COLUMN payment_amount INTEGER DEFAULT 0")
        if "payment_method" not in cols:
            c.execute("ALTER TABLE sessions ADD COLUMN payment_method TEXT DEFAULT ''")
        if "payment_status" not in cols:
            c.execute("ALTER TABLE sessions ADD COLUMN payment_status TEXT DEFAULT ''")


def add_session(m):
    """m: isi meta.json (+ style, copies, host_copy, payment, is_demo)."""
    gb = m.get("guestbook") or {}
    pay = m.get("payment") or {}
    is_demo = 1 if (m.get("is_demo") or m.get("payment_status") == "DEMO" or pay.get("status") == "DEMO") else 0
    pay_amount = 0 if is_demo else int(m.get("payment_amount") or pay.get("amount") or 0)
    pay_method = "DEMO" if is_demo else str(m.get("payment_method") or pay.get("method") or "")
    pay_status = "DEMO" if is_demo else str(m.get("payment_status") or pay.get("status") or "")
    row = (m["id"], m.get("event", ""), m.get("number"), m.get("time"), m.get("template"), m.get("layout"),
           m.get("style"), m.get("caption"), m.get("lucky"), int(m.get("copies") or 1), int(bool(m.get("host_copy"))),
           gb.get("name"), gb.get("message"), int(bool(gb.get("signature"))),
           json.dumps(m.get("poses") or [], ensure_ascii=False),
           is_demo, pay_amount, pay_method, pay_status)
    with _lock, _conn() as c:
        c.execute("""INSERT OR REPLACE INTO sessions
                     (id, event, number, time, template, layout, style, caption, lucky, copies, host_copy,
                      guest_name, guest_message, has_signature, poses, is_demo, payment_amount, payment_method, payment_status)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)


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


def stats(event, start_time=None, end_time=None, ev_config=None):
    import licensing as LIC
    is_lic_demo = bool(LIC.status().get("demo", True))

    where = "WHERE event=?"
    params = [event]
    if start_time is not None:
        where += " AND time >= ?"
        params.append(int(start_time))
    if end_time is not None:
        where += " AND time <= ?"
        params.append(int(end_time))

    with _conn() as c:
        q = lambda sql: c.execute(sql, params)

        tot = q(f"""SELECT COUNT(*) n,
                    COALESCE(SUM(copies),0) + COALESCE(SUM(host_copy),0) prints,
                    COALESCE(SUM(CASE WHEN is_demo = 1 THEN 0 ELSE payment_amount END),0) revenue,
                    COALESCE(SUM(CASE WHEN is_demo = 1 THEN 1 ELSE 0 END),0) demo_sessions,
                    COALESCE(SUM(CASE WHEN is_demo = 1 THEN copies + host_copy ELSE 0 END),0) demo_prints,
                    SUM(guest_message IS NOT NULL AND guest_message != '') gb, SUM(lucky IS NOT NULL) lucky,
                    MIN(time) first, MAX(time) last FROM sessions {where}""").fetchone()

        tpl = q(f"""SELECT template, COUNT(*) n,
                           COALESCE(SUM(CASE WHEN is_demo = 1 THEN 0 ELSE payment_amount END),0) rev,
                           COALESCE(SUM(CASE WHEN is_demo = 1 THEN 1 ELSE 0 END),0) demo_n
                    FROM sessions {where} GROUP BY template ORDER BY n DESC""").fetchall()
        lay = q(f"""SELECT layout, COUNT(*) n, COALESCE(SUM(copies),0) + COALESCE(SUM(host_copy),0) prints
                    FROM sessions {where} GROUP BY layout ORDER BY n DESC""").fetchall()
        sty = q(f"""SELECT style, COUNT(*) n
                    FROM sessions {where} GROUP BY style ORDER BY n DESC""").fetchall()
        hrs = q(f"""SELECT strftime('%H', time, 'unixepoch', 'localtime') h, COUNT(*) n,
                           COALESCE(SUM(copies),0) + COALESCE(SUM(host_copy),0) prints,
                           COALESCE(SUM(CASE WHEN is_demo = 1 THEN 0 ELSE payment_amount END),0) rev,
                           COALESCE(SUM(CASE WHEN is_demo = 1 THEN 1 ELSE 0 END),0) demo_n
                    FROM sessions {where} GROUP BY h ORDER BY h""").fetchall()
        pay_methods = q(f"""SELECT payment_method m, COUNT(*) n,
                                   COALESCE(SUM(CASE WHEN is_demo = 1 THEN 0 ELSE payment_amount END),0) rev
                            FROM sessions
                            {where} AND payment_method != '' AND payment_method != 'DEMO'
                            GROUP BY m ORDER BY rev DESC""").fetchall()
        daily = q(f"""SELECT date(time, 'unixepoch', 'localtime') dt, COUNT(*) n,
                             COALESCE(SUM(copies),0) + COALESCE(SUM(host_copy),0) prints,
                             COALESCE(SUM(CASE WHEN is_demo = 1 THEN 0 ELSE payment_amount END),0) rev,
                             COALESCE(SUM(CASE WHEN is_demo = 1 THEN 1 ELSE 0 END),0) demo_n
                      FROM sessions {where} GROUP BY dt ORDER BY dt""").fetchall()
        drw = c.execute("SELECT COUNT(*) FROM draws WHERE event=?", (event,)).fetchone()[0]

        # Rentang tanggal keseluruhan di database event ini
        bounds = c.execute("SELECT MIN(time) min_t, MAX(time) max_t FROM sessions WHERE event=?", (event,)).fetchone()

    n = tot["n"] or 0
    prints = tot["prints"] or 0
    rev = tot["revenue"] or 0
    demo_sessions = tot["demo_sessions"] or 0
    demo_prints = tot["demo_prints"] or 0
    real_sessions = n - demo_sessions

    cfg_pay = (ev_config or {}).get("payment") or {}

    peak_h = max(hrs, key=lambda x: x["n"])["h"] if hrs else None
    peak_count = max(hrs, key=lambda x: x["n"])["n"] if hrs else 0

    return {
        "sessions": n,
        "prints": prints,
        "revenue": rev,
        "revenue_formatted": f"Rp {rev:,}".replace(",", "."),
        "demo_sessions": demo_sessions,
        "demo_prints": demo_prints,
        "real_sessions": real_sessions,
        "is_demo_license": is_lic_demo,
        "avg_prints_per_session": round(prints / n, 1) if n > 0 else 0,
        "avg_revenue_per_session": round(rev / real_sessions) if real_sessions > 0 else 0,
        "paper_meters_estimated": round(prints * 0.22, 1),
        "peak_hour": f"{peak_h}:00" if peak_h is not None else None,
        "peak_hour_count": peak_count,
        "guestbook": tot["gb"] or 0,
        "lucky": tot["lucky"] or 0,
        "draws": drw,
        "first": tot["first"],
        "last": tot["last"],
        "min_date": bounds["min_t"] if bounds else None,
        "max_date": bounds["max_t"] if bounds else None,
        "templates": [dict(r) for r in tpl],
        "layouts": [dict(r) for r in lay],
        "styles": [dict(r) for r in sty],
        "hours": [dict(r) for r in hrs],
        "payment_methods": [dict(r) for r in pay_methods],
        "daily": [dict(r) for r in daily],
        "payment_enabled": bool(cfg_pay.get("enabled")),
        "price_receipt": int(cfg_pay.get("price_receipt") or 15000),
        "price_photo": int(cfg_pay.get("price_photo") or 30000),
    }


def export_rows(event, start_time=None, end_time=None):
    where = "WHERE event=?"
    params = [event]
    if start_time is not None:
        where += " AND time >= ?"
        params.append(int(start_time))
    if end_time is not None:
        where += " AND time <= ?"
        params.append(int(end_time))

    with _conn() as c:
        cur = c.execute(f"""SELECT number, datetime(time, 'unixepoch', 'localtime') waktu,
                            (CASE WHEN is_demo = 1 THEN 'DEMO' ELSE 'RESMI' END) status_lisensi,
                            template, layout, style, caption, copies, host_copy,
                            (CASE WHEN is_demo = 1 THEN 0 ELSE payment_amount END) pendapatan,
                            payment_method metode_bayar,
                            guest_name, guest_message, id
                            FROM sessions {where} ORDER BY time""", params)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()
