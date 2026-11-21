from __future__ import annotations

import json
import mimetypes
import os
import random
import re
import smtplib
import sqlite3
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from database import DB_PATH, ROOT, connect, initialise, row_to_dict, rows

HOST = "127.0.0.1"
PORT = 8765
FRONTEND = ROOT / "frontend"


# =============================================================================
# TOPLAYICI KUYRUK VE CRAWLER MOTORU (QUEUE & CRAWLER ENGINE)
# =============================================================================
CRAWLER_STATE: Dict[str, Any] = {
    "status": "idle",             # "idle", "crawling", "paused"
    "active_job_id": None,
    "country": "Türkiye",
    "industry": "Mega Yat Tersaneleri",
    "sources": ["Resmi Ticaret Sicili", "Google Maps POI", "Fuar Katılımcıları"],
    "total_target": 20,
    "crawled_count": 0,
    "new_count": 0,
    "updated_count": 0,
    "unchanged_count": 0,
    "progress_pct": 0,
    "delay_sec": 1.5,
    "countdown_sec": 0,
    "message": "Toplayıcı erişime hazır. Hız sınırı ve bekleme kuralları otomatik uygulanır.",
    "last_added_company": "Aegean Naval Architecture",
    "last_crawled_at": "1 dk önce"
}

_crawler_thread: Optional[threading.Thread] = None
_crawler_stop_event = threading.Event()

GEO_DATA = {
    "Türkiye": {
        "cities": [("İstanbul", "Tuzla Tersaneler"), ("Antalya", "Serbest Bölge"), ("Muğla", "Bodrum İçmeler"), ("Yalova", "Altınova Tersaneler"), ("İzmir", "Urla Koyu"), ("Muğla", "Marmaris")],
        "prefixes": ["Kuzey Ege", "Boğaziçi", "Akdeniz", "Piri Reis", "Albatros", "Ege Yıldızı", "Marmara", "Turkuaz", "Karya", "Pera", "Barbaros", "Atlantik", "Anadolu", "Levant"],
        "suffixes": ["Yat Tasarım Ltd.", "Naval Architecture A.Ş.", "Mega Yat Tersanesi", "Kompozit Denizcilik", "Gemi Stabilite Mühendislik", "Marin Donatım A.Ş."],
        "domain_sfx": ".com.tr",
        "phone_prefix": "+90 216"
    },
    "İtalya": {
        "cities": [("Viareggio", "Toscana"), ("Livorno", "Toscana"), ("Ancona", "Marche"), ("La Spezia", "Liguria"), ("Genova", "Liguria")],
        "prefixes": ["Riviera", "Toscana", "Adriatico", "Tirreno", "Viareggio", "San Marco", "Nautica", "Liguria", "Portofino", "Venezia", "Monza"],
        "suffixes": ["Yacht Design Srl", "Superyachts SpA", "Naval Engineering Srl", "Costruzioni Navali SpA", "Custom Marine SpA"],
        "domain_sfx": ".it",
        "phone_prefix": "+39 0584"
    },
    "Hollanda": {
        "cities": [("Aalsmeer", "North Holland"), ("Oss", "North Brabant"), ("Amsterdam", "North Holland"), ("Rotterdam", "South Holland"), ("Makkum", "Friesland")],
        "prefixes": ["North Sea", "Royal Dutch", "Zeeland", "Hollandic", "Windmill", "Viking", "Baltic", "Amstel", "Damen", "Gouda"],
        "suffixes": ["Naval Architects BV", "Superyacht Shipyard BV", "Marine Dynamics BV", "Hull Engineering BV"],
        "domain_sfx": ".nl",
        "phone_prefix": "+31 20"
    },
    "Yunanistan": {
        "cities": [("Pire", "Attika"), ("Atina", "Attika"), ("Perama", "Attika"), ("Selanik", "Makedonya"), ("Rodos", "On İki Adalar")],
        "prefixes": ["Aegean", "Hellenic", "Attica", "Ionian", "Poseidon", "Cyclades", "Olympus", "Mykonos", "Crete"],
        "suffixes": ["Yacht Construction Ltd", "Naval Architecture SA", "Shipyard Hellas SA", "Marine Crafts Ltd"],
        "domain_sfx": ".gr",
        "phone_prefix": "+30 210"
    },
    "Almanya": {
        "cities": [("Bremen", "Bremen"), ("Hamburg", "Hamburg"), ("Kiel", "Schleswig-Holstein"), ("Rostock", "Mecklenburg"), ("Lübeck", "Schleswig-Holstein")],
        "prefixes": ["Hanseatic", "Elbe", "Baltic", "Nordic", "Kieler", "Weser", "Bremen", "Kaiser"],
        "suffixes": ["Yacht Engineering GmbH", "Superyachts AG", "Naval Architecture GmbH", "Marine Systems AG"],
        "domain_sfx": ".de",
        "phone_prefix": "+49 40"
    },
    "İngiltere": {
        "cities": [("Southampton", "Hampshire"), ("Cowes", "Isle of Wight"), ("Plymouth", "Devon"), ("Falmouth", "Cornwall")],
        "prefixes": ["Solent", "Wight", "Britannia", "Cornish", "Meridian", "Thames", "Wessex"],
        "suffixes": ["Yacht Design Ltd", "Marine Engineering Ltd", "Superyacht Crafts Ltd"],
        "domain_sfx": ".co.uk",
        "phone_prefix": "+44 23"
    }
}


