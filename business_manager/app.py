from __future__ import annotations

import json
import mimetypes
import os
import re
import smtplib
import sqlite3
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from database import DB_PATH, ROOT, connect, initialise, row_to_dict, rows

HOST = "127.0.0.1"
PORT = 8765
FRONTEND = ROOT / "frontend"


class NautiGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, fmt, *args):
        # Sadeleştirilmiş konsol logu
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

        # 2. Şirket Listesi & Filtreleme (Keşif & ICP Motoru)
        if path == "/api/companies":
            q = params.get("q", [""])[0].strip().lower()
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
                    # İlgili kontaklar
                    contacts = [dict(r) for r in db.execute("SELECT * FROM contacts WHERE company_id = ? ORDER BY type", (cid,)).fetchall()]
                    # İlgili kaynak kanıtları
                    evidences = [dict(r) for r in db.execute("SELECT * FROM source_evidence WHERE company_id = ? ORDER BY fetched_at DESC", (cid,)).fetchall()]
                    # İlgili satın alma niyet sinyalleri
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

        # 3. Tekil Şirket Detayı (Firma Kartı Çekmecesi)
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
                    # İstatistikler
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

        # 7. CRM Fırsatları & Satış Boru Hattı
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
                # Parolayı gizle
                if "smtp_pass" in settings:
                    settings["smtp_pass"] = "********" if settings["smtp_pass"] else ""
                return self.send_json(settings)

        # 10. CSV Dışa Aktarma (Export)
        if path == "/api/export/csv":
            with connect() as db:
                comps = db.execute("SELECT * FROM companies WHERE merged_into IS NULL ORDER BY icp_score DESC").fetchall()
                csv_lines = [
                    "VKN,MERSIS_NO,RESMI_UNVAN,MARKA_ADI,DOMAIN,NACE_KODU,IL,ILCE,CALISAN_BANDI,BILESIK_ICP_SKORU,GUVEN_SKORU,DOGRULANMIS_EPOSTA,TELEFON,HUKUKI_DAYANAK"
                ]
                for c in comps:
                    cid = c["id"]
                    email_row = db.execute("SELECT value FROM contacts WHERE company_id = ? AND type = 'email' LIMIT 1", (cid,)).fetchone()
                    phone_row = db.execute("SELECT value FROM contacts WHERE company_id = ? AND type = 'phone' LIMIT 1", (cid,)).fetchone()
                    email = email_row[0] if email_row else ""
                    phone = phone_row[0] if phone_row else ""
                    legal_name_safe = '"' + c["legal_name"].replace('"', '""') + '"'
                    csv_lines.append(f"{c['vkn']},{c['mersis_no']},{legal_name_safe},{c['short_name']},{c['domain']},{c['nace_code']},{c['province']},{c['district']},{c['employee_band']},{c['icp_score']},{c['trust_score']},{email},{phone},KVKK_md5_2f_Mesru_Menfaat_IYS_Tacir")

                content = "\ufeff" + "\n".join(csv_lines)
                body = content.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename=nautigraph_tr_yat_tasarim_{datetime.now().strftime('%Y%m%d')}.csv")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        # 11. Yasal İYS / Opt-Out Sayfası (Unsubscribe Endpoint)
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

        # Statik dosya rotası
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

        # 1. Yeni Şirket Ekleme / Güncelleme (Entity Resolution ile VKN ve Domain Kontrolü)
        if path == "/api/companies":
            vkn = data.get("vkn", "").strip()
            legal_name = data.get("legal_name", "").strip()
            domain = data.get("domain", "").strip()

            if not legal_name:
                return self.send_json({"error": "Şirket ünvanı zorunludur."}, HTTPStatus.BAD_REQUEST)

            with connect() as db:
                # Deterministik VKN Eşleşmesi
                if vkn:
                    existing = db.execute("SELECT id, legal_name FROM companies WHERE vkn = ?", (vkn,)).fetchone()
                    if existing:
                        return self.send_json({
                            "error": f"VKN Çakışması: Bu VKN ({vkn}) zaten '{existing['legal_name']}' adına kayıtlı.",
                            "existing_id": existing["id"]
                        }, HTTPStatus.CONFLICT)

                cid = data.get("id") or f"cmp-{uuid.uuid4().hex[:8]}"
                sb = data.get("score_breakdown", {})
                db.execute(
                    """INSERT INTO companies (
                        id, vkn, mersis_no, legal_name, short_name, normalized_name, domain,
                        nace_code, nace_desc, province, district, employee_band, employee_est,
                        trust_score, icp_score, score_icp, score_freshness, score_contact,
                        score_intent, score_reachability, icp_reason, tech_stack_json, status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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

                # Varsa ilk kontağı kaydet
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

        # 4. Otomatik E-Posta Sequence Gönderim Motoru (SMTP & Dynamic Variable Engine)
        if path.startswith("/api/campaigns/") and path.endswith("/send"):
            camp_id = path.split("/api/campaigns/")[1].split("/send")[0]
            step_id = data.get("step_id")
            company_ids = data.get("company_ids", [])  # Belirli firmalar veya tüm liste
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

                # Hedef firmaları tespit et
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
                    # Doğrulanmış e-posta ara
                    contact = db.execute("SELECT * FROM contacts WHERE company_id = ? AND type = 'email' AND consent_status != 'opt_out' ORDER BY is_verified DESC LIMIT 1", (cid,)).fetchone()
                    if not contact:
                        continue

                    # Sinyal ve CAD bilgisi
                    sig = db.execute("SELECT label, detail FROM intent_signals WHERE company_id = ? ORDER BY occurred_at DESC LIMIT 1", (cid,)).fetchone()
                    sig_label = sig["label"] if sig else "Sektörel Gelişmeler"
                    sig_detail = sig["detail"] if sig else "Son Teknoloji Yatırımları"

                    try:
                        tech_stack = json.loads(comp["tech_stack_json"] or "[]")
                        cad_tool = tech_stack[0] if tech_stack else "Rhino 3D"
                    except Exception:
                        cad_tool = "3D CAD / Klas Modelleme"

                    # Şablon Değişkenlerini Enterpole Et (Liquid/Jinja2 tarzı)
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

                    # KVKK & İYS Yasal Opt-Out Dipnotu Ekle
                    opt_out_link = f"http://{HOST}:{PORT}/api/email-logs/opt-out?email={contact['value']}&cid={cid}"
                    legal_footer = f"\n\n---\nBu e-posta 6563 sayılı Kanun ve KVKK md. 5/2-f (Meşru Menfaat / Tacir İletişimi) kapsamında {comp['legal_name']} tüzel kişiliğine ticari elektronik ileti olarak iletilmiştir. İletişim listesinden çıkmak için: {opt_out_link}"
                    full_body = body + legal_footer

                    log_id = f"log-{uuid.uuid4().hex[:10]}"
                    smtp_resp = "SMTP 250 2.0.0 OK: Delivered via NautiGraph Sandbox Relay"

                    # Gerçek SMTP Gönderimi (Eğer ayarlandıysa)
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

                    # Log tablosuna kaydet
                    db.execute(
                        """INSERT INTO email_logs (
                            id, campaign_id, step_id, company_id, contact_id, recipient_email,
                            recipient_name, rendered_subject, rendered_body, status, smtp_response, sent_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            log_id,
                            camp_id,
                            step["id"],
                            cid,
                            contact["id"],
                            contact["value"],
                            contact["role_title"] or comp["short_name"],
                            subject,
                            full_body,
                            "sent",
                            smtp_resp,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )

                    # Otomatik CRM Fırsat Aşaması Güncelleme
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

        # 5. E-posta Etkileşimi Simülasyonu (Açılma, Yanıt, Opt-Out)
        if path.startswith("/api/email-logs/") and path.endswith("/interact"):
            log_id = path.split("/api/email-logs/")[1].split("/interact")[0]
            action = data.get("action")  # 'open', 'reply', 'opt_out'
            with connect() as db:
                log = db.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,)).fetchone()
                if not log:
                    return self.send_json({"error": "Log bulunamadı."}, HTTPStatus.NOT_FOUND)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if action == "open":
                    db.execute("UPDATE email_logs SET status = 'opened', opened_at = ? WHERE id = ?", (now, log_id))
                elif action == "reply":
                    db.execute("UPDATE email_logs SET status = 'replied', replied_at = ? WHERE id = ?", (now, log_id))
                    # Yanıt geldiğinde CRM fırsatını Demo/Keşif aşamasına taşı
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

        # 7. Manuel Tekilleştirme Eylemi (Merge / Reject)
        if path == "/api/health/dedup-action":
            dq_id = data.get("id")
            action = data.get("action")  # 'merge' veya 'reject'
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

        # CRM Deal Aşaması Değiştirme (Kanban Sürükle-Bırak)
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
    print(f"  NAUTIGRAPH TR — B2B DENİZCİLİK & YAT KİMLİK GRAFİĞİ")
    print(f"  Sunucu Aktif: http://{HOST}:{PORT}")
    print(f"=======================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nNautiGraph sunucusu kapatılıyor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
