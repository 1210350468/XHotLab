import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .config import DB_FILE


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def connection():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_FILE, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=15000')
        with db:
            yield db
    finally:
        db.close()


def initialize() -> None:
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript("""
        CREATE TABLE IF NOT EXISTS trends (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL,
            url TEXT NOT NULL, source TEXT NOT NULL, category TEXT NOT NULL,
            published_at TEXT NOT NULL, seen_at TEXT NOT NULL,
            volume INTEGER NOT NULL, score INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trend_score ON trends(score DESC, published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_trend_category ON trends(category);
        CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY, trend_id TEXT NOT NULL, title TEXT NOT NULL,
            content TEXT NOT NULL, style TEXT NOT NULL, language TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(trend_id) REFERENCES trends(id)
        );
        CREATE TABLE IF NOT EXISTS fetch_log (
            source TEXT PRIMARY KEY, status TEXT NOT NULL, count INTEGER NOT NULL,
            detail TEXT NOT NULL, checked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS browser_queue (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','opened','recorded','skipped')),
            post_url TEXT,
            created_at TEXT NOT NULL,
            opened_at TEXT,
            finished_at TEXT,
            FOREIGN KEY(draft_id) REFERENCES drafts(id)
        );
        CREATE INDEX IF NOT EXISTS idx_browser_queue ON browser_queue(status, created_at);
        CREATE TABLE IF NOT EXISTS creator_profile (
            id INTEGER PRIMARY KEY CHECK(id=1),
            content TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            model TEXT NOT NULL, effort TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_messages ON conversation_messages(conversation_id, created_at);
        CREATE TABLE IF NOT EXISTS llm_usage (
            id TEXT PRIMARY KEY,
            model TEXT NOT NULL, purpose TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cost_usd REAL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_jobs (
            id TEXT PRIMARY KEY, provider TEXT NOT NULL, connection TEXT NOT NULL,
            model TEXT, effort TEXT NOT NULL, mode TEXT NOT NULL,
            task TEXT NOT NULL, workdir TEXT NOT NULL,
            status TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            started_at TEXT, finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS creative_packs (
            id TEXT PRIMARY KEY, trend_id TEXT NOT NULL UNIQUE,
            draft_id TEXT NOT NULL UNIQUE, headline TEXT NOT NULL,
            hook TEXT NOT NULL, source_url TEXT NOT NULL,
            image_directory TEXT NOT NULL, model TEXT NOT NULL,
            cost_usd REAL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS creative_runs (
            id TEXT PRIMARY KEY, status TEXT NOT NULL,
            started_at TEXT NOT NULL, finished_at TEXT,
            produced INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS trend_media (
            id TEXT PRIMARY KEY,
            trend_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('photo','video','animated_gif')),
            source_url TEXT NOT NULL,
            preview_url TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            cached_file TEXT,
            imported_at TEXT,
            FOREIGN KEY(trend_id) REFERENCES trends(id)
        );
        CREATE INDEX IF NOT EXISTS idx_trend_media_post ON trend_media(trend_id);
        CREATE TABLE IF NOT EXISTS queue_media (
            queue_id TEXT NOT NULL,
            media_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY(queue_id,media_id),
            FOREIGN KEY(queue_id) REFERENCES browser_queue(id)
        );
        CREATE TABLE IF NOT EXISTS uploaded_media (
            id TEXT PRIMARY KEY,
            queue_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            cached_file TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(queue_id) REFERENCES browser_queue(id)
        );
        CREATE INDEX IF NOT EXISTS idx_uploaded_media_queue ON uploaded_media(queue_id);
        CREATE TABLE IF NOT EXISTS douyin_video_candidates (
            id TEXT PRIMARY KEY,
            job_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            description TEXT NOT NULL,
            author_name TEXT NOT NULL,
            like_count INTEGER NOT NULL,
            comment_count INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            cover_url TEXT NOT NULL,
            video_file TEXT,
            queue_id TEXT,
            scheduled_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_douyin_video_job
            ON douyin_video_candidates(job_id,like_count DESC);
        CREATE INDEX IF NOT EXISTS idx_douyin_video_schedule
            ON douyin_video_candidates(scheduled_at);
        CREATE TABLE IF NOT EXISTS browser_prep_jobs (
            id TEXT PRIMARY KEY,
            queue_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN (
                'queued','running','waiting_login','ready','closed','failed'
            )),
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(queue_id) REFERENCES browser_queue(id)
        );
        CREATE INDEX IF NOT EXISTS idx_browser_prep_jobs ON browser_prep_jobs(queue_id,created_at DESC);
        """)
        candidate_columns = {
            row['name'] for row in db.execute(
                'PRAGMA table_info(douyin_video_candidates)')
        }
        if 'rights_evidence' in candidate_columns:
            db.execute(
                'ALTER TABLE douyin_video_candidates DROP COLUMN rights_evidence')
        if 'rights_status' in candidate_columns:
            db.execute(
                'ALTER TABLE douyin_video_candidates DROP COLUMN rights_status')
        db.execute("""INSERT OR IGNORE INTO creator_profile(id,content,enabled,updated_at)
            VALUES(1,?,1,?)""", (
            '创作目标：经营中文 X 账号，追踪 X 中文社区近期热门原帖及真实讨论。'
            '优先使用已有的低成本模型 API，形成原创观点并保留原帖来源。'
            '稿件先审核，再通过 X 官方网页发布。'
            '交互偏好：中文界面、明确展示成本和任务状态。',
            now(),
        ))
        db.execute("""UPDATE trends SET category='douyin_video'
            WHERE id LIKE 'douyin:%' AND category='x_zh_douyin_video'""")


