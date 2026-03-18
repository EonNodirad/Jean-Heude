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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    user_id TEXT,
                    model TEXT,
                    tokens_in INTEGER DEFAULT 0,
                    tokens_out INTEGER DEFAULT 0,
                    latency_ms INTEGER DEFAULT 0,
                    tool_name TEXT,
                    event_type TEXT,
                    error TEXT
                )""")
            # Migrations colonnes legacy
            for col, definition in [("image", "TEXT")]:
                try:
                    await db.execute(f"ALTER TABLE memory_chat ADD COLUMN {col} {definition}")
                except Exception:
                    pass
            await db.commit()

    async def log_metric(self, user_id: str, model: str = "", tokens_in: int = 0,
                         tokens_out: int = 0, latency_ms: int = 0,
                         tool_name: str = "", event_type: str = "inference", error: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO metrics (user_id, model, tokens_in, tokens_out, latency_ms, tool_name, event_type, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, model, tokens_in, tokens_out, latency_ms, tool_name or None, event_type, error or None)
            )
            await db.commit()

    async def get_metrics_summary(self, hours: int = 24) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            since = f"datetime('now', '-{hours} hours')"
            async with db.execute(f"""
                SELECT
                    COUNT(*) as total_requests,
                    SUM(tokens_in + tokens_out) as total_tokens,
                    AVG(latency_ms) as avg_latency_ms,
                    SUM(CASE WHEN error IS NOT NULL AND error != '' THEN 1 ELSE 0 END) as error_count,
                    model,
                    COUNT(*) as model_count
                FROM metrics
                WHERE timestamp >= {since} AND event_type = 'inference'
                GROUP BY model
                ORDER BY model_count DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_all_sessions(self, limit: int = 100) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT h.id, h.userID, h.resume, h.timestamp,
                          COUNT(m.id) as message_count
                   FROM historique_chat h
                   LEFT JOIN memory_chat m ON m.sessionID = h.id
                   GROUP BY h.id
                   ORDER BY h.timestamp DESC
                   LIMIT ?""",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_active_sessions_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(DISTINCT userID) FROM historique_chat WHERE timestamp >= datetime('now', '-1 hour')"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_history_list(self, user_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, resume, timestamp FROM historique_chat WHERE userID = ? ORDER BY timestamp DESC", (user_id,)) as cursor:
                lignes = await cursor.fetchall()
                return [{"id": ligne["id"], "resume": ligne["resume"], "timestamp": ligne["timestamp"]} for ligne in lignes]

    async def check_session_owner(self, session_id: int, user_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM historique_chat WHERE id = ? AND userID = ?",
                (session_id, user_id)
            ) as cursor:
                return await cursor.fetchone() is not None

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
