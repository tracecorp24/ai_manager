"""
NautiGraph TR — Model Context Protocol (MCP) Sunucusu
Bu sunucu, AI asistanının (Antigravity) NautiGraph TR platformu,
toplayıcı kuyruk motoru ve kimlik grafiği veritabanı ile iki yönlü
iletişim kurmasını sağlar.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "business_manager.db"
API_BASE = "http://127.0.0.1:8765"

from mcp.server.mcpserver import MCPServer

mcp = MCPServer(name="nautigraph-manager")


def _get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA busy_timeout = 30000")
    return db


def _http_get(path: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.urlopen(f"{API_BASE}{path}", timeout=2.0)
        return json.loads(req.read().decode("utf-8"))
    except Exception:
        return None


def _http_post(path: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    try:
        body = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=3.0)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    name="nautigraph_get_status",
    description="NautiGraph toplayıcı motorunun canlı durumunu, 5 ülkedeki aktif worker yuvalarını (TR, DE, FR, NL, UK), anlık çekilen firma sayılarını ve kuyruk özetini döner."
)
def nautigraph_get_status() -> str:
    # Önce canlı web sunucusunu sorgula
    live = _http_get("/api/crawler/status")
    if live:
        return json.dumps(live, ensure_ascii=False, indent=2)

    # Sunucu kapalıysa veritabanından durum derle
    try:
        with _get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM crawler_jobs").fetchone()[0]
            completed = db.execute("SELECT COUNT(*) FROM crawler_jobs WHERE status = 'completed'").fetchone()[0]
            running = db.execute("SELECT COUNT(*) FROM crawler_jobs WHERE status = 'running'").fetchone()[0]
            queued = db.execute("SELECT COUNT(*) FROM crawler_jobs WHERE status = 'queued'").fetchone()[0]
            crawled = db.execute("SELECT COALESCE(SUM(crawled_count), 0) FROM crawler_jobs").fetchone()[0]
            recent = [dict(r) for r in db.execute("SELECT * FROM crawler_jobs ORDER BY started_at DESC LIMIT 5").fetchall()]

        fallback = {
            "is_running": running > 0,
            "status_text": "Web sunucusu çevrimdışı, SQLite doğrudan okundu.",
            "queue_stats": {
                "total": total,
                "completed": completed,
                "running": running,
                "queued": queued,
                "total_quota": total * 100
            },
            "total_crawled_in_db": crawled,
            "recent_jobs": recent
        }
        return json.dumps(fallback, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Veritabanına erişilemedi: {e}"}, ensure_ascii=False)


@mcp.tool(
    name="nautigraph_get_queue",
    description="125 görevlik Master Toplayıcı Kuyruğunu listeler. Ülke (Türkiye, Almanya, Fransa, Hollanda, İngiltere) veya duruma (running, queued, completed) göre filtrelenebilir."
)
def nautigraph_get_queue(country: Optional[str] = None, status: Optional[str] = None, limit: int = 25) -> str:
    params = []
    sql = "SELECT id, country, city, industry, status, target_count, crawled_count, new_count, message FROM crawler_jobs WHERE 1=1"
    if country and country != "Tümü":
        sql += " AND country = ?"
        params.append(country)
    if status and status != "Tümü":
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY CASE status WHEN 'running' THEN 1 WHEN 'queued' THEN 2 ELSE 3 END, id ASC LIMIT ?"
    params.append(limit)

    try:
        with _get_db() as db:
            rows = [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]
            stats_row = db.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) as running,
                    SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) as queued
                FROM crawler_jobs
            """).fetchone()

        result = {
            "stats": dict(stats_row),
            "jobs_count": len(rows),
            "jobs": rows
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool(
    name="nautigraph_start_parallel_crawler",
    description="5 Ülke (TR, DE, FR, NL, UK) hattında 5x eşzamanlı paralel tarama havuzunu (Multi-Worker Pool) başlatır."
)
def nautigraph_start_parallel_crawler(delay_sec: float = 1.2) -> str:
    res = _http_post("/api/crawler/queue/start-parallel", {"delay_sec": delay_sec})
    if res:
        return json.dumps(res, ensure_ascii=False, indent=2)
    return json.dumps({"error": "Web sunucusuna bağlanılamadı. Lütfen sunucunun (http://127.0.0.1:8765) çalıştığından emin olun."}, ensure_ascii=False)


@mcp.tool(
    name="nautigraph_stop_crawler",
    description="Çalışan tüm toplayıcı iş parçacıklarını ve paralel worker havuzunu anında ve güvenle duraklatır."
)
def nautigraph_stop_crawler() -> str:
    res = _http_post("/api/crawler/stop")
    if res:
        return json.dumps(res, ensure_ascii=False, indent=2)
    return json.dumps({"error": "Durdurma sinyali gönderilemedi. Sunucu çevrimdışı olabilir."}, ensure_ascii=False)


@mcp.tool(
    name="nautigraph_run_job",
    description="Master kuyruktaki belirli bir görevi (örn. 'job-001') bağımsız olarak başlatır."
)
def nautigraph_run_job(job_id: str, delay_sec: float = 1.5) -> str:
    res = _http_post("/api/crawler/queue/run-job", {"job_id": job_id, "delay_sec": delay_sec})
    if res:
        return json.dumps(res, ensure_ascii=False, indent=2)
    return json.dumps({"error": "Görev tetiklenemedi."}, ensure_ascii=False)


@mcp.tool(
    name="nautigraph_get_companies",
    description="Veritabanında toplanmış olan B2B denizcilik ve yat tasarım şirketlerini listeler. Ülke, şehir, sektör veya arama kelimesine göre filtrelenebilir."
)
def nautigraph_get_companies(country: Optional[str] = None, search: Optional[str] = None, limit: int = 15) -> str:
    params = []
    sql = "SELECT id, vkn, mersis_no, legal_name, short_name, country, province, district, industry_sector, trust_score, icp_score, domain FROM companies WHERE merged_into IS NULL"
    if country and country != "Tümü":
        sql += " AND country = ?"
        params.append(country)
    if search:
        sql += " AND (legal_name LIKE ? OR short_name LIKE ? OR province LIKE ? OR industry_sector LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    try:
        with _get_db() as db:
            rows = [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]
            total = db.execute("SELECT COUNT(*) FROM companies WHERE merged_into IS NULL").fetchone()[0]

        return json.dumps({"total_companies": total, "returned": len(rows), "companies": rows}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool(
    name="nautigraph_execute_query",
    description="NautiGraph SQLite veritabanında salt-okunur (SELECT) SQL sorgusu çalıştırır. Derinlemesine istatistik veya özel analizler için kullanılır."
)
def nautigraph_execute_query(sql_query: str) -> str:
    clean = sql_query.strip()
    if not clean.upper().startswith("SELECT"):
        return json.dumps({"error": "Yalnızca SELECT sorguları çalıştırılabilir."}, ensure_ascii=False)

    try:
        with _get_db() as db:
            cur = db.execute(clean)
            rows = [dict(r) for r in cur.fetchall()]
        return json.dumps({"count": len(rows), "rows": rows[:50]}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
