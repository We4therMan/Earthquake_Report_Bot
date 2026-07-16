import sqlite3

def init_guild_table():
    conn = sqlite3.connect("data/guild_settings.db")
    cursor = conn.cursor()

    cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
                )
    """)
    conn.commit()
    conn.close()

def set_channel(guild_id: int, channel_id: int):
    conn = sqlite3.connect("data/guild_settings.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO guild_settings (guild_id, channel_id)
    VALUES (?, ?)
    ON CONFLICT(guild_id)
    DO UPDATE SET channel_id = excluded.channel_id
    """, (guild_id, channel_id))

    conn.commit()
    conn.close()

def get_channel(guild_id: int):
    conn = sqlite3.connect("data/guild_settings.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT channel_id FROM guild_settings WHERE guild_id = ?",
        (guild_id,)
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None