import sqlite3


def init_db():
    with sqlite3.connect("database.db", check_same_thread=False) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone_number TEXT DEFAULT '',
                balance INTEGER DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT CHECK(type IN ('deposit', 'withdraw')) NOT NULL,
                status TEXT CHECK(status IN ('pending', 'completed', 'failed')) DEFAULT 'pending',
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                file_id TEXT UNIQUE NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1), -- Faqat 1 qator bo'lishi uchun
                admin_id INTEGER DEFAULT 288649486,
                card_number TEXT DEFAULT '0000 0000 0000 0000',
                card_holder TEXT DEFAULT 'Unknown User'
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")

        conn.commit()


def get_admin_id():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM settings WHERE id = 1")
    admin_id = cursor.fetchone()
    conn.close()
    return admin_id[0] if admin_id else None


def update_admin_id(new_admin_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET admin_id = ? WHERE id = 1", (new_admin_id,))
    conn.commit()
    conn.close()


def get_card_details():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT card_number, card_holder FROM settings WHERE id = 1")
    card_details = cursor.fetchone()
    conn.close()
    return card_details if card_details else ("0000 0000 0000 0000", "Unknown User")


def update_card_details(new_card_number: str, new_card_holder: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET card_number = ?, card_holder = ? WHERE id = 1",
        (new_card_number, new_card_holder)
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT user_id, phone_number, balance, created_at FROM users")
    users = cursor.fetchall()

    conn.close()
    return users


def get_transactions_by_verification(status):
    """Tasdiqlangan, tasdiqlanmagan yoki hali tekshirilmagan tranzaksiyalarni olish"""
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        query = """
            SELECT t.transaction_id, u.user_id, u.phone_number, t.amount, t.status, t.created_at, r.verified
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            LEFT JOIN receipts r ON t.transaction_id = r.transaction_id
            WHERE {condition}
            ORDER BY t.created_at DESC
        """

        if status == "verified":
            condition = "r.verified = TRUE"
        elif status == "unverified":
            condition = "r.verified = FALSE"
        else:  # "new" status
            condition = "r.verified IS NULL"

        cursor.execute(query.format(condition=condition))
        transactions = cursor.fetchall()
        conn.close()
        return transactions

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return None


def verify_transaction(transaction_id):
    """Tranzaksiyani tasdiqlash"""
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE receipts SET verified = TRUE WHERE transaction_id = ?
        """, (transaction_id,))
        
        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False


def reject_transaction(transaction_id):
    """Tranzaksiyani rad etish"""
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE transactions SET status = 'failed' WHERE transaction_id = ?
        """, (transaction_id,))
        
        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