def save_trends(items: list[dict]) -> int:
    with connection() as db:
        for item in items:
            db.execute("""INSERT INTO trends
              (id,title,summary,url,source,category,published_at,seen_at,volume,score)
              VALUES (:id,:title,:summary,:url,:source,:category,:published_at,:seen_at,:volume,:score)
              ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                 summary=excluded.summary, volume=excluded.volume, score=excluded.score,
                 category=excluded.category,source=excluded.source,url=excluded.url,
                 published_at=excluded.published_at, seen_at=excluded.seen_at""", item)
    return len(items)


def upsert_douyin_candidates(items: list[dict]) -> int:
    with connection() as db:
        for item in items:
            value = {**item, 'created_at': now(), 'updated_at': now()}
            db.execute("""INSERT INTO douyin_video_candidates
                (id,job_id,content_id,source_url,description,author_name,
                like_count,comment_count,published_at,cover_url,created_at,updated_at)
                VALUES (:id,:job_id,:content_id,:source_url,:description,:author_name,
                :like_count,:comment_count,:published_at,:cover_url,
                :created_at,:updated_at)
                ON CONFLICT(id) DO UPDATE SET
                job_id=excluded.job_id,content_id=excluded.content_id,
                source_url=excluded.source_url,
                description=excluded.description,
                author_name=excluded.author_name,
                like_count=excluded.like_count,
                comment_count=excluded.comment_count,
                published_at=excluded.published_at,
                cover_url=excluded.cover_url,
                updated_at=excluded.updated_at""", value)
    return len(items)


def douyin_candidates() -> list[dict]:
    with connection() as db:
        return [dict(item) for item in db.execute("""
            SELECT v.*,q.status AS queue_status FROM douyin_video_candidates v
            LEFT JOIN browser_queue q ON q.id=v.queue_id
            ORDER BY CASE WHEN v.scheduled_at IS NOT NULL THEN 0 ELSE 1 END,
            v.scheduled_at ASC,v.like_count DESC LIMIT 150
        """)]


def get_douyin_candidate(candidate_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM douyin_video_candidates WHERE id=?',
                         (candidate_id,)).fetchone()
        return dict(row) if row else None