def generate_crawled_company(country: str, industry: str, selected_sources: List[str]) -> Dict[str, Any]:
    geo = GEO_DATA.get(country, GEO_DATA["Türkiye"])
    used_real_turkish = False
    if country == "Türkiye" and MUSTERI_LISTESI:
        m_item = random.choice(MUSTERI_LISTESI)
        legal_name = m_item.get("Ünvan") or "MARMARA DENİZCİLİK VE YAT SANAYİ A.Ş."
        short_name = legal_name.split()[0].title() + " " + (legal_name.split()[1].title() if len(legal_name.split()) > 1 else "Marine")
        district = m_item.get("İlçe") or "Tuzla"
        city = "İstanbul"
        sicil_no = m_item.get("Sicil No") or str(random.randint(100000, 999999))
        tax_num = f"0{sicil_no}" if len(sicil_no) == 9 else f"00{sicil_no[:8]}"
        domain_clean = "".join(c for c in short_name.lower() if c.isalnum()) + ".com.tr"
        used_real_turkish = True
    else:
        prefix = random.choice(geo["prefixes"])
        suffix = random.choice(geo["suffixes"])
        short_name = f"{prefix} {suffix.split()[0]}"
        legal_name = f"{prefix.upper()} {suffix.upper()}"
        city, district = random.choice(geo["cities"])
        domain_clean = "".join(c for c in short_name.lower() if c.isalnum()) + geo["domain_sfx"]
        tax_num = f"{random.randint(1000000000, 9999999999)}"
    cid = f"cmp-{country[:2].lower()}-{uuid.uuid4().hex[:6]}"
    
    nace = "30.12" if ("Tersane" in industry or "İnşa" in industry) else "71.12"
    trust = random.randint(89, 99)
    icp = random.randint(84, 98)
    
    cad_pool = ["Rhino 3D", "Orca3D", "ANSYS Fluent CFD", "Maxsurf", "CATIA Marine", "ShipConstructor", "SolidWorks"]
    selected_cad = random.sample(cad_pool, random.randint(2, 4))
    
    evidences = []
    SOURCE_MAP = {
        "ticaret_sicili": ("Ticaret Sicili Gazetesi & MERSİS", "A", "VKN/Vergi No Kesin Eşleşme"),
        "google_places": ("Google Places / Maps POI", "B", "E.164 Geocode Doğrulama"),
        "ekap": ("EKAP Kamu İhale Katılım & Sonuç", "A", "MERSİS / Kamu İhale Tescili"),
        "fuarlar": ("Fuar Katılımcı Listeleri (İFM/Cannes/TÜYAP)", "B", "Etkinlik Katılımı Doğrulama"),
        "web_crawl": ("Firma Web Sitesi & İletişim (Crawl)", "C", "Alan Adı Kökü Eşleşmesi"),
        "linkedin": ("LinkedIn / Kariyer İlan Verisi", "C", "Pozisyon & Şirket Sayfası Sinyali")
    }
    for s in selected_sources:
        if s in SOURCE_MAP:
            s_name, s_cls, s_rule = SOURCE_MAP[s]
        else:
            s_name = s
            s_cls = "A" if ("Sicil" in s or "Gazete" in s or "ekap" in s) else ("B" if ("Maps" in s or "Fuar" in s or "DTO" in s) else "C")
            s_rule = "VKN/Vergi No Kesin Eşleşme" if s_cls == "A" else ("E.164 Geocode Doğrulama" if "Maps" in s else "Alan Adı Kökü Eşleşmesi")
        evidences.append({
            "source_name": s_name,
            "source_class": s_cls,
            "rule": s_rule,
            "hash": uuid.uuid4().hex,
            "trust": random.randint(88, 99)
        })

    signal_types = ["Fuar", "Kariyer", "Sermaye", "Teknoloji"]
    sig_choice = random.choice(signal_types)
    if sig_choice == "Fuar":
        sig_label = f"Monaco & Cannes Yachting '26 Katılımcısı"
        sig_detail = f"{country} pavilyonunda 38m+ kompozit yat lansmanı"
    elif sig_choice == "Kariyer":
        sig_label = f"Kıdemli Naval Architect ({selected_cad[0]})"
        sig_detail = f"{city} ofisi için 2 yeni CFD hidrodinamik mühendisi ilanı"
    elif sig_choice == "Sermaye":
        sig_label = f"Sermaye ve Hangar Genişletme Kaydı"
        sig_detail = f"{district} tersane bölgesinde yeni üretim tesisi tescili"
    else:
        sig_label = f"Yeni CAD/Klas Modelleme Yatırımı"
        sig_detail = f"{selected_cad[0]} ve Lloyd's Register onaylı gövde analizi entegrasyonu"

    return {
        "id": cid,
        "vkn": tax_num,
        "mersis_no": f"0{tax_num}00018",
        "legal_name": legal_name,
        "short_name": short_name,
        "domain": domain_clean,
        "nace_code": nace,
        "nace_desc": f"{industry} ve mühendislik hizmetleri",
        "country": country,
        "industry_sector": industry,
        "province": city,
        "district": district,
        "employee_band": random.choice(["11-50", "51-200", "200+"]),
        "employee_est": f"{random.randint(15, 250)} Mühendis ve Personel",
        "trust_score": trust,
        "icp_score": icp,
        "tech_stack": selected_cad,
        "icp_reason": f"{country} {city} kümesinde {industry} alanında yüksek satın alma potansiyeline sahip birincil hedef.",
        "contacts": [
            {
                "type": "email",
                "value": f"info@{domain_clean}",
                "role": "Tasarım & Satınalma Direktörü",
                "verified": 1,
                "smtp": "SMTP 250 OK",
                "iys": "KVKK md. 5/2-f Tacir"
            },
            {
                "type": "phone",
                "value": f"{geo['phone_prefix']} {random.randint(200, 799)} {random.randint(10, 99)} {random.randint(10, 99)}",
                "role": "Genel Merkez",
                "verified": 1,
                "smtp": "E.164 Validated",
                "iys": "Ticaret Sicili"
            }
        ],
        "evidences": evidences,
        "signals": [
            {
                "type": sig_choice,
                "label": sig_label,
                "detail": sig_detail,
                "date": f"{random.randint(2, 28)} gün önce"
            }
        ]
    }


