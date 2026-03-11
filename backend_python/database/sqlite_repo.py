import aiosqlite
import os

class SQLiteRepo:
    def __init__(self, db_path: str = "memory/memoire.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS historique_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TIMESTAMP, resume TEXT, userID TEXT)")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS long_term_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_text TEXT,
                    vector_id TEXT
                )""")
            try:
                await db.execute("ALTER TABLE memory_chat ADD COLUMN image TEXT")
            except Exception:
                pass
            await db.commit()

    async def get_history_list(self, user_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, resume, timestamp FROM historique_chat WHERE userID = ? ORDER BY timestamp DESC", (user_id,)) as cursor:
                lignes = await cursor.fetchall()
                return [{"id": ligne["id"], "resume": ligne["resume"], "timestamp": ligne["timestamp"]} for ligne in lignes]

    async def get_history(self, session_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT role, content, image FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC", (session_id,)) as cursor:
                lignes = await cursor.fetchall()
                return [{"role": ligne["role"], "content": ligne["content"], "image": ligne["image"]} for ligne in lignes]

    async def create_session(self, resume: str, user_id: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                (resume, user_id)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_recent_memory_chat(self, session_id: int, limit: int = 20):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            ) as cursor:
                lignes = await cursor.fetchall()
                return [{"role": m[0], "content": m[1]} for m in reversed(list(lignes))]

    async def add_memory_chat(self, role: str, content: str, session_id: int, image_path: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO memory_chat (role, content, timestamp, sessionID, image) VALUES (?, ?, datetime('now'), ?, ?)",
                (role, content, session_id, image_path)
            )
            await db.commit()

    async def search_keyword_memory(self, keywords: list[str]) -> list[str]:
        if not keywords:
            return []
        sql_query = "SELECT chunk_text FROM long_term_index WHERE " + " OR ".join(["chunk_text LIKE ?"] * len(keywords))
        params = [f"%{k}%" for k in keywords]
        
        memories_list = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql_query, params) as cursor:
                k_results = await cursor.fetchall()
                for row in k_results:
                    if row[0] not in memories_list:
                        memories_list.append(row[0])
        return memories_list

    async def clear_long_term_index(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM long_term_index")
            await db.commit()

    async def add_long_term_index(self, chunk_text: str, vector_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO long_term_index (chunk_text, vector_id) VALUES (?, ?)", (chunk_text, vector_id))
            await db.commit()