def schedule_douyin_candidate(candidate_id: str, queue_id: str,
                              scheduled_at: str) -> dict:
    with connection() as db:
        row = db.execute('SELECT queue_id FROM douyin_video_candidates WHERE id=?',
                         (candidate_id,)).fetchone()
        if row is None:
            raise LookupError('抖音候选视频不存在')
        if row['queue_id'] and row['queue_id'] != queue_id:
            raise ValueError('这条抖音视频已经进入发布安排')
        db.execute("""UPDATE douyin_video_candidates
            SET queue_id=?,scheduled_at=?,updated_at=? WHERE id=?""",
            (queue_id, scheduled_at, now(), candidate_id))
    return get_douyin_candidate(candidate_id)


def set_douyin_video_file(candidate_id: str, video_file: str) -> dict:
    with connection() as db:
        updated = db.execute("""UPDATE douyin_video_candidates
            SET video_file=?,updated_at=? WHERE id=?""",
            (video_file, now(), candidate_id))
        if updated.rowcount != 1:
            raise LookupError('抖音视频候选不存在')
    return get_douyin_candidate(candidate_id)


def save_trend_media(items: list[dict]) -> int:
    with connection() as db:
        for item in items:
            db.execute("""INSERT INTO trend_media
                (id,trend_id,kind,source_url,preview_url,width,height,cached_file,imported_at)
                VALUES (:id,:trend_id,:kind,:source_url,:preview_url,:width,:height,NULL,NULL)
                ON CONFLICT(id) DO UPDATE SET preview_url=excluded.preview_url,
                    width=excluded.width,height=excluded.height""", item)
    return len(items)


