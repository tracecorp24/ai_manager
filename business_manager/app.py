from __future__ import annotations

import json
import mimetypes
import sqlite3
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from database import ROOT, connect, initialise, rows

HOST = "127.0.0.1"
PORT = 8765
FRONTEND = ROOT / "frontend"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[business_manager] {self.address_string()} - {fmt % args}")

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/dashboard":
            with connect() as db:
                result = {
                    "companies": db.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
                    "active_jobs": db.execute("SELECT COUNT(*) FROM job_postings WHERE status='Aktif'").fetchone()[0],
                    "opportunities": db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],
                    "demo_companies": db.execute("SELECT COUNT(*) FROM companies WHERE registration_no LIKE 'BM-DEMO-%'").fetchone()[0],
                }
            return self.send_json(result)
        if parsed.path == "/api/companies":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            like = f"%{query}%"
            return self.send_json(rows("SELECT * FROM companies WHERE name LIKE ? OR registration_no LIKE ? ORDER BY name LIMIT 200", (like, like)))
        if parsed.path == "/api/job-postings":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            like = f"%{query}%"
            return self.send_json(rows("""SELECT j.*, c.name company_name FROM job_postings j JOIN companies c ON c.id=j.company_id
                WHERE j.title LIKE ? OR c.name LIKE ? ORDER BY j.published_at DESC, j.id DESC""", (like, like)))
        if parsed.path == "/api/opportunities":
            return self.send_json(rows("SELECT o.*, c.name company_name FROM opportunities o JOIN companies c ON c.id=o.company_id ORDER BY o.id DESC"))
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "product": "business_manager"})
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            data = self.body()
            with connect() as db:
                if parsed.path == "/api/companies":
                    if not data.get("name"):
                        return self.send_json({"error": "Şirket adı zorunludur."}, HTTPStatus.BAD_REQUEST)
                    cur = db.execute("INSERT INTO companies(registration_no,name,address,district,status,phone,email,sector,notes) VALUES(?,?,?,?,?,?,?,?,?)", tuple(data.get(k) for k in ("registration_no","name","address","district","status","phone","email","sector","notes")))
                    return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
                if parsed.path == "/api/job-postings":
                    if not data.get("title") or not data.get("company_id"):
                        return self.send_json({"error": "İlan başlığı ve şirket zorunludur."}, HTTPStatus.BAD_REQUEST)
                    cur = db.execute("INSERT INTO job_postings(company_id,title,location,work_type,description,requirements,salary,status,deadline) VALUES(?,?,?,?,?,?,?,?,?)", tuple(data.get(k) for k in ("company_id","title","location","work_type","description","requirements","salary","status","deadline")))
                    return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
                if parsed.path == "/api/opportunities":
                    cur = db.execute("INSERT INTO opportunities(company_id,name,stage,amount,notes) VALUES(?,?,?,?,?)", tuple(data.get(k) for k in ("company_id","name","stage","amount","notes")))
                    return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
        except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return self.send_json({"error": "Endpoint bulunamadı."}, HTTPStatus.NOT_FOUND)


def main():
    initialise()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Business Manager hazır: http://{HOST}:{PORT}")
    threading.Timer(0.7, lambda: webbrowser.open(f"http://{HOST}:{PORT}/")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatılıyor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
