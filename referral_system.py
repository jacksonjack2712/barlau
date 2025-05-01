import sqlite3

DB_PATH = "referral_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
        user_id INTEGER PRIMARY KEY,
        referrer_id INTEGER,
        balance REAL DEFAULT 0.0
    )""")
    conn.commit()
    conn.close()

def register_user(user_id: int, referrer_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM referrals WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO referrals (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
    conn.commit()
    conn.close()

def add_referral_bonus(user_id: int, amount: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM referrals WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0]:
        bonus = round(amount * 0.1, 2)
        c.execute("UPDATE referrals SET balance = balance + ? WHERE user_id = ?", (bonus, result[0]))
    conn.commit()
    conn.close()

def get_referral_balance(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM referrals WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return round(result[0], 2) if result else 0.0

def get_referral_count(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0