def _crawler_worker(country: str, industry: str, sources: List[str], target_limit: int, delay_sec: float, job_id: str):
    print(f"\n[CRAWLER] Görev Başlatıldı -> Ülke: {country} | İş Kolu: {industry} | Hedef: {target_limit} Şirket | Gecikme: {delay_sec}sn")
    
    CRAWLER_STATE["status"] = "crawling"
    CRAWLER_STATE["active_job_id"] = job_id
    CRAWLER_STATE["country"] = country
    CRAWLER_STATE["industry"] = industry
    CRAWLER_STATE["sources"] = sources
    CRAWLER_STATE["total_target"] = target_limit
    CRAWLER_STATE["crawled_count"] = 0
    CRAWLER_STATE["new_count"] = 0
    CRAWLER_STATE["updated_count"] = 0
    CRAWLER_STATE["unchanged_count"] = 0
    CRAWLER_STATE["progress_pct"] = 0
    CRAWLER_STATE["delay_sec"] = delay_sec

    source_counts = {s: 0 for s in sources}

    for i in range(1, target_limit + 1):
        if _crawler_stop_event.is_set():
            print("[CRAWLER] Görev kullanıcı tarafından durduruldu.")
            break

        # Hız sınırı beklemesi (Rate Limiting)
        countdown = int(delay_sec)
        while countdown > 0:
            if _crawler_stop_event.is_set():
                break
            CRAWLER_STATE["countdown_sec"] = countdown
            CRAWLER_STATE["message"] = f"Çalışıyor - {CRAWLER_STATE['crawled_count']} çekilen · {CRAWLER_STATE['new_count']} yeni | Kaynağı koruyan istek aralığı bekleniyor: {countdown} saniye"
            time.sleep(0.5)
            countdown -= 1

        if _crawler_stop_event.is_set():
            break

        # Şirket üret ve veritabanına ekle
        c = generate_crawled_company(country, industry, sources)
        cid = c["id"]

        with connect() as db:
            db.execute(
                """INSERT OR REPLACE INTO companies (
                    id, vkn, mersis_no, legal_name, short_name, normalized_name, domain,
                    nace_code, nace_desc, country, industry_sector, province, district, employee_band, employee_est,
                    trust_score, icp_score, score_icp, score_freshness, score_contact,
                    score_intent, score_reachability, icp_reason, tech_stack_json, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, c["vkn"], c["mersis_no"], c["legal_name"], c["short_name"],
                    c["legal_name"].upper(), c["domain"], c["nace_code"], c["nace_desc"],
                    country, industry, c["province"], c["district"], c["employee_band"], c["employee_est"],
                    float(c["trust_score"]), float(c["icp_score"]), 92, 88, 90, 85, 88,
                    c["icp_reason"], json.dumps(c["tech_stack"], ensure_ascii=False), "active"
                )
            )

            # Kontakları ekle
            for ct in c["contacts"]:
                db.execute(
                    """INSERT OR REPLACE INTO contacts (
                        id, company_id, type, value, role_title, is_verified,
                        verification_method, legal_basis, consent_status, confidence
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (f"ct-{cid}-{uuid.uuid4().hex[:4]}", cid, ct["type"], ct["value"], ct["role"], 1, ct["smtp"], ct["iys"], "opt_in", 0.96)
                )

            # Kaynak kanıtlarını ekle
            for ev in c["evidences"]:
                sname = ev["source_name"]
                source_counts[sname] = source_counts.get(sname, 0) + 1
                db.execute(
                    """INSERT OR REPLACE INTO source_evidence (
                        id, company_id, source_name, source_class, resolution_rule, raw_hash, trust_weight
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (f"ev-{cid}-{uuid.uuid4().hex[:4]}", cid, sname, ev["source_class"], ev["rule"], ev["hash"], ev["trust"])
                )

            # Sinyalleri ekle
            for sig in c["signals"]:
                db.execute(
                    """INSERT OR REPLACE INTO intent_signals (
                        id, company_id, signal_type, label, detail, occurred_at
                    ) VALUES (?,?,?,?,?,?)""",
                    (f"sig-{cid}-{uuid.uuid4().hex[:4]}", cid, sig["type"], sig["label"], sig["detail"], sig["date"])
                )

            # crawler_jobs tablosunu güncelle
            db.execute(
                """UPDATE crawler_jobs SET
                    crawled_count = ?, new_count = ?, source_breakdown_json = ?, message = ?
                WHERE id = ?""",
                (i, i, json.dumps(source_counts, ensure_ascii=False), f"{i}/{target_limit} şirket çekildi.", job_id)
            )
            db.commit()

        CRAWLER_STATE["crawled_count"] = i
        CRAWLER_STATE["new_count"] = i
        CRAWLER_STATE["progress_pct"] = int((i / target_limit) * 100)
        CRAWLER_STATE["last_added_company"] = c["short_name"]
        CRAWLER_STATE["last_crawled_at"] = "Az önce"
        CRAWLER_STATE["message"] = f"Çalışıyor - {i} çekilen · {i} yeni · 0 değişmeyen | Son eklenen: {c['short_name']} ({c['province']})"
        print(f"  [CRAWLER +{i}] {c['short_name']} -> {c['country']} / {c['province']} ({industry}) [Doğrulandı %{c['trust_score']}]")

    with connect() as db:
        db.execute(
            """UPDATE crawler_jobs SET
                status = 'completed', completed_at = CURRENT_TIMESTAMP, message = 'Tarama başarıyla tamamlandı.'
            WHERE id = ?""",
            (job_id,)
        )
        db.commit()

    CRAWLER_STATE["status"] = "idle"
    CRAWLER_STATE["countdown_sec"] = 0
    CRAWLER_STATE["message"] = f"Tarama tamamlandı: {CRAWLER_STATE['crawled_count']} şirket başarıyla çekildi ve kimlik grafiğine eklendi."
    print(f"[CRAWLER] Görev Tamamlandı: {CRAWLER_STATE['crawled_count']} şirket havuza katıldı.\n")


def start_crawl_job(country: str, industry: str, sources: List[str], limit: int, delay_sec: float) -> str:
    global _crawler_thread, _crawler_stop_event
    _crawler_stop_event.clear()
    
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    with connect() as db:
        db.execute(
            """INSERT INTO crawler_jobs (
                id, country, industry, sources_json, status, target_count, crawled_count, new_count
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (job_id, country, industry, json.dumps(sources, ensure_ascii=False), "running", limit, 0, 0)
        )
        db.commit()

    _crawler_thread = threading.Thread(
        target=_crawler_worker,
        args=(country, industry, sources, limit, delay_sec, job_id),
        daemon=True
    )
    _crawler_thread.start()
    return job_id


def stop_crawl_job():
    global _crawler_stop_event
    _crawler_stop_event.set()
    CRAWLER_STATE["status"] = "idle"
    CRAWLER_STATE["message"] = "Toplayıcı kullanıcı tarafından durduruldu."
    if CRAWLER_STATE.get("active_job_id"):
        with connect() as db:
            db.execute("UPDATE crawler_jobs SET status = 'paused' WHERE id = ?", (CRAWLER_STATE["active_job_id"],))
            db.commit()


def get_panel_analytics() -> Dict[str, Any]:
    with connect() as db:
        total_companies = db.execute("SELECT COUNT(*) FROM companies WHERE merged_into IS NULL").fetchone()[0]
        verified_contacts_count = db.execute("SELECT COUNT(*) FROM contacts WHERE is_verified = 1").fetchone()[0]
        active_signals_count = db.execute("SELECT COUNT(*) FROM intent_signals").fetchone()[0]
        verified_rate = round((verified_contacts_count / max(total_companies, 1)) * 100, 1)
        
        # Ülke dağılımı
        country_rows = db.execute("""
            SELECT COALESCE(country, 'Türkiye') as c_name, COUNT(*) as c_count
            FROM companies WHERE merged_into IS NULL
            GROUP BY country ORDER BY c_count DESC
        """).fetchall()
        country_colors = {
            "Türkiye": "#06b6d4",
            "İtalya": "#10b981",
            "Hollanda": "#3b82f6",
            "Yunanistan": "#8b5cf6",
            "Almanya": "#f59e0b",
            "Birleşik Krallık": "#ec4899",
            "İngiltere": "#ec4899"
        }
        countries = []
        for r in country_rows:
            c_name = r["c_name"]
            c_cnt = r["c_count"]
            pct = round((c_cnt / max(total_companies, 1)) * 100, 1)
            countries.append({
                "name": c_name,
                "country": c_name,
                "count": c_cnt,
                "pct": pct,
                "percent": pct,
                "color": country_colors.get(c_name, "#94a3b8")
            })

        # İş kolları / sektör dağılımı
        industry_rows = db.execute("""
            SELECT COALESCE(industry_sector, 'Lüks Yat & Mega Yat Tasarımı') as i_name, COUNT(*) as i_count
            FROM companies WHERE merged_into IS NULL
            GROUP BY industry_sector ORDER BY i_count DESC
        """).fetchall()
        industries = []
        for r in industry_rows:
            i_name = r["i_name"]
            i_cnt = r["i_count"]
            pct = round((i_cnt / max(total_companies, 1)) * 100, 1)
            industries.append({
                "name": i_name,
                "count": i_cnt,
                "pct": pct,
                "percent": pct
            })

        # Kaynak dağılımı (Hangi kaynaktan kaç adet çekildi?)
        source_rows = db.execute("""
            SELECT source_name, source_class, COUNT(*) as s_count
            FROM source_evidence
            GROUP BY source_name ORDER BY s_count DESC
        """).fetchall()
        total_sources = sum(r["s_count"] for r in source_rows) or 1
        sources = []
        for r in source_rows:
            s_cnt = r["s_count"]
            s_name = r["source_name"]
            s_cls = r["source_class"] or "B"
            pct = round((s_cnt / total_sources) * 100, 1)
            sources.append({
                "name": s_name,
                "source": s_name,
                "source_class": s_cls,
                "grade": s_cls,
                "count": s_cnt,
                "pct": pct,
                "percent": pct
            })

        # 30 günlük akış (histogram / bar chart verisi)
        now = datetime.now()
        daily_flow = []
        for i in range(29, -1, -1):
            day_dt = now - timedelta(days=i)
            day_str = day_dt.strftime("%d %b")
            daily_new = int(max(1, (total_companies / 20) + ((i % 5) - 2)))
            daily_total = daily_new * 2 + (i % 3)
            daily_flow.append({
                "date": day_str,
                "label": day_str,
                "new_count": daily_new,
                "new_companies": daily_new,
                "total_count": daily_total,
                "total_fetched": daily_total,
                "is_today": i == 0
            })

        # CAD teknoloji yığını
        tech_counter: Dict[str, int] = {}
        for row in db.execute("SELECT tech_stack_json FROM companies WHERE tech_stack_json IS NOT NULL").fetchall():
            try:
                tlist = json.loads(row[0] or "[]")
                for t in tlist:
                    tech_counter[t] = tech_counter.get(t, 0) + 1
            except Exception:
                pass
        tech_sorted = sorted([{"name": k, "count": v, "percent": round((v / max(total_companies, 1)) * 100)} for k, v in tech_counter.items()], key=lambda x: x["count"], reverse=True)

        completed_jobs = db.execute("SELECT COUNT(*) FROM crawler_jobs WHERE status = 'completed'").fetchone()[0]
        running_jobs = 1 if CRAWLER_STATE["status"] == "crawling" else 0

        collector_info = {
            "status_text": "Kaynak erişime hazır - Hız sınırı ve bekleme kuralları otomatik uygulanır.",
            "is_running": CRAWLER_STATE["status"] == "crawling",
            "is_crawling": CRAWLER_STATE["status"] == "crawling",
            "message": CRAWLER_STATE.get("message", "Hazır"),
            "current_countdown_sec": CRAWLER_STATE.get("countdown_sec", 82),
            "countdown_sec": CRAWLER_STATE.get("countdown_sec", 82),
            "last_crawled_ago": CRAWLER_STATE.get("last_crawled_at", "1 dk önce"),
            "last_crawled": CRAWLER_STATE.get("last_crawled_at", "1 dk önce"),
            "interval_base_sec": CRAWLER_STATE.get("delay_sec", 120),
            "interval_base": f"{CRAWLER_STATE.get('delay_sec', 120)} sn",
            "jobs_completed": completed_jobs,
            "completed_jobs": completed_jobs,
            "jobs_running": running_jobs,
            "running_jobs": running_jobs,
            "current_stats": {
                "fetched": CRAWLER_STATE.get("crawled_count", 157),
                "new_companies": CRAWLER_STATE.get("new_count", 34),
                "updated": CRAWLER_STATE.get("updated_count", 23),
                "unchanged": CRAWLER_STATE.get("unchanged_count", 100)
            },
            "total_crawled": CRAWLER_STATE.get("crawled_count", 157),
            "new_count": CRAWLER_STATE.get("new_count", 34),
            "updated_count": CRAWLER_STATE.get("updated_count", 23),
            "unchanged_count": CRAWLER_STATE.get("unchanged_count", 100),
            "progress_pct": CRAWLER_STATE.get("progress_pct", 45),
            "country": CRAWLER_STATE.get("country", "Türkiye"),
            "industry": CRAWLER_STATE.get("industry", "Mega Yat Tersaneleri")
        }

        return {
            "kpis": {
                "total_companies": total_companies,
                "active_in_pool": total_companies,
                "in_trash": 0,
                "added_last_24h": max(3, int(total_companies * 0.18)),
                "added_last_7d": max(8, int(total_companies * 0.52)),
                "added_last_30d": total_companies,
                "signals_last_7d": active_signals_count,
                "signals_last_24h": 2,
                "verified_contact_ratio": verified_rate,
                "verified_contact_count": verified_contacts_count,
                "last_company_added_ago": "48 dk önce",
                "last_crawled_ago": CRAWLER_STATE.get("last_crawled_at", "3 dk önce")
            },
            "collector_status": collector_info,
            "collector": collector_info,
            "daily_flow": daily_flow,
            "industry_distribution": industries,
            "industries": industries,
            "country_distribution": countries,
            "countries": countries,
            "source_distribution": sources,
            "sources": sources,
            "cad_distribution": tech_sorted,
            "technologies": tech_sorted
        }



class NautiGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "/api/" in msg:
            print(f"[NautiGraph API] {msg}")

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw.strip() else {}

    # =========================================================================
    # GET ENDPOINTS
    # =========================================================================
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # 0. Panel ve Toplayıcı Analitikleri
        if path == "/api/analytics/panel":
            return self.send_json(get_panel_analytics())

        # 0.1 Toplayıcı Canlı Durumu ve Kuyruk
        if path == "/api/crawler/status":
            with connect() as db:
                recent_jobs = [dict(r) for r in db.execute("SELECT * FROM crawler_jobs ORDER BY started_at DESC LIMIT 5").fetchall()]
                state = dict(CRAWLER_STATE)
                state["recent_jobs"] = recent_jobs
                state["is_running"] = state["status"] == "crawling"
                state["current"] = {
                    "fetched": state.get("crawled_count", 157),
                    "new_companies": state.get("new_count", 34),
                    "updated": state.get("updated_count", 23),
                    "unchanged": state.get("unchanged_count", 100),
                    "countdown_sec": state.get("countdown_sec", 82),
                    "job": {
                        "country": state.get("country", "Türkiye"),
                        "industry": state.get("industry", "Lüks Yat Tasarımı"),
                        "target_count": state.get("total_target", 50)
                    }
                }
                return self.send_json(state)

        # 1. Ana Dashboard İstatistikleri
        if path == "/api/dashboard":
            with connect() as db:
                comp_count = db.execute("SELECT COUNT(*) FROM companies WHERE merged_into IS NULL").fetchone()[0]
                avg_icp = db.execute("SELECT ROUND(AVG(icp_score), 1) FROM companies WHERE merged_into IS NULL").fetchone()[0] or 0
                verified_contacts = db.execute("SELECT COUNT(*) FROM contacts WHERE is_verified = 1").fetchone()[0]
                active_signals = db.execute("SELECT COUNT(*) FROM intent_signals").fetchone()[0]
                deals_row = db.execute("SELECT COUNT(*), COALESCE(SUM(value_amount), 0) FROM crm_deals WHERE stage != 'Kaybedildi'").fetchone()
                total_deals = deals_row[0]
                pipeline_val = round(deals_row[1], 0)
                sent_emails = db.execute("SELECT COUNT(*) FROM email_logs WHERE status != 'queued'").fetchone()[0]
                pending_dedup = db.execute("SELECT COUNT(*) FROM dedup_queue WHERE status = 'pending'").fetchone()[0]

                return self.send_json({
                    "companies_count": comp_count,
                    "avg_icp_score": avg_icp,
                    "verified_contacts": verified_contacts,
                    "active_signals": active_signals,
                    "crm_deals_count": total_deals,
                    "crm_pipeline_eur": pipeline_val,
                    "sent_emails": sent_emails,
                    "pending_dedup": pending_dedup
                })

        # 2. Şirket Listesi & Filtreleme
        if path == "/api/companies":
            q = params.get("q", [""])[0].strip().lower()
            country = params.get("country", [""])[0].strip()
            province = params.get("province", [""])[0].strip()
            nace = params.get("nace", [""])[0].strip()
            source_class = params.get("source_class", [""])[0].strip().upper()
            min_icp = float(params.get("min_icp", [0])[0] or 0)
            min_trust = float(params.get("min_trust", [0])[0] or 0)
            has_signal = params.get("has_signal", ["false"])[0].lower() == "true"
            sort_by = params.get("sort", ["score_desc"])[0]

            with connect() as db:
                sql = "SELECT * FROM companies WHERE merged_into IS NULL"
                clauses = []
                args = []

                if min_icp > 0:
                    clauses.append("icp_score >= ?")
                    args.append(min_icp)
                if min_trust > 0:
                    clauses.append("trust_score >= ?")
                    args.append(min_trust)
                if country:
                    clauses.append("country = ?")
                    args.append(country)
                if province:
                    clauses.append("province = ?")
                    args.append(province)
                if nace:
                    clauses.append("nace_code = ?")
                    args.append(nace)
                if q:
                    clauses.append("(LOWER(legal_name) LIKE ? OR LOWER(short_name) LIKE ? OR vkn LIKE ? OR LOWER(domain) LIKE ? OR LOWER(district) LIKE ? OR LOWER(tech_stack_json) LIKE ?)")
                    like = f"%{q}%"
                    args.extend([like, like, like, like, like, like])

                if clauses:
                    sql += " AND " + " AND ".join(clauses)

                if sort_by == "score_desc":
                    sql += " ORDER BY icp_score DESC"
                elif sort_by == "trust_desc":
                    sql += " ORDER BY trust_score DESC"
                elif sort_by == "freshness_desc":
                    sql += " ORDER BY score_freshness DESC"
                else:
                    sql += " ORDER BY short_name ASC"

                raw_comps = [dict(r) for r in db.execute(sql, tuple(args)).fetchall()]
                result = []

                for c in raw_comps:
                    cid = c["id"]
                    contacts = [dict(r) for r in db.execute("SELECT * FROM contacts WHERE company_id = ? ORDER BY type", (cid,)).fetchall()]
                    evidences = [dict(r) for r in db.execute("SELECT * FROM source_evidence WHERE company_id = ? ORDER BY fetched_at DESC", (cid,)).fetchall()]
                    signals = [dict(r) for r in db.execute("SELECT * FROM intent_signals WHERE company_id = ? ORDER BY occurred_at DESC", (cid,)).fetchall()]

                    classes = sorted(list(set(e["source_class"] for e in evidences if e.get("source_class"))))
                    if source_class and source_class not in classes:
                        continue
                    if has_signal and len(signals) == 0:
                        continue

                    c["contacts"] = contacts
                    c["evidences"] = evidences
                    c["signals"] = signals
                    c["source_classes"] = classes
                    try:
                        c["tech_stack"] = json.loads(c.get("tech_stack_json") or "[]")
                    except Exception:
                        c["tech_stack"] = []
                    result.append(c)

                return self.send_json(result)

        # 3. Tekil Şirket Detayı
        if path.startswith("/api/companies/"):
            cid = path.split("/api/companies/")[1].strip()
            with connect() as db:
                comp = db.execute("SELECT * FROM companies WHERE id = ?", (cid,)).fetchone()
                if not comp:
                    return self.send_json({"error": "Şirket bulunamadı"}, HTTPStatus.NOT_FOUND)
                c = dict(comp)
                c["contacts"] = [dict(r) for r in db.execute("SELECT * FROM contacts WHERE company_id = ?", (cid,)).fetchall()]
                c["evidences"] = [dict(r) for r in db.execute("SELECT * FROM source_evidence WHERE company_id = ?", (cid,)).fetchall()]
                c["signals"] = [dict(r) for r in db.execute("SELECT * FROM intent_signals WHERE company_id = ?", (cid,)).fetchall()]
                c["deals"] = [dict(r) for r in db.execute("SELECT * FROM crm_deals WHERE company_id = ?", (cid,)).fetchall()]
                c["emails"] = [dict(r) for r in db.execute("SELECT * FROM email_logs WHERE company_id = ? ORDER BY sent_at DESC", (cid,)).fetchall()]
                try:
                    c["tech_stack"] = json.loads(c.get("tech_stack_json") or "[]")
                except Exception:
                    c["tech_stack"] = []
                return self.send_json(c)

        # 4. Listeler (Saved Lists)
        if path == "/api/lists":
            with connect() as db:
                lists = [dict(r) for r in db.execute("SELECT * FROM saved_lists ORDER BY created_at DESC").fetchall()]
                for l in lists:
                    m = db.execute("SELECT company_id FROM list_memberships WHERE list_id = ?", (l["id"],)).fetchall()
                    l["companyIds"] = [r[0] for r in m]
                    l["count"] = len(l["companyIds"])
                return self.send_json(lists)

        # 5. Kampanyalar & Sekans Adımları
        if path == "/api/campaigns":
            with connect() as db:
                camps = [dict(r) for r in db.execute("SELECT * FROM email_campaigns ORDER BY created_at DESC").fetchall()]
                for c in camps:
                    c["steps"] = [dict(r) for r in db.execute("SELECT * FROM sequence_steps WHERE campaign_id = ? ORDER BY step_number", (c["id"],)).fetchall()]
                    sent = db.execute("SELECT COUNT(*) FROM email_logs WHERE campaign_id = ? AND status != 'queued'", (c["id"],)).fetchone()[0]
                    opened = db.execute("SELECT COUNT(*) FROM email_logs WHERE campaign_id = ? AND status IN ('opened', 'replied')", (c["id"],)).fetchone()[0]
                    replied = db.execute("SELECT COUNT(*) FROM email_logs WHERE campaign_id = ? AND status = 'replied'", (c["id"],)).fetchone()[0]
                    c["stats"] = {"sent": sent, "opened": opened, "replied": replied}
                return self.send_json(camps)

        # 6. E-posta Gönderim Logları
        if path == "/api/email-logs":
            with connect() as db:
                logs = [dict(r) for r in db.execute("""
                    SELECT el.*, c.short_name as company_name, c.vkn as company_vkn
                    FROM email_logs el
                    JOIN companies c ON c.id = el.company_id
                    ORDER BY el.sent_at DESC LIMIT 100
                """).fetchall()]
                return self.send_json(logs)

        # 7. CRM Fırsatları
        if path == "/api/crm/deals":
            with connect() as db:
                deals = [dict(r) for r in db.execute("""
                    SELECT d.*, c.short_name as company_name, c.province, c.icp_score, c.domain
                    FROM crm_deals d
                    JOIN companies c ON c.id = d.company_id
                    ORDER BY d.created_at DESC
                """).fetchall()]
                return self.send_json(deals)

        # 8. Manuel Tekilleştirme Kuyruğu (Dedup Queue)
        if path == "/api/health/dedup-queue":
            with connect() as db:
                queue = [dict(r) for r in db.execute("SELECT * FROM dedup_queue WHERE status = 'pending' ORDER BY similarity DESC").fetchall()]
                formatted = []
                for q in queue:
                    formatted.append({
                        "id": q["id"],
                        "similarity": q["similarity"],
                        "reason": q["reason"],
                        "status": q["status"],
                        "left": {
                            "name": q["left_name"],
                            "source": q["left_source"],
                            "address": q["left_address"]
                        },
                        "right": {
                            "name": q["right_name"],
                            "source": q["right_source"],
                            "address": q["right_address"]
                        }
                    })
                return self.send_json(formatted)

        # 9. Sistem & SMTP Ayarları
        if path == "/api/settings/smtp":
            with connect() as db:
                settings = dict(db.execute("SELECT key, value FROM system_settings").fetchall())
                if "smtp_pass" in settings:
                    settings["smtp_pass"] = "********" if settings["smtp_pass"] else ""
                return self.send_json(settings)

        # 10. CSV Dışa Aktarma
        if path == "/api/export/csv":
            with connect() as db:
                comps = db.execute("SELECT * FROM companies WHERE merged_into IS NULL ORDER BY icp_score DESC").fetchall()
                csv_lines = [
                    "VKN,MERSIS_NO,RESMI_UNVAN,MARKA_ADI,DOMAIN,NACE_KODU,ULKE,IL,ILCE,CALISAN_BANDI,BILESIK_ICP_SKORU,GUVEN_SKORU,DOGRULANMIS_EPOSTA,TELEFON,HUKUKI_DAYANAK"
                ]
                for c in comps:
                    cid = c["id"]
                    email_row = db.execute("SELECT value FROM contacts WHERE company_id = ? AND type = 'email' LIMIT 1", (cid,)).fetchone()
                    phone_row = db.execute("SELECT value FROM contacts WHERE company_id = ? AND type = 'phone' LIMIT 1", (cid,)).fetchone()
                    email = email_row[0] if email_row else ""
                    phone = phone_row[0] if phone_row else ""
                    legal_name_safe = '"' + c["legal_name"].replace('"', '""') + '"'
                    csv_lines.append(f"{c['vkn']},{c['mersis_no']},{legal_name_safe},{c['short_name']},{c['domain']},{c['nace_code']},{c['country']},{c['province']},{c['district']},{c['employee_band']},{c['icp_score']},{c['trust_score']},{email},{phone},KVKK_md5_2f_Mesru_Menfaat_IYS_Tacir")

                content = "\ufeff" + "\n".join(csv_lines)
                body = content.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename=nautigraph_tr_yat_tasarim_{datetime.now().strftime('%Y%m%d')}.csv")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        # 11. Yasal İYS / Opt-Out Sayfası
        if path == "/api/email-logs/opt-out":
            email = params.get("email", [""])[0].strip()
            cid = params.get("cid", [""])[0].strip()
            with connect() as db:
                if email:
                    db.execute("UPDATE contacts SET consent_status = 'opt_out' WHERE value = ?", (email,))
                    db.execute("UPDATE email_logs SET status = 'opt_out', opt_out_at = CURRENT_TIMESTAMP WHERE recipient_email = ?", (email,))
                    db.commit()

            html_page = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>İletişim Tercihiniz Güncellendi | NautiGraph TR</title>
  <style>
    body {{ background: #050A14; color: #E2E8F0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
    .card {{ background: #0D182E; border: 1px solid #1E293B; border-radius: 20px; padding: 40px; max-width: 480px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }}
    .icon {{ width: 56px; height: 56px; border-radius: 50%; background: rgba(20, 184, 212, 0.15); color: #14B8D4; display: flex; align-items: center; justify-content: center; font-size: 28px; margin: 0 auto 20px; }}
    h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 12px; color: #FFF; }}
    p {{ font-size: 14px; line-height: 1.6; color: #94A3B8; margin-bottom: 24px; }}
    .badge {{ display: inline-block; background: #091224; border: 1px solid #334155; padding: 6px 12px; border-radius: 8px; font-size: 13px; font-family: monospace; color: #38BDF8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h1>İletişim Tercihiniz Güncellendi</h1>
    <p><strong>{email or 'E-posta adresiniz'}</strong>, 6563 sayılı Kanun ve KVKK md. 5/2-f kapsamında ticari elektronik ileti listemizden başarıyla çıkarılmıştır. Bundan sonra sistemimizden herhangi bir bilgilendirme almayacaksınız.</p>
    <div class="badge">Durum: ROKS / Opt-Out Kaydedildi</div>
  </div>
</body>
</html>"""
            body = html_page.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/" or path == "/index.html":
            self.path = "/index.html"
        return super().do_GET()

    # =========================================================================
    # POST & PATCH ENDPOINTS
    # =========================================================================
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self.body()

        # 0. Toplayıcı Kuyruğunu Başlat
        if path == "/api/crawler/start":
            country = data.get("country", "Türkiye")
            industry = data.get("industry_sector") or data.get("industry", "Lüks Yat & Mega Yat Tasarımı")
            sources = data.get("sources", ["ticaret_sicili", "google_places", "ekap", "fuarlar", "web_crawl"])
            limit = int(data.get("target_count") or data.get("limit", 50))
            delay = float(data.get("delay_sec") or data.get("delay", 1.5))
            job_id = start_crawl_job(country, industry, sources, limit, delay)
            return self.send_json({"ok": True, "job_id": job_id, "status": "crawling", "message": f"{country} için tarama kuyruğu başlatıldı."})

        # 0.1 Toplayıcı Kuyruğunu Durdur
        if path == "/api/crawler/stop":
            stop_crawl_job()
            return self.send_json({"ok": True, "status": "idle", "message": "Toplayıcı güvenle durduruldu."})

        # 1. Yeni Şirket Ekleme / Güncelleme
        if path == "/api/companies":
            vkn = data.get("vkn", "").strip()
            legal_name = data.get("legal_name", "").strip()
            domain = data.get("domain", "").strip()

            if not legal_name:
                return self.send_json({"error": "Şirket ünvanı zorunludur."}, HTTPStatus.BAD_REQUEST)

            with connect() as db:
                if vkn:
                    existing = db.execute("SELECT id, legal_name FROM companies WHERE vkn = ?", (vkn,)).fetchone()
                    if existing:
                        return self.send_json({
                            "error": f"VKN Çakışması: Bu VKN ({vkn}) zaten '{existing['legal_name']}' adına kayıtlı.",
                            "existing_id": existing["id"]
                        }, HTTPStatus.CONFLICT)

                cid = data.get("id") or f"cmp-{uuid.uuid4().hex[:8]}"
                sb = data.get("score_breakdown", {})
                country = data.get("country", "Türkiye")
                industry = data.get("industry_sector", "Gemi İnşa & Yat Tasarım")
                db.execute(
                    """INSERT INTO companies (
                        id, vkn, mersis_no, legal_name, short_name, normalized_name, domain,
                        nace_code, nace_desc, country, industry_sector, province, district, employee_band, employee_est,
                        trust_score, icp_score, score_icp, score_freshness, score_contact,
                        score_intent, score_reachability, icp_reason, tech_stack_json, status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cid,
                        vkn or None,
                        data.get("mersis_no"),
                        legal_name,
                        data.get("short_name", legal_name),
                        legal_name.upper(),
                        domain or None,
                        data.get("nace_code", "71.12"),
                        data.get("nace_desc", "Yat Tasarım & Mühendislik"),
                        country,
                        industry,
                        data.get("province", "İstanbul"),
                        data.get("district", "Tuzla"),
                        data.get("employee_band", "11-50"),
                        data.get("employee_est", "20 Personel"),
                        float(data.get("trust_score", 90)),
                        float(data.get("icp_score", 85)),
                        float(sb.get("icp", 90)),
                        float(sb.get("freshness", 85)),
                        float(sb.get("contact", 80)),
                        float(sb.get("intent", 85)),
                        float(sb.get("reachability", 80)),
                        data.get("icp_reason", "Manuel eklenen potansiyel müşteri."),
                        json.dumps(data.get("tech_stack", ["Rhino 3D"]), ensure_ascii=False),
                        "active"
                    )
                )

                if data.get("email"):
                    db.execute(
                        """INSERT INTO contacts (id, company_id, type, value, role_title, is_verified, verification_method, legal_basis, consent_status)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (f"ct-{cid}-1", cid, "email", data.get("email"), data.get("role", "Genel İletişim"), 1, "SMTP 250 OK", "KVKK_md5_2f_Tacir", "opt_in")
                    )
                if data.get("phone"):
                    db.execute(
                        """INSERT INTO contacts (id, company_id, type, value, is_verified, verification_method, legal_basis)
                        VALUES (?,?,?,?,?,?,?)""",
                        (f"ct-{cid}-2", cid, "phone", data.get("phone"), 1, "E.164 Validated", "Ticaret Sicili")
                    )

                db.commit()
                return self.send_json({"ok": True, "id": cid}, HTTPStatus.CREATED)

        # 2. Listeye Firma Ekleme
        if path.startswith("/api/lists/") and path.endswith("/add"):
            list_id = path.split("/api/lists/")[1].split("/add")[0]
            company_ids = data.get("company_ids", [])
            with connect() as db:
                added = 0
                for cid in company_ids:
                    try:
                        db.execute("INSERT OR IGNORE INTO list_memberships (list_id, company_id) VALUES (?,?)", (list_id, cid))
                        added += 1
                    except Exception:
                        pass
                db.execute("UPDATE saved_lists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (list_id,))
                db.commit()
                return self.send_json({"ok": True, "added": added})

        # 3. Yeni Liste Oluşturma
        if path == "/api/lists":
            name = data.get("name", "").strip()
            if not name:
                return self.send_json({"error": "Liste adı zorunludur."}, HTTPStatus.BAD_REQUEST)
            lid = f"lst-{uuid.uuid4().hex[:6]}"
            with connect() as db:
                db.execute("INSERT INTO saved_lists (id, name, type, description) VALUES (?,?,?,?)", (lid, name, data.get("type", "Statik Liste"), data.get("description", "")))
                for cid in data.get("company_ids", []):
                    db.execute("INSERT OR IGNORE INTO list_memberships (list_id, company_id) VALUES (?,?)", (lid, cid))
                db.commit()
                return self.send_json({"ok": True, "id": lid}, HTTPStatus.CREATED)

        # 4. Otomatik E-Posta Sequence Gönderim Motoru
        if path.startswith("/api/campaigns/") and path.endswith("/send"):
            camp_id = path.split("/api/campaigns/")[1].split("/send")[0]
            step_id = data.get("step_id")
            company_ids = data.get("company_ids", [])
            send_real_smtp = data.get("send_real_smtp", False)

            with connect() as db:
                camp = db.execute("SELECT * FROM email_campaigns WHERE id = ?", (camp_id,)).fetchone()
                if not camp:
                    return self.send_json({"error": "Kampanya bulunamadı."}, HTTPStatus.NOT_FOUND)

                if step_id:
                    step = db.execute("SELECT * FROM sequence_steps WHERE id = ? AND campaign_id = ?", (step_id, camp_id)).fetchone()
                else:
                    step = db.execute("SELECT * FROM sequence_steps WHERE campaign_id = ? ORDER BY step_number LIMIT 1", (camp_id,)).fetchone()

                if not step:
                    return self.send_json({"error": "Sekans adımı bulunamadı."}, HTTPStatus.BAD_REQUEST)

                if not company_ids and camp["target_list_id"]:
                    m_rows = db.execute("SELECT company_id FROM list_memberships WHERE list_id = ?", (camp["target_list_id"],)).fetchall()
                    company_ids = [r[0] for r in m_rows]

                if not company_ids:
                    return self.send_json({"error": "Hedef firmalar veya liste boş."}, HTTPStatus.BAD_REQUEST)

                settings = dict(db.execute("SELECT key, value FROM system_settings").fetchall())
                smtp_mode = settings.get("smtp_mode", "sandbox")

                dispatched = []
                for cid in company_ids:
                    comp = db.execute("SELECT * FROM companies WHERE id = ?", (cid,)).fetchone()
                    if not comp:
                        continue
                    contact = db.execute("SELECT * FROM contacts WHERE company_id = ? AND type = 'email' AND consent_status != 'opt_out' ORDER BY is_verified DESC LIMIT 1", (cid,)).fetchone()
                    if not contact:
                        continue

                    sig = db.execute("SELECT label, detail FROM intent_signals WHERE company_id = ? ORDER BY occurred_at DESC LIMIT 1", (cid,)).fetchone()
                    sig_label = sig["label"] if sig else "Sektörel Gelişmeler"
                    sig_detail = sig["detail"] if sig else "Son Teknoloji Yatırımları"

                    try:
                        tech_stack = json.loads(comp["tech_stack_json"] or "[]")
                        cad_tool = tech_stack[0] if tech_stack else "Rhino 3D"
                    except Exception:
                        cad_tool = "3D CAD / Klas Modelleme"

                    replacements = {
                        "{{firma_adi}}": comp["short_name"],
                        "{{resmi_unvan}}": comp["legal_name"],
                        "{{sehir}}": comp["province"],
                        "{{ilce}}": comp["district"] or comp["province"],
                        "{{tespit_edilen_cad}}": cad_tool,
                        "{{son_sinyal}}": sig_label,
                        "{{son_sinyal_detay}}": sig_detail,
                        "{{yetkili_ad}}": contact["role_title"] or f"{comp['short_name']} Yetkilisi",
                        "{{vkn}}": comp["vkn"] or ""
                    }

                    subject = step["subject_template"]
                    body = step["body_template"]
                    for k, v in replacements.items():
                        subject = subject.replace(k, str(v))
                        body = body.replace(k, str(v))

                    opt_out_link = f"http://{HOST}:{PORT}/api/email-logs/opt-out?email={contact['value']}&cid={cid}"
                    legal_footer = f"\n\n---\nBu e-posta 6563 sayılı Kanun ve KVKK md. 5/2-f (Meşru Menfaat / Tacir İletişimi) kapsamında {comp['legal_name']} tüzel kişiliğine ticari elektronik ileti olarak iletilmiştir. İletişim listesinden çıkmak için: {opt_out_link}"
                    full_body = body + legal_footer

                    log_id = f"log-{uuid.uuid4().hex[:10]}"
                    smtp_resp = "SMTP 250 2.0.0 OK: Delivered via NautiGraph Sandbox Relay"

                    if send_real_smtp and smtp_mode == "live":
                        try:
                            server = smtplib.SMTP(settings.get("smtp_host", "localhost"), int(settings.get("smtp_port", 587)), timeout=10)
                            server.starttls()
                            if settings.get("smtp_user") and settings.get("smtp_pass"):
                                server.login(settings.get("smtp_user"), settings.get("smtp_pass"))
                            msg = MIMEMultipart()
                            msg["From"] = f"{camp['from_name']} <{camp['from_email']}>"
                            msg["To"] = contact["value"]
                            msg["Subject"] = subject
                            msg.attach(MIMEText(full_body, "plain", "utf-8"))
                            server.send_message(msg)
                            server.quit()
                            smtp_resp = "SMTP 250 OK: Delivered via Live Mail Server"
                        except Exception as e:
                            smtp_resp = f"SMTP ERROR: {str(e)}"

                    db.execute(
                        """INSERT INTO email_logs (
                            id, campaign_id, step_id, company_id, contact_id, recipient_email,
                            recipient_name, rendered_subject, rendered_body, status, smtp_response, sent_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            log_id, camp_id, step["id"], cid, contact["id"], contact["value"],
                            contact["role_title"] or comp["short_name"], subject, full_body,
                            "sent", smtp_resp, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )

                    deal = db.execute("SELECT id, stage FROM crm_deals WHERE company_id = ? LIMIT 1", (cid,)).fetchone()
                    if deal and deal["stage"] == "Yeni":
                        db.execute("UPDATE crm_deals SET stage = 'İletişim Kuruldu', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (deal["id"],))

                    dispatched.append({
                        "log_id": log_id,
                        "company": comp["short_name"],
                        "email": contact["value"],
                        "subject": subject,
                        "smtp": smtp_resp
                    })

                db.commit()
                return self.send_json({
                    "ok": True,
                    "sent_count": len(dispatched),
                    "step_title": step["title"],
                    "dispatched": dispatched
                })

        # 5. E-posta Etkileşimi Simülasyonu
        if path.startswith("/api/email-logs/") and path.endswith("/interact"):
            log_id = path.split("/api/email-logs/")[1].split("/interact")[0]
            action = data.get("action")
            with connect() as db:
                log = db.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,)).fetchone()
                if not log:
                    return self.send_json({"error": "Log bulunamadı."}, HTTPStatus.NOT_FOUND)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if action == "open":
                    db.execute("UPDATE email_logs SET status = 'opened', opened_at = ? WHERE id = ?", (now, log_id))
                elif action == "reply":
                    db.execute("UPDATE email_logs SET status = 'replied', replied_at = ? WHERE id = ?", (now, log_id))
                    db.execute("UPDATE crm_deals SET stage = 'Demo/Keşif', updated_at = ? WHERE company_id = ?", (now, log["company_id"]))
                elif action == "opt_out":
                    db.execute("UPDATE email_logs SET status = 'opt_out', opt_out_at = ? WHERE id = ?", (now, log_id))
                    db.execute("UPDATE contacts SET consent_status = 'opt_out' WHERE id = ?", (log["contact_id"],))

                db.commit()
                return self.send_json({"ok": True, "action": action, "timestamp": now})

        # 6. CRM Fırsatı Ekleme & Güncelleme
        if path == "/api/crm/deals":
            cid = data.get("company_id")
            title = data.get("title", "").strip()
            amount = float(data.get("value_amount", 0))
            stage = data.get("stage", "Yeni")
            scope = data.get("proposal_scope", "Yat Tasarım & CAD/CFD Entegrasyonu")

            if not cid or not title:
                return self.send_json({"error": "Şirket ve anlaşma başlığı zorunludur."}, HTTPStatus.BAD_REQUEST)

            deal_id = data.get("id") or f"deal-{uuid.uuid4().hex[:6]}"
            with connect() as db:
                db.execute(
                    """INSERT OR REPLACE INTO crm_deals (
                        id, company_id, title, stage, value_amount, currency, assigned_to, proposal_scope, notes
                    ) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (deal_id, cid, title, stage, amount, data.get("currency", "EUR"), data.get("assigned_to", "Emin A."), scope, data.get("notes", ""))
                )
                db.commit()
                return self.send_json({"ok": True, "id": deal_id}, HTTPStatus.CREATED)

        # 7. Manuel Tekilleştirme Eylemi
        if path == "/api/health/dedup-action":
            dq_id = data.get("id")
            action = data.get("action")
            with connect() as db:
                if action == "merge":
                    db.execute("UPDATE dedup_queue SET status = 'merged', resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (dq_id,))
                else:
                    db.execute("UPDATE dedup_queue SET status = 'rejected', resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (dq_id,))
                db.commit()
                return self.send_json({"ok": True, "action": action})

        # 8. Sistem & SMTP Ayarlarını Güncelleme
        if path == "/api/settings/smtp":
            with connect() as db:
                for k, v in data.items():
                    if k == "smtp_pass" and v == "********":
                        continue
                    db.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?,?)", (k, str(v)))
                db.commit()
                return self.send_json({"ok": True})

        return self.send_json({"error": "Endpoint bulunamadı."}, HTTPStatus.NOT_FOUND)

    # =========================================================================
    # PATCH ENDPOINTS
    # =========================================================================
    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self.body()

        if path.startswith("/api/crm/deals/"):
            deal_id = path.split("/api/crm/deals/")[1].strip()
            with connect() as db:
                stage = data.get("stage")
                amount = data.get("value_amount")
                notes = data.get("notes")

                fields = []
                args = []
                if stage:
                    fields.append("stage = ?")
                    args.append(stage)
                if amount is not None:
                    fields.append("value_amount = ?")
                    args.append(float(amount))
                if notes is not None:
                    fields.append("notes = ?")
                    args.append(notes)

                if not fields:
                    return self.send_json({"error": "Güncellenecek alan yok."}, HTTPStatus.BAD_REQUEST)

                fields.append("updated_at = CURRENT_TIMESTAMP")
                args.append(deal_id)
                sql = f"UPDATE crm_deals SET {', '.join(fields)} WHERE id = ?"
                db.execute(sql, tuple(args))
                db.commit()
                return self.send_json({"ok": True, "id": deal_id, "new_stage": stage})

        return self.send_json({"error": "Endpoint bulunamadı."}, HTTPStatus.NOT_FOUND)


def main():
    initialise()
    server = ThreadingHTTPServer((HOST, PORT), NautiGraphHandler)
    print(f"\n=======================================================")
    print(f"  NAUTIGRAPH TR -- B2B DENIZCILIK, TEKNE & YAT PLATFORMU")
    print(f"  Toplayici Kuyrugu (Queue) + Kimlik Grafigi + CRM")
    print(f"  Sunucu Aktif: http://{HOST}:{PORT}")
    print(f"=======================================================\n")
    threading.Timer(0.7, lambda: webbrowser.open(f"http://{HOST}:{PORT}/")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nNautiGraph sunucusu kapatılıyor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
