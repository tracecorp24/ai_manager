from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "business_manager.db"
SCHEMA_PATH = ROOT / "schema.sql"
SEED_JSON = DATA_DIR / "nautigraph_seed.json"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def row_to_dict(r: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if r is None:
        return None
    return {k: r[k] for k in r.keys()}


def rows(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with connect() as db:
        cur = db.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def initialise() -> None:
    """Veritabanı tablolarını kurar, eksik sütunları migre eder ve tohum verilerini yükler."""
    with connect() as db:
        # Migrasyon: İndekslerden önce mevcut tablonun eksik sütunlarını ekle
        table_exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'").fetchone()
        if table_exists:
            cols = [r[1] for r in db.execute("PRAGMA table_info(companies)").fetchall()]
            if "country" not in cols:
                db.execute("ALTER TABLE companies ADD COLUMN country TEXT NOT NULL DEFAULT 'Türkiye'")
            if "industry_sector" not in cols:
                db.execute("ALTER TABLE companies ADD COLUMN industry_sector TEXT DEFAULT 'Gemi İnşa & Yat Tasarım'")

        jobs_table = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawler_jobs'").fetchone()
        if jobs_table:
            jcols = [r[1] for r in db.execute("PRAGMA table_info(crawler_jobs)").fetchall()]
            if "city" not in jcols:
                db.execute("ALTER TABLE crawler_jobs ADD COLUMN city TEXT DEFAULT 'Genel'")


        db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        count = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        if count == 0 and SEED_JSON.exists():
            _seed_from_nautigraph(db)
        
        _seed_international_and_sectors(db)
        _seed_default_campaigns_and_deals(db)
        _seed_crawler_jobs(db)
        db.commit()


def _seed_from_nautigraph(db: sqlite3.Connection) -> None:
    try:
        data = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[database] Tohum verisi okunamadı: {e}")
        return

    companies = data.get("companies", [])
    for c in companies:
        cid = c.get("id")
        sb = c.get("score_breakdown", {})
        nace = c.get("nace_code", "71.12")
        sector = "Mega Yat Tersaneleri" if nace == "30.12" else "Gemi İnşa & Yat Tasarım"

        db.execute(
            """INSERT OR REPLACE INTO companies (
                id, vkn, mersis_no, legal_name, short_name, normalized_name, domain,
                nace_code, nace_desc, country, industry_sector, province, district, employee_band, employee_est,
                trust_score, icp_score, score_icp, score_freshness, score_contact,
                score_intent, score_reachability, icp_reason, tech_stack_json, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                c.get("vkn"),
                c.get("mersis_no"),
                c.get("legal_name"),
                c.get("short_name"),
                c.get("legal_name", "").upper(),
                c.get("domain"),
                nace,
                c.get("nace_desc"),
                "Türkiye",
                sector,
                c.get("province"),
                c.get("district"),
                c.get("employee_band"),
                c.get("employee_est"),
                float(c.get("trust_score", 0)),
                float(c.get("icp_score", 0)),
                float(sb.get("icp", 90)),
                float(sb.get("freshness", 85)),
                float(sb.get("contact", 85)),
                float(sb.get("intent", 88)),
                float(sb.get("reachability", 85)),
                c.get("icp_reason", ""),
                json.dumps(c.get("tech_stack", []), ensure_ascii=False),
                "active"
            )
        )

        # 1. Contacts
        for idx, ct in enumerate(c.get("contacts", [])):
            ct_id = f"ct-{cid}-{idx+1}"
            db.execute(
                """INSERT OR REPLACE INTO contacts (
                    id, company_id, type, value, role_title, is_verified,
                    verification_method, legal_basis, consent_status, confidence
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    ct_id,
                    cid,
                    ct.get("type"),
                    ct.get("value"),
                    ct.get("role") or ct.get("role_title") or "Yetkili",
                    1 if ct.get("verified") or ct.get("is_verified") else 0,
                    ct.get("smtp") or ct.get("verification_method") or "SMTP 250 OK",
                    ct.get("iys") or ct.get("legal_basis") or "KVKK_md5_2f_Tacir",
                    "opt_in" if ct.get("verified") or ct.get("is_verified") else "pending",
                    float(ct.get("confidence", 0.95))
                )
            )

        # 2. Source Evidences (MinIO Kanıt İzi)
        for idx, ev in enumerate(c.get("evidences", [])):
            ev_id = f"ev-{cid}-{idx+1}"
            db.execute(
                """INSERT OR REPLACE INTO source_evidence (
                    id, company_id, source_name, source_class, resolution_rule,
                    raw_hash, trust_weight, fetched_at
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    ev_id,
                    cid,
                    ev.get("source") or ev.get("source_name") or "Ticaret Sicili",
                    ev.get("cls") or ev.get("source_class") or "A",
                    ev.get("rule") or ev.get("resolution_rule") or "VKN Kesin Eşleşme",
                    ev.get("hash") or ev.get("raw_hash") or uuid.uuid4().hex,
                    float(ev.get("trust") or ev.get("trust_weight") or 85),
                    ev.get("date") or ev.get("fetched_at") or "2026-11-01"
                )
            )

        # 3. Intent Signals
        for idx, sig in enumerate(c.get("signals", [])):
            sig_id = f"sig-{cid}-{idx+1}"
            db.execute(
                """INSERT OR REPLACE INTO intent_signals (
                    id, company_id, signal_type, label, detail, occurred_at
                ) VALUES (?,?,?,?,?,?)""",
                (
                    sig_id,
                    cid,
                    sig.get("type") or sig.get("signal_type") or "Fuar",
                    sig.get("label") or "Sektörel Gelişme",
                    sig.get("detail") or "Aktif satın alma sinyali tespit edildi.",
                    sig.get("date") or sig.get("occurred_at") or "Yakın zamanda"
                )
            )

    # 4. Saved Lists
    for lst in data.get("saved_lists", []):
        lid = lst.get("id")
        db.execute(
            """INSERT OR REPLACE INTO saved_lists (id, name, type, description)
            VALUES (?,?,?,?)""",
            (lid, lst.get("name"), lst.get("type"), f"NautiGraph hedef listesi: {lst.get('name')}")
        )
        for comp_id in lst.get("companyIds", []):
            db.execute(
                """INSERT OR IGNORE INTO list_memberships (list_id, company_id)
                VALUES (?,?)""",
                (lid, comp_id)
            )

    # 5. Dedup Queue
    for dq in data.get("dedup_queue", []):
        dq_id = dq.get("id")
        left = dq.get("left", {})
        right = dq.get("right", {})
        db.execute(
            """INSERT OR REPLACE INTO dedup_queue (
                id, similarity, reason, left_name, left_source, left_address,
                right_name, right_source, right_address, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                dq_id,
                float(dq.get("similarity", 0.90)),
                dq.get("reason"),
                left.get("name", ""),
                left.get("source", ""),
                left.get("address", ""),
                right.get("name", ""),
                right.get("source", ""),
                right.get("address", ""),
                "pending"
            )
        )
    print(f"[database] {len(companies)} denizcilik şirketi başarıyla tohumlandı.")


def _seed_international_and_sectors(db: sqlite3.Connection) -> None:
    """İtalya, Hollanda, Yunanistan ve Almanya'dan uluslararası yat şirketleri ve sektör dağılımı ekler."""
    intl_comps = [
        # İtalya
        ("cmp-it-01", "IT09182736451", "Sanlorenzo Yacht Engineering SpA", "Sanlorenzo Yachts", "sanlorenzoyacht.it", "30.12", "İtalya", "Mega Yat Tersaneleri", "Viareggio", "Toscana", "200+", 95, 94, '["CATIA V5", "Rhino 3D", "Siemens NX"]', "Dünyanın en büyük 3 mega yat üreticisinden biri, Viareggio tersanesi"),
        ("cmp-it-02", "IT04512398712", "Benetti Custom Naval Architecture Srl", "Benetti Custom", "benettiyachts.it", "71.12", "İtalya", "Gemi İnşa & Yat Tasarım", "Livorno", "Toscana", "51-200", 94, 92, '["Rhino 3D", "Orca3D", "ANSYS Fluent"]', "60m+ çelik ve alüminyum gövde stabilite ve hidrodinamik tasarım ofisi"),
        ("cmp-it-03", "IT08871234901", "Overmarine Group Mangusta SpA", "Mangusta Yachts", "mangustayachts.com", "30.12", "İtalya", "Mega Yat Tersaneleri", "Viareggio", "Toscana", "200+", 92, 90, '["Rhino 3D", "Maxsurf", "AutoCAD Marine"]', "Yüksek hızlı deplasman motoryat imalatı"),
        # Hollanda
        ("cmp-nl-01", "NL801234567B01", "Feadship Royal Van Lent Shipyard BV", "Feadship Royal", "feadship.nl", "30.12", "Hollanda", "Mega Yat Tersaneleri", "Aalsmeer", "North Holland", "200+", 99, 96, '["ShipConstructor", "CATIA Marine", "ANSYS Fluent"]', "Hollanda kraliyet süperyat tersanesi, 80m+ özel yapım projeler"),
        ("cmp-nl-02", "NL819283746B01", "De Voogt Naval Architects BV", "De Voogt Naval", "devoogt.feadship.nl", "71.12", "Hollanda", "Gemi İnşa & Yat Tasarım", "Haarlem", "North Holland", "51-200", 98, 95, '["Rhino 3D", "Orca3D", "CFD Numeca", "Maxsurf"]', "Dünya lideri bağımsız naval architecture stüdyosu"),
        ("cmp-nl-03", "NL845612378B01", "Heesen Yachts Sales & Engineering BV", "Heesen Yachts", "heesenyachts.com", "30.12", "Hollanda", "Mega Yat Tersaneleri", "Oss", "North Brabant", "200+", 96, 92, '["SolidWorks Marine", "ShipConstructor", "Siemens NX"]', "Alüminyum gövdeli hızlı süperyat imalatı"),
        # Yunanistan
        ("cmp-gr-01", "EL998877665", "Aegean Marine Dynamics Ltd", "Aegean Marine GR", "aegeanmarine.gr", "71.12", "Yunanistan", "Gemi İnşa & Yat Tasarım", "Pire", "Attika", "11-50", 91, 88, '["Rhino 3D", "Maxsurf", "AutoCAD Marine"]', "Ege Denizi adaları için hızlı katamaran ve özel gulet mühendisliği"),
        ("cmp-gr-02", "EL912345678", "Golden Yachts Shipyard Hellas SA", "Golden Yachts", "goldenyachts.gr", "30.12", "Yunanistan", "Mega Yat Tersaneleri", "Perama", "Attika", "51-200", 93, 89, '["CATIA Marine", "Rhino 3D"]', "70m+ lüks motoryat imalatı ve kapsamlı refit tersanesi"),
        # Almanya
        ("cmp-de-01", "DE123456789", "Lürssen Yacht Engineering GmbH", "Lürssen Yachts", "luerssen.com", "30.12", "Almanya", "Mega Yat Tersaneleri", "Bremen", "Bremen", "200+", 99, 97, '["Siemens NX", "CATIA Marine", "ANSYS Fluent"]', "Dünyanın en büyük mega yat üreticisi (100m+)"),
        ("cmp-de-02", "DE987654321", "Dykstra Naval Architects GmbH", "Dykstra Naval", "dykstra.com", "71.12", "Almanya", "Gemi İnşa & Yat Tasarım", "Hamburg", "Hamburg", "11-50", 97, 94, '["Rhino 3D", "Maxsurf", "Gurit Composites"]', "Performans yelkenli süperyat ve DynaRig sistem mimarları")
    ]

    for item in intl_comps:
        cid, vkn, legal_name, short_name, domain, nace, country, sector, prov, dist, band, trust, icp, tech, reason = item
        db.execute(
            """INSERT OR IGNORE INTO companies (
                id, vkn, legal_name, short_name, normalized_name, domain, nace_code,
                country, industry_sector, province, district, employee_band, trust_score,
                icp_score, score_icp, score_freshness, score_contact, score_intent, score_reachability,
                icp_reason, tech_stack_json, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid, vkn, legal_name, short_name, legal_name.upper(), domain, nace,
                country, sector, prov, dist, band, trust, icp,
                94, 90, 92, 88, 86, reason, tech, "active"
            )
        )
        # Kontak
        db.execute(
            """INSERT OR IGNORE INTO contacts (id, company_id, type, value, role_title, is_verified, verification_method, legal_basis, consent_status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (f"ct-{cid}-1", cid, "email", f"info@{domain}", "Tasarım & Satınalma Direktörü", 1, "SMTP 250 OK", "KVKK_md5_2f_Tacir", "opt_in")
        )
        # Kanıt
        sources = [
            ("Resmi Ticaret Sicili / EU Chamber", "A", "AB Sicil Numarası Kesin Eşleşme"),
            ("Monaco Yacht Show / Cannes Festivali", "B", "Resmi Fuar Katılımcı Listesi"),
            ("Google Places & Marine POI", "B", "E.164 Geocode Doğrulama"),
            ("JSON-LD Organization Crawler", "C", "Domain & Schema.org Doğrulama")
        ]
        for idx, (sname, scls, srule) in enumerate(sources, 1):
            db.execute(
                """INSERT OR IGNORE INTO source_evidence (id, company_id, source_name, source_class, resolution_rule, raw_hash, trust_weight)
                VALUES (?,?,?,?,?,?,?)""",
                (f"ev-{cid}-{idx}", cid, sname, scls, srule, uuid.uuid4().hex, 90)
            )
        # Sinyal
        db.execute(
            """INSERT OR IGNORE INTO intent_signals (id, company_id, signal_type, label, detail, occurred_at)
            VALUES (?,?,?,?,?,?)""",
            (f"sig-{cid}-1", cid, "Fuar", "MetsTrade & Monaco '26 Katılımcısı", f"{country} pavilyonunda yeni gövde konsepti lansmanı", "1 hafta önce")
        )


def _seed_crawler_jobs(db: sqlite3.Connection) -> None:
    """5 Ülke x 5 Büyük Şehir x 5 Sektörel Title = 125 Master Kuyruk Görevini (100'er Hedef Kota) Tohumlar."""
    from test_queue_config import MASTER_QUEUE
    
    cur_count = db.execute("SELECT COUNT(*) FROM crawler_jobs").fetchone()[0]
    if cur_count >= 125:
        return

    now = datetime.now()
    task_idx = 1
    
    for c_group in MASTER_QUEUE:
        country = c_group["country"]
        city = c_group["city"]
        sources_json = json.dumps(c_group["sources"], ensure_ascii=False)
        
        for title in c_group["titles"]:
            job_id = f"job-{task_idx:03d}"
            target_count = 100
            
            # İlk 1 görev çalışıyor (running), sonraki 4 görev tamamlandı (completed), kalanı bekliyor (queued)
            if task_idx == 1:
                status = "running"
                crawled = 34
                new_c = 12
                upd = 8
                unch = 14
                msg = f"Çalışıyor - {crawled}/100 çekildi. {city} bölgesinde tarama devam ediyor."
                st_time = (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                cp_time = None
            elif task_idx in (2, 3, 4, 5):
                status = "completed"
                crawled = 100 if task_idx % 2 == 0 else 88
                new_c = int(crawled * 0.4)
                upd = int(crawled * 0.25)
                unch = crawled - new_c - upd
                msg = f"100 hedef kotasından {crawled} adet çekildi; tamamlanarak sonraki göreve aktarıldı."
                st_time = (now - timedelta(hours=task_idx)).strftime("%Y-%m-%d %H:%M:%S")
                cp_time = (now - timedelta(hours=task_idx - 1, minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                status = "queued"
                crawled = 0
                new_c = 0
                upd = 0
                unch = 0
                msg = "Kuyrukta bekliyor (Hedef: 100 İlan / Şirket - Bulamazsa otomatik pas geçme aktif)"
                st_time = (now + timedelta(minutes=task_idx * 5)).strftime("%Y-%m-%d %H:%M:%S")
                cp_time = None
                
            sb_json = json.dumps({s: int(crawled / max(len(c_group["sources"]), 1)) for s in c_group["sources"]}, ensure_ascii=False)
            
            db.execute("""
                INSERT OR REPLACE INTO crawler_jobs (
                    id, country, city, industry, sources_json, status, target_count,
                    crawled_count, new_count, updated_count, unchanged_count,
                    source_breakdown_json, message, started_at, completed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                job_id, country, city, title, sources_json, status, target_count,
                crawled, new_c, upd, unch, sb_json, msg, st_time, cp_time
            ))
            task_idx += 1
    
    db.commit()
    print(f"[database] 125 Master Kuyruk Görevi başarıyla veritabanına işlendi.")


def _seed_default_campaigns_and_deals(db: sqlite3.Connection) -> None:
    # 1. Varsayılan E-posta Kampanyası ve Adımları
    camp_id = "camp-yacht-01"
    cur = db.execute("SELECT COUNT(*) FROM email_campaigns WHERE id=?", (camp_id,)).fetchone()[0]
    if cur == 0:
        db.execute(
            """INSERT INTO email_campaigns (id, name, target_list_id, status, from_name, from_email, reply_to)
            VALUES (?,?,?,?,?,?,?)""",
            (
                camp_id,
                "Türkiye & Akdeniz Yat Tersaneleri B2B Mühendislik Çözüm Tanıtımı",
                "lst-1",
                "running",
                "NautiGraph Denizcilik Teknolojileri",
                "outreach@nautigraph.marine",
                "emin@nautigraph.marine"
            )
        )

        # Adım 1
        db.execute(
            """INSERT INTO sequence_steps (id, campaign_id, step_number, title, delay_days, subject_template, body_template)
            VALUES (?,?,?,?,?,?,?)""",
            (
                "step-1",
                camp_id,
                1,
                "Adım 1: İlk Temas & Sektörel Değer Teklifi",
                0,
                "{{firma_adi}} için {{tespit_edilen_cad}} optimizasyonu & {{son_sinyal}}",
                """Sayın {{yetkili_ad}},

{{firma_adi}} ekibinin {{sehir}} bölgesinde yürüttüğü yüksek standartlı tekne mühendisliği çalışmalarını ve son olarak {{son_sinyal}} gelişmesini takdirle takip ediyoruz.

Özellikle {{tespit_edilen_cad}} ve klas modellemelerinde mühendislik ekiplerinin karşılaştığı hidrodinamik analiz darboğazlarını %40 oranında hafifleten yeni nesil çözümümüzü Türkiye'nin önde gelen yat tasarım ofisleriyle buluşturuyoruz.

Önümüzdeki hafta 15 dakikalık kısa bir teknik keşif görüşmesi gerçekleştirebilir miyiz?

Saygılarımızla,
NautiGraph Denizcilik Çözümleri Ekibi
https://nautigraph.marine"""
            )
        )

        # Adım 2
        db.execute(
            """INSERT INTO sequence_steps (id, campaign_id, step_number, title, delay_days, subject_template, body_template)
            VALUES (?,?,?,?,?,?,?)""",
            (
                "step-2",
                camp_id,
                2,
                "Adım 2: Vaka Analizi & Klas Onay Süresi",
                3,
                "Takip: {{firma_adi}} yat projelerinde klas onay sürecini hızlandırma",
                """Merhaba {{yetkili_ad}},

Geçtiğimiz günlerde ilettiğim mesajıma ek olarak; benzer bir 45m kompozit yat projesinde Lloyd's Register klas onay süresini 3 haftadan 6 güne indiren vaka analizimizi sizinle paylaşmak istedim.

Detaylı teknik raporu incelemek veya projenize özel bir demo görmek isterseniz memnuniyetle yanıtlarım.

İyi çalışmalar dilerim."""
            )
        )

        # Adım 3
        db.execute(
            """INSERT INTO sequence_steps (id, campaign_id, step_number, title, delay_days, subject_template, body_template)
            VALUES (?,?,?,?,?,?,?)""",
            (
                "step-3",
                camp_id,
                3,
                "Adım 3: Son Çağrı & İletişim Hattı",
                7,
                "{{firma_adi}} ile iletişim kanallarımız açık",
                """Merhaba {{yetkili_ad}},

Şu aşamada gündeminizin yoğun olduğunu tahmin edebiliyorum. Sizi gereksiz e-postalarla meşgul etmek istemem.

Yat tasarım ve tersane mühendisliği optimizasyonuna ihtiyaç duyduğunuzda dilediğiniz zaman bu e-posta üzerinden doğrudan bana ulaşabilirsiniz.

Başarılı ve pruvanızın neta olduğu projeler dilerim."""
            )
        )

    # 2. Varsayılan CRM Fırsatları
    deals_count = db.execute("SELECT COUNT(*) FROM crm_deals").fetchone()[0]
    if deals_count == 0:
        sample_deals = [
            ("deal-01", "cmp-01", "Aegean Naval - Rhino/Orca3D CFD Entegrasyonu", "Yeni", 45000, "EUR", "Emin A.", "CFD ve Klas Onay Mühendislik Lisansı"),
            ("deal-02", "cmp-02", "Blue Horizon - 3. Hangar Tersane ERP & Proje Yönetimi", "İletişim Kuruldu", 120000, "EUR", "Emin A.", "Antalya Serbest Bölge Tersane Otomasyonu"),
            ("deal-03", "cmp-03", "Karya Yacht - 28m Katamaran Stabilite Hesaplama", "Demo/Keşif", 35000, "EUR", "Emin A.", "Karbon-Epoksi Kompozit Yapısal Analiz"),
            ("deal-04", "cmp-04", "Marmara Hydro-Tech - Klas Danışmanlık Projesi", "Teklif Verildi", 58000, "EUR", "Emin A.", "Altınova Tersaneler Bölgesi Gemi Stabilite Modülü"),
            ("deal-05", "cmp-05", "Bosphorus Custom - 42m Çelik Motoryat Donatım", "Kazanıldı", 85000, "EUR", "Emin A.", "Tuzla Tersanesi Tam Donatım Takip Sistemi")
        ]
        for d in sample_deals:
            db.execute(
                """INSERT INTO crm_deals (id, company_id, title, stage, value_amount, currency, assigned_to, proposal_scope)
                VALUES (?,?,?,?,?,?,?,?)""",
                d
            )

    # 3. Varsayılan Sistem Ayarları
    db.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_mode', 'sandbox')")
    db.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_host', 'smtp.gmail.com')")
    db.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_port', '587')")
    db.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_user', 'outreach@nautigraph.marine')")