def trend_media(trend_id: str) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT * FROM trend_media WHERE trend_id=?
            ORDER BY CASE kind WHEN 'photo' THEN 0 ELSE 1 END,id LIMIT 12
        """, (trend_id,))]


def update_cached_media(media_id: str, relative_file: str) -> None:
    with connection() as db:
        updated = db.execute("""UPDATE trend_media SET cached_file=?,imported_at=?
            WHERE id=?""", (relative_file, now(), media_id))
        if updated.rowcount != 1:
            raise ValueError('无法登记原帖媒体文件')


def queue_media_ids(queue_id: str) -> list[str]:
    with connection() as db:
        return [row['media_id'] for row in db.execute("""
            SELECT media_id FROM queue_media WHERE queue_id=?
            ORDER BY position ASC
        """, (queue_id,))]


def add_uploaded_media(queue_id: str, name: str, relative_file: str) -> dict:
    row = {
        'id': str(uuid4()), 'queue_id': queue_id, 'filename': name[:120],
        'cached_file': relative_file, 'created_at': now(),
    }
    with connection() as db:
        db.execute("""INSERT INTO uploaded_media
            (id,queue_id,filename,cached_file,created_at)
            VALUES (:id,:queue_id,:filename,:cached_file,:created_at)""", row)
    return row


def uploaded_media(queue_id: str) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute(
            'SELECT * FROM uploaded_media WHERE queue_id=? ORDER BY created_at,id',
            (queue_id,),
        )]


def set_queue_media_ids(queue_id: str, ids: list[str]) -> None:
    with connection() as db:
        queue = db.execute('SELECT status FROM browser_queue WHERE id=?', (queue_id,)).fetchone()
        if queue is None:
            raise LookupError('待发布内容不存在')
        if queue['status'] == 'recorded':
            raise ValueError('已登记发布的内容不能修改图片')
        db.execute('DELETE FROM queue_media WHERE queue_id=?', (queue_id,))
        for position, value in enumerate(ids):
            db.execute("""INSERT INTO queue_media(queue_id,media_id,position)
                VALUES(?,?,?)""", (queue_id, value, position))


def queue_media_info(queue_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("""SELECT q.*, d.trend_id,p.image_directory,p.id AS pack_id
            FROM browser_queue AS q
            JOIN drafts AS d ON d.id=q.draft_id
            LEFT JOIN creative_packs AS p ON p.draft_id=q.draft_id
            WHERE q.id=?""", (queue_id,)).fetchone()
        return dict(row) if row else None


def new_browser_prep_job(queue_id: str) -> dict:
    with connection() as db:
        existing = db.execute("""SELECT id FROM browser_prep_jobs
            WHERE queue_id=? AND status IN ('queued','running','waiting_login','ready')
            ORDER BY created_at DESC LIMIT 1""", (queue_id,)).fetchone()
        if existing:
            raise ValueError('这条内容已有正在使用的浏览器发布窗口')
        row = {'id': str(uuid4()), 'queue_id': queue_id,
               'status': 'queued', 'detail': '等待浏览器进程启动',
               'created_at': now(), 'updated_at': now()}
        db.execute("""INSERT INTO browser_prep_jobs
            (id,queue_id,status,detail,created_at,updated_at)
            VALUES(:id,:queue_id,:status,:detail,:created_at,:updated_at)""", row)
    return row


def get_browser_prep_job(job_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM browser_prep_jobs WHERE id=?', (job_id,)).fetchone()
        return dict(row) if row else None


def latest_browser_prep_job(queue_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("""SELECT * FROM browser_prep_jobs WHERE queue_id=?
            ORDER BY created_at DESC LIMIT 1""", (queue_id,)).fetchone()
        return dict(row) if row else None


def update_browser_prep_job(job_id: str, status: str, detail: str = '') -> None:
    with connection() as db:
        result = db.execute("""UPDATE browser_prep_jobs
            SET status=?,detail=?,updated_at=? WHERE id=?
        """, (status, detail[:3000], now(), job_id))
        if result.rowcount != 1:
            raise ValueError('浏览器发布任务不存在')


def save_fetch_status(source: str, status: str, count: int, detail: str = '') -> None:
    with connection() as db:
        db.execute("""INSERT INTO fetch_log(source,status,count,detail,checked_at)
          VALUES(?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET status=excluded.status,
          count=excluded.count,detail=excluded.detail,checked_at=excluded.checked_at""",
          (source, status, count, detail, now()))


def fetch_logs() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM fetch_log WHERE source LIKE 'X 中文社区%' ORDER BY source")]


def get_trend(trend_id: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM trends WHERE id=? AND category LIKE 'x_zh%'", (trend_id,),
        ).fetchone()
        return dict(row) if row else None


def get_creative_pack_for_trend(trend_id: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            'SELECT * FROM creative_packs WHERE trend_id=?', (trend_id,),
        ).fetchone()
        return dict(row) if row else None


def list_trends(category: str = '', search: str = '', sort: str = 'hot', limit: int = 80, offset: int = 0) -> list[dict]:
    predicates = [
        "t.category LIKE 'x_zh%'",
        "julianday(t.published_at) >= julianday('now') - 1",
        "julianday(t.published_at) <= julianday('now')",
    ]
    args: list = []
    if category and category != 'all':
        predicates.append('t.category = ?')
        args.append(category)
    if search.strip():
        predicates.append('(t.title LIKE ? OR t.summary LIKE ?)')
        args.extend([f'%{search.strip()}%', f'%{search.strip()}%'])
    where = 'WHERE ' + ' AND '.join(predicates) if predicates else ''
    ordering = ('fresh_score DESC, t.published_at DESC'
                if sort == 'hot' else 't.published_at DESC, fresh_score DESC')
    with connection() as db:
        return [dict(row) for row in db.execute(
            f"""SELECT t.*,
                ROUND(t.score / (1.0 + MAX(0.0, (julianday('now') -
                    julianday(t.published_at)) * 4.0)), 1) AS fresh_score,
                (SELECT m.preview_url FROM trend_media AS m
                 WHERE m.trend_id=t.id ORDER BY m.id LIMIT 1) AS preview_url,
                (SELECT COUNT(*) FROM trend_media AS m
                 WHERE m.trend_id=t.id) AS media_count
                FROM trends AS t {where} ORDER BY {ordering} LIMIT ? OFFSET ?""",
            (*args, min(200, max(1, limit)), max(0, offset)))]


def statistics() -> dict:
    with connection() as db:
        recent = """category LIKE 'x_zh%'
            AND julianday(published_at) >= julianday('now') - 1
            AND julianday(published_at) <= julianday('now')"""
        total = db.execute(f"SELECT COUNT(*) FROM trends WHERE {recent}").fetchone()[0]
        drafts = db.execute("""SELECT COUNT(*) FROM drafts AS d
            JOIN trends AS t ON t.id=d.trend_id WHERE t.category LIKE 'x_zh%'""").fetchone()[0]
        categories = [dict(row) for row in db.execute(
            f"""SELECT category, COUNT(*) AS count FROM trends
            WHERE {recent} GROUP BY category ORDER BY count DESC""")]
        last_seen = db.execute("SELECT MAX(seen_at) FROM trends WHERE category LIKE 'x_zh%'").fetchone()[0]
        last_checked = db.execute("""SELECT MAX(checked_at) FROM fetch_log
            WHERE source LIKE 'X 中文社区%' AND status='ok'""").fetchone()[0]
    return {'total': total, 'drafts': drafts, 'categories': categories,
            'last_seen': last_seen, 'last_checked': last_checked,
            'freshness_window_hours': 24}


def create_draft(trend: dict, content: str, style: str, language: str) -> dict:
    value = {'id': str(uuid4()), 'trend_id': trend['id'], 'title': trend['title'],
             'content': content, 'style': style, 'language': language,
             'created_at': now(), 'updated_at': now()}
    with connection() as db:
        db.execute("""INSERT INTO drafts(id,trend_id,title,content,style,language,created_at,updated_at)
            VALUES(:id,:trend_id,:title,:content,:style,:language,:created_at,:updated_at)""", value)
    return value


def list_drafts() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT d.* FROM drafts AS d JOIN trends AS t ON t.id=d.trend_id
            WHERE t.category LIKE 'x_zh%' OR t.category='douyin_video'
            ORDER BY d.updated_at DESC LIMIT 200
        """)]


