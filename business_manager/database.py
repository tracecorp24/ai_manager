from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "business_manager.db"
SCHEMA_PATH = ROOT / "schema.sql"
LEGACY_JSON = ROOT / "frontend" / "musteri_listesi.json"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _repair(value: Any) -> Any:
    if not isinstance(value, str) or "Ã" not in value and "Ä" not in value:
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def initialise() -> None:
    with connect() as db:
        db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        company_count = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        if company_count == 0 and LEGACY_JSON.exists():
            try:
                rows = json.loads(LEGACY_JSON.read_text(encoding="utf-8"))
                for row in rows:
                    name = _repair(row.get("Ünvan") or row.get("Ãœnvan") or "İsimsiz şirket")
                    reg = row.get("Sicil No") or row.get("sicil_no")
                    address = _repair(row.get("Adres", ""))
                    district = _repair(row.get("İlçe") or row.get("Ä°lÃ§e") or "")
                    status = _repair(row.get("Durum", "Faal"))
                    db.execute(
                        "INSERT OR IGNORE INTO companies(registration_no,name,address,district,status) VALUES(?,?,?,?,?)",
                        (str(reg) if reg else None, name, address, district, status),
                    )
            except (OSError, ValueError, TypeError):
                pass
        _seed_demo(db)
        db.commit()


def _seed_demo(db: sqlite3.Connection) -> None:
    demos = [
        ("BM-DEMO-01", "Arven Makine Teknolojileri", "İstanbul", "Makine"),
        ("BM-DEMO-02", "Kuzey Kalıp Sistemleri", "Kocaeli", "Kalıp"),
        ("BM-DEMO-03", "Nova Otomasyon", "Ankara", "Otomasyon"),
        ("BM-DEMO-04", "Eksen Endüstriyel Tasarım", "Bursa", "Tasarım"),
        ("BM-DEMO-05", "MaviHat Yazılım", "İzmir", "Yazılım"),
        ("BM-DEMO-06", "Pera Robotik", "İstanbul", "Robotik"),
        ("BM-DEMO-07", "Atlas Prototip", "Eskişehir", "Prototip"),
        ("BM-DEMO-08", "Rota Enerji Sistemleri", "Konya", "Enerji"),
        ("BM-DEMO-09", "Beyaz Metal Sanayi", "Tekirdağ", "Metal"),
        ("BM-DEMO-10", "Vizyon Mühendislik", "Sakarya", "Mühendislik"),
    ]
    for i, (reg, name, city, sector) in enumerate(demos, 1):
        db.execute(
            "INSERT OR IGNORE INTO companies(registration_no,name,district,status,sector,email) VALUES(?,?,?,?,?,?)",
            (reg, name, city, "Faal", sector, f"info{i}@businessdemo.local"),
        )
    demo_companies = [r[0] for r in db.execute("SELECT id FROM companies WHERE registration_no LIKE 'BM-DEMO-%' ORDER BY id").fetchall()]
    titles = [
        "Kıdemli Makine Tasarım Mühendisi", "CNC Kalıp Uzmanı", "PLC Otomasyon Mühendisi",
        "Endüstriyel Ürün Tasarımcısı", "Full Stack Geliştirici", "Robotik Sistem Mühendisi",
        "Prototip Üretim Teknisyeni", "Enerji Sistemleri Proje Uzmanı", "Metal Üretim Sorumlusu",
        "Teklif ve Proje Mühendisi",
    ]
    for company_id, title in zip(demo_companies, titles):
        exists = db.execute("SELECT 1 FROM job_postings WHERE company_id=? AND title=?", (company_id, title)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO job_postings(company_id,title,location,work_type,description,requirements,salary) VALUES(?,?,?,?,?,?,?)",
                (company_id, title, "Türkiye", "Tam Zamanlı", f"{title} pozisyonu için deneyimli ekip arkadaşı arıyoruz.", "İlgili bölüm mezuniyeti, ekip çalışması ve proje deneyimi.", "₺45.000 - ₺75.000"),
            )


def rows(query: str, params: tuple = ()) -> list[dict]:
    with connect() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]
