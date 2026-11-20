from __future__ import annotations

import json
import sqlite3
import uuid
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
    """Veritabanı tablolarını kurar ve NautiGraph tohum verilerini yükler."""
    with connect() as db:
        db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        count = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        if count == 0 and SEED_JSON.exists():
            _seed_from_nautigraph(db)
        _seed_default_campaigns_and_deals(db)
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
        db.execute(
            """INSERT OR REPLACE INTO companies (
                id, vkn, mersis_no, legal_name, short_name, normalized_name, domain,
                nace_code, nace_desc, province, district, employee_band, employee_est,
                trust_score, icp_score, score_icp, score_freshness, score_contact,
                score_intent, score_reachability, icp_reason, tech_stack_json, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                c.get("vkn"),
                c.get("mersis_no"),
                c.get("legal_name"),
                c.get("short_name"),
                c.get("legal_name", "").upper(),
                c.get("domain"),
                c.get("nace_code"),
                c.get("nace_desc"),
                c.get("province"),
                c.get("district"),
                c.get("employee_band"),
                c.get("employee_est"),
                float(c.get("trust_score", 0)),
                float(c.get("icp_score", 0)),
                float(sb.get("icp", 0)),
                float(sb.get("freshness", 0)),
                float(sb.get("contact", 0)),
                float(sb.get("intent", 0)),
                float(sb.get("reachability", 0)),
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
                    ct.get("role"),
                    1 if ct.get("verified") else 0,
                    ct.get("smtp", "Doğrulanmış"),
                    ct.get("iys", "KVKK_md5_2f_Tacir"),
                    "opt_in" if ct.get("verified") else "pending",
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
                    ev.get("source"),
                    ev.get("cls"),
                    ev.get("rule"),
                    ev.get("hash"),
                    float(ev.get("trust", 85)),
                    ev.get("date", "2026-11-01")
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
                    sig.get("type"),
                    sig.get("label"),
                    sig.get("detail"),
                    sig.get("date", "Yakın zamanda")
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
    print(f"[database] {len(companies)} denizcilik/yat şirketi veritabanına başarıyla aktarıldı.")


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
                "Türkiye Yat Tersaneleri & Tasarım Ofisleri B2B Çözüm Tanıtımı",
                "lst-1",
                "running",
                "NautiGraph Denizcilik Teknolojileri",
                "outreach@nautigraph.marine",
                "emin@nautigraph.marine"
            )
        )

        # Adım 1: İlk Temas (Kişiselleştirilmiş CAD/CFD Değer Önerisi)
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

        # Adım 2: Takip (Case Study & 45m Kompozit Yat Örneği)
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

        # Adım 3: Son İletişim / Ayrılış Mesajı
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

    # 2. Varsayılan CRM Fırsatları (Kanban Tahtası İçin)
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
    db.execute(
        "INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_mode', 'sandbox')"
    )
    db.execute(
        "INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_host', 'smtp.gmail.com')"
    )
    db.execute(
        "INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_port', '587')"
    )
    db.execute(
        "INSERT OR IGNORE INTO system_settings (key, value) VALUES ('smtp_user', 'outreach@nautigraph.marine')"
    )