def get_draft(draft_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
        return dict(row) if row else None


def queue_ids_for_draft(draft_id: str) -> list[str]:
    with connection() as db:
        return [row['id'] for row in db.execute(
            "SELECT id FROM browser_queue WHERE draft_id=? AND status!='recorded'",
            (draft_id,),
        )]


def change_draft(draft_id: str, content: str) -> bool:
    with connection() as db:
        queue_item = db.execute('SELECT status FROM browser_queue WHERE draft_id=?', (draft_id,)).fetchone()
        if queue_item and queue_item['status'] == 'recorded':
            raise ValueError('此草稿已登记发布记录')
        result = db.execute('UPDATE drafts SET content=?, updated_at=? WHERE id=?',
                            (content, now(), draft_id))
        if result.rowcount and queue_item:
            db.execute("""UPDATE browser_queue SET content=?,status='queued',
                opened_at=NULL,finished_at=NULL WHERE draft_id=?""", (content, draft_id))
        return result.rowcount > 0


def delete_draft(draft_id: str) -> bool:
    with connection() as db:
        active = db.execute("""SELECT j.id FROM browser_prep_jobs AS j
            JOIN browser_queue AS q ON q.id=j.queue_id
            WHERE q.draft_id=? AND j.status IN ('queued','running','waiting_login','ready')
            LIMIT 1""", (draft_id,)).fetchone()
        if active:
            raise ValueError('请先关闭这条草稿的 X 浏览器发布窗口')
        existing = db.execute("""SELECT id FROM browser_queue
            WHERE draft_id=? AND status!='recorded'""", (draft_id,)).fetchall()
        for row in existing:
            db.execute('DELETE FROM queue_media WHERE queue_id=?', (row['id'],))
            db.execute('DELETE FROM uploaded_media WHERE queue_id=?', (row['id'],))
            db.execute('DELETE FROM browser_prep_jobs WHERE queue_id=?', (row['id'],))
        db.execute("DELETE FROM browser_queue WHERE draft_id=? AND status!='recorded'", (draft_id,))
        return db.execute('DELETE FROM drafts WHERE id=? AND id NOT IN (SELECT draft_id FROM browser_queue)', (draft_id,)).rowcount > 0


def queue_drafts(draft_ids: list[str]) -> list[dict]:
    if not draft_ids:
        raise ValueError('请至少选择一条草稿')
    if len(draft_ids) > 50 or len(set(draft_ids)) != len(draft_ids):
        raise ValueError('一次最多选择 50 条不同草稿')
    with connection() as db:
        items = []
        for draft_id in draft_ids:
            draft = db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
            if draft is None:
                raise ValueError('待发布的草稿不存在')
            if not draft['content'].strip() or len(draft['content']) > 280:
                raise ValueError(f'草稿「{draft["title"]}」的内容长度需要在 1 到 280 个字符以内')
            existing = db.execute('SELECT * FROM browser_queue WHERE draft_id=?', (draft_id,)).fetchone()
            if existing:
                if existing['status'] == 'recorded':
                    raise ValueError('此草稿已登记发布记录')
                if existing['status'] == 'skipped':
                    db.execute("""UPDATE browser_queue SET status='queued',
                        finished_at=NULL WHERE draft_id=?""", (draft_id,))
                    existing = db.execute('SELECT * FROM browser_queue WHERE draft_id=?', (draft_id,)).fetchone()
                items.append(dict(existing))
                continue
            item = {
                'id': str(uuid4()), 'draft_id': draft_id, 'content': draft['content'],
                'status': 'queued', 'post_url': None, 'created_at': now(),
                'opened_at': None, 'finished_at': None,
            }
            db.execute("""INSERT INTO browser_queue(
                id,draft_id,content,status,post_url,created_at,opened_at,finished_at
            ) VALUES (:id,:draft_id,:content,:status,:post_url,:created_at,:opened_at,:finished_at)""", item)
            items.append(item)
    return items


def list_browser_queue() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT q.*, d.title AS title, d.trend_id AS trend_id,
                   p.id AS pack_id
            FROM browser_queue AS q JOIN drafts AS d ON d.id=q.draft_id
            JOIN trends AS t ON t.id=d.trend_id
            LEFT JOIN creative_packs AS p ON p.draft_id=d.id
            WHERE t.category LIKE 'x_zh%' OR t.category='douyin_video'
            ORDER BY CASE q.status WHEN 'queued' THEN 0 WHEN 'opened' THEN 1
                WHEN 'recorded' THEN 2 ELSE 3 END, q.created_at DESC LIMIT 300
        """)]


def change_queue_status(item_id: str, action: str, post_url: str | None = None) -> dict:
    with connection() as db:
        row = db.execute('SELECT * FROM browser_queue WHERE id=?', (item_id,)).fetchone()
        if row is None:
            raise LookupError('未找到待发布任务')
        if action == 'open':
            if row['status'] not in ('queued', 'opened'):
                raise ValueError('任务状态已结束，请查看发布记录')
            db.execute("UPDATE browser_queue SET status='opened',opened_at=? WHERE id=?", (now(), item_id))
        elif action == 'record':
            if row['status'] != 'opened':
                raise ValueError('请先打开 X 官方编辑器')
            if not post_url:
                raise ValueError('请提供已经发布的实际帖子链接')
            db.execute("""UPDATE browser_queue SET status='recorded',post_url=?,finished_at=?
                WHERE id=?""", (post_url, now(), item_id))
        elif action == 'skip':
            if row['status'] not in ('queued', 'opened'):
                raise ValueError('此任务已经结束')
            db.execute("UPDATE browser_queue SET status='skipped',finished_at=? WHERE id=?", (now(), item_id))
        elif action == 'requeue':
            if row['status'] not in ('opened', 'skipped'):
                raise ValueError('只能将已打开或跳过的任务重新加入队列')
            db.execute("""UPDATE browser_queue SET status='queued',
                opened_at=NULL,finished_at=NULL WHERE id=?""", (item_id,))
        else:
            raise ValueError('未知操作')
        return dict(db.execute('SELECT * FROM browser_queue WHERE id=?', (item_id,)).fetchone())


def delete_queue_item(item_id: str) -> bool:
    with connection() as db:
        active = db.execute("""SELECT id FROM browser_prep_jobs
            WHERE queue_id=? AND status IN ('queued','running','waiting_login','ready')
            LIMIT 1""", (item_id,)).fetchone()
        if active:
            raise ValueError('请先关闭 X 浏览器发布窗口')
        db.execute('DELETE FROM queue_media WHERE queue_id=?', (item_id,))
        db.execute('DELETE FROM uploaded_media WHERE queue_id=?', (item_id,))
        db.execute('DELETE FROM browser_prep_jobs WHERE queue_id=?', (item_id,))
        return db.execute("DELETE FROM browser_queue WHERE id=? AND status!='recorded'", (item_id,)).rowcount > 0


def profile() -> dict:
    with connection() as db:
        row = db.execute('SELECT * FROM creator_profile WHERE id=1').fetchone()
        return dict(row)


def save_profile(content: str, enabled: bool) -> dict:
    with connection() as db:
        db.execute("UPDATE creator_profile SET content=?, enabled=?, updated_at=? WHERE id=1",
                   (content.strip(), int(enabled), now()))
    return profile()


def new_conversation(model: str, effort: str) -> dict:
    value = {'id': str(uuid4()), 'title': '新对话', 'model': model, 'effort': effort,
             'created_at': now(), 'updated_at': now()}
    with connection() as db:
        db.execute("""INSERT INTO conversations(id,title,model,effort,created_at,updated_at)
            VALUES(:id,:title,:model,:effort,:created_at,:updated_at)""", value)
    return value


def conversations() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute(
            'SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 150')]


def get_conversation(conversation_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM conversations WHERE id=?', (conversation_id,)).fetchone()
        return dict(row) if row else None


def conversation_messages(conversation_id: str) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT * FROM conversation_messages WHERE conversation_id=?
            ORDER BY created_at ASC, rowid ASC LIMIT 250
        """, (conversation_id,))]


