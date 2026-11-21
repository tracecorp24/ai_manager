"""
NautiGraph TR — Scrapling Canlı Veri Kazıma ve Zenginleştirme Motoru
Bu modül, Scrapling kütüphanesini (Fetcher, Adaptive Selectors, Regex Ayrıştırma)
kullanarak B2B yat tasarım şirketlerinin web sitelerinden ve dizinlerinden
iletişim ve CAD teknolojisi verisi çeker.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List, Optional

try:
    from scrapling.fetchers import Fetcher
    SCRAPLING_AVAILABLE = True
except Exception as e:
    SCRAPLING_AVAILABLE = False
    Fetcher = None


class MaritimeScraplingEngine:
    def __init__(self, timeout: int = 8):
        self.timeout = timeout

    @property
    def is_available(self) -> bool:
        return SCRAPLING_AVAILABLE and Fetcher is not None

    def enrich_company_website(self, domain_or_url: str) -> Dict[str, Any]:
        """
        Hedef şirketin web sitesini (Impressum, iletişim, hakkımızda)
        Scrapling Fetcher ile tarayarak e-posta, telefon ve CAD araçlarını çıkarır.
        """
        result = {
            "success": False,
            "emails": [],
            "phones": [],
            "detected_cad": [],
            "scraped_urls": []
        }

        if not self.is_available:
            return result

        # Temiz URL oluştur
        raw = domain_or_url.strip()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            base_url = f"https://{raw}"
        else:
            base_url = raw

        parsed = urllib.parse.urlparse(base_url)
        domain = parsed.netloc or parsed.path

        # Taranacak kritik sayfalar (Impressum & İletişim odaklı)
        target_paths = ["", "/impressum", "/iletisim", "/contact", "/mentions-legales", "/hakkimizda", "/about"]
        
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        phone_pattern = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3}[-.\s]?\d{2}[-.\s]?\d{2}')
        cad_keywords = ["rhino", "rhino 3d", "autocad", "maxsurf", "siemens nx", "catia", "solidworks", "orca3d", "ansys"]

        for path in target_paths:
            full_url = f"https://{domain}{path}"
            try:
                resp = Fetcher.get(full_url, timeout=self.timeout)
                if resp.status == 200:
                    result["scraped_urls"].append(full_url)
                    text = resp.text

                    # E-postaları ayıkla
                    for em in email_pattern.findall(text):
                        em_clean = em.lower().strip()
                        if not em_clean.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".js")):
                            if em_clean not in result["emails"]:
                                result["emails"].append(em_clean)

                    # Telefonları ayıkla
                    for ph in phone_pattern.findall(text):
                        ph_clean = ph.strip()
                        if len(ph_clean) >= 10 and ph_clean not in result["phones"]:
                            result["phones"].append(ph_clean)

                    # CAD araçlarını tespit et
                    text_lower = text.lower()
                    for kw in cad_keywords:
                        if kw in text_lower:
                            kw_title = kw.title() if kw != "siemens nx" else "Siemens NX"
                            if kw_title not in result["detected_cad"]:
                                result["detected_cad"].append(kw_title)

                    if result["emails"] and len(result["scraped_urls"]) >= 2:
                        break  # Yeterli iletişim verisi bulundu
            except Exception:
                continue

        result["success"] = len(result["emails"]) > 0 or len(result["phones"]) > 0 or len(result["detected_cad"]) > 0
        return result
