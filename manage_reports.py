import sqlite3

def init_reports_table():
    conn = sqlite3.connect("data/reports.db")
    cursor = conn.cursor()

    cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS reports (
                event_id TEXT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                PRIMARY KEY(event_id, guild_id)
                )
    """)
    conn.commit()
    conn.close()
    print("report table created")

def store_report_msg(ev_id, guild_id, channel_id, message_id):
    """add (ev_id, guild_id, channel_id, message_id) to table"""
    conn = sqlite3.connect("data/reports.db")
    cursor = conn.cursor()

    sql = "INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?)"
    data = (ev_id, guild_id, channel_id, message_id)

    cursor.execute(sql,data)
    conn.commit()

    conn.close()

def select_report_msgs(ev_id):
    """Return list of tuples for ev_id
    [(guild,channel,msg),...]
    """
    conn = sqlite3.connect("data/reports.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
    """
    SELECT guild_id, channel_id, message_id
    FROM reports
    WHERE event_id = ?
    """, (ev_id,))

    reports_for_event = cursor.fetchall()
    reports = [(guild_id, channel_id, message_id) for guild_id, channel_id, message_id in reports_for_event]
    return reports