def delete_conversation(conversation_id: str) -> bool:
    with connection() as db:
        db.execute('DELETE FROM conversation_messages WHERE conversation_id=?', (conversation_id,))
        return db.execute('DELETE FROM conversations WHERE id=?', (conversation_id,)).rowcount > 0


def append_exchange(conversation_id: str, user_content: str, assistant_content: str,
                    model: str, effort: str) -> None:
    with connection() as db:
        for role, content in (('user', user_content), ('assistant', assistant_content)):
            db.execute("""INSERT INTO conversation_messages(id,conversation_id,role,content,created_at)
                VALUES(?,?,?,?,?)""", (str(uuid4()), conversation_id, role, content, now()))
        previous = db.execute('SELECT title FROM conversations WHERE id=?', (conversation_id,)).fetchone()
        title = user_content.strip()[:56] if previous['title'] == '新对话' else previous['title']
        db.execute("""UPDATE conversations SET title=?,model=?,effort=?,updated_at=? WHERE id=?""",
                   (title, model, effort, now(), conversation_id))


def recent_user_content(limit: int = 45) -> list[str]:
    with connection() as db:
        return [row['content'] for row in db.execute("""
            SELECT content FROM conversation_messages WHERE role='user'
            ORDER BY created_at DESC, rowid DESC LIMIT ?
        """, (limit,))]


