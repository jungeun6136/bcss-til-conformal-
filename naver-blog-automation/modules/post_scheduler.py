import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class PostScheduler:
    """
    SQLite 기반 예약 발행 큐.
    start_background() 호출 시 백그라운드 타이머가 매분 체크해서 자동 발행.
    """

    def __init__(self, db_path: str, poster):
        self.db_path = str(db_path)
        self.poster  = poster        # NaverBlogPoster 인스턴스
        self._lock   = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._init_db()

    # ── DB 초기화 ─────────────────────────────────────
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    title        TEXT    NOT NULL,
                    content      TEXT    NOT NULL,
                    images       TEXT    DEFAULT '[]',
                    keyword      TEXT    DEFAULT '',
                    scheduled_at TEXT    NOT NULL,
                    status       TEXT    DEFAULT 'pending',
                    result_msg   TEXT    DEFAULT '',
                    created_at   TEXT    NOT NULL
                )
            """)
            conn.commit()

    # ── 큐 조작 ───────────────────────────────────────
    def add(
        self,
        title: str,
        content: str,
        scheduled_at: datetime,
        images: List[str] = [],
        keyword: str = "",
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO queue (title, content, images, keyword, scheduled_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    title,
                    content,
                    json.dumps(images, ensure_ascii=False),
                    keyword,
                    scheduled_at.isoformat(),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return cur.lastrowid

    def get_all(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM queue ORDER BY scheduled_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_pending(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM queue WHERE status='pending' ORDER BY scheduled_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def cancel(self, post_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE queue SET status='cancelled' WHERE id=? AND status='pending'",
                (post_id,),
            )
            conn.commit()

    def delete(self, post_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM queue WHERE id=?", (post_id,))
            conn.commit()

    def counts(self) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as n FROM queue GROUP BY status"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def _set_status(self, post_id: int, status: str, msg: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE queue SET status=?, result_msg=? WHERE id=?",
                (status, msg, post_id),
            )
            conn.commit()

    # ── 발행 체크 ─────────────────────────────────────
    def check_and_post(self, naver_id: str = ""):
        """발행 시간이 된 pending 항목을 순서대로 처리 (하루 한도 고려)"""
        with self._lock:
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                due = conn.execute(
                    "SELECT * FROM queue "
                    "WHERE status='pending' AND scheduled_at <= ? "
                    "ORDER BY scheduled_at LIMIT 3",
                    (now,),
                ).fetchall()

            for row in due:
                item = dict(row)

                if not self.poster.can_post():
                    self._set_status(item["id"], "failed", "일일 발행 한도 초과 — 내일 재시도")
                    continue

                images = json.loads(item.get("images", "[]"))
                ok, msg = self.poster.post(
                    title=item["title"],
                    content=item["content"],
                    images=images,
                    naver_id=naver_id,
                )
                self._set_status(item["id"], "done" if ok else "failed", msg)

    # ── 백그라운드 타이머 ─────────────────────────────
    def start_background(self, naver_id: str = "", interval_sec: int = 60):
        """앱이 실행 중인 동안 매 interval_sec 초마다 큐를 체크"""
        self.check_and_post(naver_id)
        self._timer = threading.Timer(
            interval_sec, self.start_background, args=[naver_id, interval_sec]
        )
        self._timer.daemon = True
        self._timer.start()

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def is_running(self) -> bool:
        return self._timer is not None and self._timer.is_alive()