def save_usage(model: str, purpose: str, usage: dict) -> None:
    with connection() as db:
        db.execute("""INSERT INTO llm_usage
            (id,model,purpose,input_tokens,output_tokens,cost_usd,created_at)
            VALUES(?,?,?,?,?,?,?)""", (
            str(uuid4()), model, purpose, usage.get('input_tokens', 0),
            usage.get('output_tokens', 0), usage.get('cost_usd'), now(),
        ))


def usage_summary() -> dict:
    with connection() as db:
        row = db.execute("""SELECT COUNT(*) AS requests, SUM(cost_usd) AS total_cost,
            SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens
            FROM llm_usage""").fetchone()
    return {'requests': row['requests'], 'total_cost_usd': row['total_cost'],
            'input_tokens': row['input_tokens'], 'output_tokens': row['output_tokens']}


def new_agent_job(provider: str, connection_type: str, model: str | None,
                  effort: str, mode: str, task: str, workdir: str) -> dict:
    value = {'id': str(uuid4()), 'provider': provider, 'connection': connection_type,
             'model': model, 'effort': effort, 'mode': mode, 'task': task,
             'workdir': workdir, 'status': 'queued',
             'created_at': now(), 'started_at': None, 'finished_at': None,
             'result': '', 'error': ''}
    with connection() as db:
        db.execute("""INSERT INTO agent_jobs
            (id,provider,connection,model,effort,mode,task,workdir,
             status,created_at,started_at,finished_at,result,error)
             VALUES(:id,:provider,:connection,:model,:effort,:mode,:task,:workdir,
             :status,:created_at,:started_at,:finished_at,:result,:error)""", value)
    return value


def get_agent_job(job_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM agent_jobs WHERE id=?', (job_id,)).fetchone()
        return dict(row) if row else None


def list_agent_jobs() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute(
            'SELECT * FROM agent_jobs ORDER BY created_at DESC LIMIT 80')]


def start_agent_job(job_id: str) -> None:
    with connection() as db:
        result = db.execute("""UPDATE agent_jobs SET status='running',started_at=?
            WHERE id=? AND status='queued'""", (now(), job_id))
        if result.rowcount != 1:
            raise ValueError('Agent 任务状态异常')


def finish_agent_job(job_id: str, status: str, result: str, error: str) -> None:
    with connection() as db:
        updated = db.execute("""UPDATE agent_jobs SET status=?,result=?,error=?,finished_at=?
            WHERE id=? AND status='running'""", (status, result[:80000], error[:8000], now(), job_id))
        if updated.rowcount != 1:
            raise ValueError('Agent 任务结束状态异常')


def delete_agent_job(job_id: str) -> bool:
    with connection() as db:
        result = db.execute(
            "DELETE FROM agent_jobs WHERE id=? AND status IN ('completed','failed')",
            (job_id,),
        )
        return result.rowcount == 1


def existing_creative_trends() -> set[str]:
    with connection() as db:
        return {row['trend_id'] for row in db.execute('SELECT trend_id FROM creative_packs')}


def create_creative_pack(trend: dict, draft_id: str, headline: str, hook: str,
                         relative_directory: str, model: str, cost_usd: float | None) -> dict:
    row = {
        'id': str(uuid4()), 'trend_id': trend['id'], 'draft_id': draft_id,
        'headline': headline, 'hook': hook, 'source_url': trend['url'],
        'image_directory': relative_directory, 'model': model,
        'cost_usd': cost_usd, 'created_at': now(),
    }
    with connection() as db:
        db.execute("""INSERT INTO creative_packs
            (id,trend_id,draft_id,headline,hook,source_url,image_directory,model,cost_usd,created_at)
            VALUES(:id,:trend_id,:draft_id,:headline,:hook,:source_url,:image_directory,:model,:cost_usd,:created_at)""", row)
    return row


def creative_packs(limit: int = 100) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT p.*, d.content AS content, t.category AS category, t.source AS source
            FROM creative_packs AS p
            JOIN drafts AS d ON d.id=p.draft_id
            JOIN trends AS t ON t.id=p.trend_id
            WHERE t.category LIKE 'x_zh%'
            ORDER BY p.created_at DESC LIMIT ?
        """, (limit,))]


def get_creative_pack(pack_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM creative_packs WHERE id=?', (pack_id,)).fetchone()
        return dict(row) if row else None


def creative_cost_today() -> float:
    with connection() as db:
        row = db.execute("""SELECT COALESCE(SUM(cost_usd),0) FROM creative_packs
            WHERE created_at >= datetime('now','start of day')""").fetchone()
        return float(row[0])


def new_creative_run() -> str:
    run_id = str(uuid4())
    with connection() as db:
        db.execute("""INSERT INTO creative_runs(id,status,started_at,produced)
            VALUES(?,'running',?,0)""", (run_id, now()))
    return run_id


def finish_creative_run(run_id: str, status: str, produced: int, error: str = '') -> None:
    with connection() as db:
        db.execute("""UPDATE creative_runs SET status=?, produced=?,error=?,finished_at=?
            WHERE id=? AND status='running'""", (status, produced, error[:8000], now(), run_id))


def creative_runs() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute(
            'SELECT * FROM creative_runs ORDER BY started_at DESC LIMIT 30')]
