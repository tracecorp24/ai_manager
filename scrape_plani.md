# 🌐 Küresel ve Türkiye B2B Şirket Kimlik Grafiği & Veri Toplama Ana Planı (Master Architecture Plan)

> **Sistem:** NautiGraph B2B Denizcilik, Tekne & Yat Tasarımı, Tersane & Mühendislik Kimlik Grafiği  
> **Temel İlke:** "Kazımasız Mimari Öncelikli" (Zero-Scrape First) + Resmi Açık Veri Yığınları + Açık POI Katmanı + Hibrit Scrapling Otomasyonu  
> **Hedef Coğrafya:** Türkiye 🇹🇷, Almanya 🇩🇪, Hollanda 🇳🇱, İngiltere 🇬🇧, Fransa 🇫🇷 ve Akdeniz Havzası

---

## İçindekiler
1. [Yönetici Özeti ve Temel Felsefe](#1-yönetici-özeti-ve-temel-felsefe)
2. [Scrapling Mimarisi, Yetenekleri ve Karar Matrisi](#2-scrapling-mimarisi-yetenekleri-ve-karar-matrisi)
3. [Fiziksel İşletme ve POI Katmanı: Google Maps Alternatifleri](#3-fiziksel-işletme-ve-poi-katmanı-google-maps-alternatifleri)
4. [Beş Hedef Ülkenin Resmi Kayıt ve Açık Veri Envanteri](#4-beş-hedef-ülkenin-resmi-kayıt-ve-açık-veri-envanteri)
   - [Türkiye 🇹🇷](#türkiye--en-zor-ülke-merkezi-açık-veri-yok)
   - [Almanya 🇩🇪](#almanya--zengin-açık-veri-ekosistemi)
   - [Hollanda 🇳🇱](#hollanda--kvk-merkezli-hibrit-model)
   - [İngiltere 🇬🇧](#ingiltere--en-açık-ve-erişilebilir-ülke)
   - [Fransa 🇫🇷](#fransa--base-sirene-ve-merkezi-api-ekosistemi)
5. [Ülke-Üstü ve Sınır Ötesi Doğrulama Kaynakları](#5-ülke-üstü-ve-sınır-ötesi-doğrulama-kaynakları)
6. [Uçtan Uca B2B Veri Boru Hattı ve Entity Resolution](#6-uçtan-uca-b2b-veri-boru-hattı-ve-entity-resolution)
7. [Scrapling Üretim Hazır Kod İskeleti](#7-scrapling-üretim-hazır-kod-iskeleti)
8. [Hukuki Çerçeve ve Uyumluluk (KVKK, GDPR, İYS)](#8-hukuki-çerçeve-ve-uyumluluk-kvkk-gdpr-iys)
9. [NautiGraph TR Sistem Entegrasyonu](#9-nautigraph-tr-sistem-entegrasyonu)
10. [Doğrulanmış Kaynaklar, Resmi Portallar ve Canlı API Bağlantıları Dizini](#10-doğrulanmış-kaynaklar-resmi-portallar-ve-canlı-api-bağlantıları-dizini)

---

## 1. Yönetici Özeti ve Temel Felsefe

B2B şirket ve müşteri istihbaratı oluştururken yapılan en büyük hata, **"her kaynaktan her veriyi web scraping ile kazımaya çalışmaktır."** Bu yaklaşım; IP banları, Cloudflare engelleri, kırılan DOM seçicileri ve yüksek proxy/sunucu maliyetleriyle hızla çöker.

En verimli ve ölçeklenebilir yaklaşım **üç katmanlı hibrit modeldir**:
1. **Omurga (Resmi Siciller):** Devletlerin ücretsiz sunduğu toplu açık veri dosyaları (CSV, Parquet, SQLite) ve açık REST API'ler doğrudan indirilerek temel şirket kimlikleri (Unvan, VKN/KDV/KVK/SIREN no, NACE/SIC kodu, resmi adres) kazımasız oluşturulur.
2. **Fiziksel Varlık & POI (Açık Haritalar):** Google Places API faturalarından kaçınmak için Overture Maps (88,4M yer) ve Foursquare OS Places (100M+ POI) katmanları coğrafi ve isim bazlı eşleştirilir.
3. **Tamamlayıcı Kazıma (Hedefli Scrapling):** Scrapling yalnızca açık API/toplu indirme sunmayan ticaret odaları (İTO, İZTO, ATSO, BTSO) ile firmaların web sitelerindeki yasal sayfalar (*Impressum*, *mentions légales*, iletişim) için devreye alınır.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ KATMAN 1: RESMİ SİCİL OMURGASI (KAZIMASIZ / ZERO-SCRAPE)                    │
│ UK Companies House (CSV/API) │ FR Base Sirene (Parquet)                    │
│ DE OffeneRegister (SQLite)   │ NL KVK Zoeken API (€0)                       │
│ TR musteri_listesi.json / TSG Düzey Protokolü                               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ KATMAN 2: AÇIK KAYNAK POI ZENGİNLEŞTİRMESİ                                  │
│ Overture Maps Places (88.4M) + Foursquare OS Places (100M)                  │
│ -> Konum koordinatları, tabela adı, çalışma saatleri, mevcut web/telefon    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ KATMAN 3: HEDEFLİ SCRAPLING OTOMASYONU                                       │
│ 1. Yerel Odalar: İTO Bilgi Bankası, İZTO ASP.NET, ATSO, BTSO                │
│ 2. Yasal Sayfalar: Impressum & Mentions Légales sayfalarından e-posta/tel   │
│ 3. Niyet Sinyalleri: EKAP ihale ilanları, fuar katılımcı listeleri, kariyer │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Scrapling Mimarisi, Yetenekleri ve Karar Matrisi

Scrapling, Python 3.10+ (`pip install "scrapling[all]"`) ortamında çalışan, hafif HTTP istemcisinden tam donanımlı anti-bot tarayıcısına kadar kademeli ölçeklenen modern bir kazıma kütüphanesidir.

### 2.1. Çekirdek Motorlar ve Yetenekler
- **`Fetcher` / `AsyncFetcher`:** Tarayıcı TLS parmak izi taklidi, HTTP/3 desteği ve `FetcherSession` oturum yönetimi sunar. En düşük RAM/CPU tüketimiyle statik sayfalarda saniyede yüzlerce istek işler.
- **`DynamicFetcher` / `DynamicSession`:** Optimize edilmiş `patchright` tabanlı Chromium motorudur. JavaScript ile yüklenen tabloları, `wait_selector` ile AJAX içeriklerini ve ASP.NET WebForms durumlarını yönetir.
- **`StealthyFetcher` / `StealthySession`:** Modifiye edilmiş Camoufox motorudur. Gerçek tarayıcı parmak izi enjeksiyonu, `solve_cloudflare=True` ile Cloudflare Turnstile ve Interstitial aşımı, ~3.500 reklam/izleyici filtresi ve DoH ile DNS sızıntı koruması sağlar.
- **Arka Plan Ağ Yakalama (`record_requests=True`):** Tarayıcı oturumunda arka planda gerçekleşen tüm XHR/Fetch ağ çağrılarını belleğe alır. `session.network.search()` ile API yanıtları DOM parse edilmeden doğrudan JSON olarak okunur.
- **Uyarlanabilir Ayrıştırma (`adaptive=True`):** `auto_save=True` ile ilk çalıştırmada element parmak izini kaydeder. Hedef sitenin HTML DOM tasarımı değişse bile elementi benzerlik skoru üzerinden otomatik olarak bulur.

### 2.2. Hedef Tipine Göre Karar Matrisi

| Hedef Tipi | Örnek Kaynak | Doğru Araç | Tercih Nedeni |
| :--- | :--- | :--- | :--- |
| **REST API** | Companies House, Sirene API, KVK API | `requests` / `httpx` | Doğrudan JSON döner, kazıma ek yükü gereksizdir. |
| **Bulk CSV/Parquet/SQLite** | Sirene Bulk, OffeneRegister, Companies House | `curl` + `duckdb` / `pandas` | Milyonlarca satırı diskten doğrudan işler; en hızlı ve ucuz yoldur. |
| **Klasik HTML Dizin & Sayfalar** | Stadtbranchenbuch, NNDR bağlantı listeleri | `Fetcher` + `adaptive=True` | Minimum kaynak tüketimi, DOM değişikliklerine direnç. |
| **JS / WebForms Portalları** | İZTO, İTO Bilgi Bankası, MERSİS | `DynamicFetcher` / `DynamicSession` | Form POST, sessionstate ve istemci tarafı render çözümü. |
| **Cloudflare / WAF Korumalı Dizin** | Özel tedarikçi katalogları, korumalı dizinler | `StealthyFetcher` (`solve_cloudflare=True`) | Turnstile ve bot challenge bariyerlerini bypass eder. |
| **Arka Plan JSON Çağrısı Yapan Portal**| Oda sorgu arayüzleri, canlı arama formları | `record_requests=True` | DOM seçicisi yazmadan doğrudan arka plan JSON verisini yakalar. |

> [!CAUTION]
> **Anti-Bot ve Ölçek Sınırları:** Akamai, DataDome, Kasada ve Incapsula gibi kurumsal koruma katmanlarında harici antibot token çözücüleri gerekir. Resim/metin tabanlı CAPTCHA soran formlarda Turnstile otomasyonu tek başına yeterli olmaz.

---

## 3. Fiziksel İşletme ve POI Katmanı: Google Maps Alternatifleri

Fiziksel işletmelerin konum, kategori, çalışma saatleri ve marka verileri için Google Places API'ye bağımlı kalmak bütçeyi tüketir.

### 3.1. Google Places API Maliyet Riski (1 Mart 2025 Sonrası)
- Sabit aylık 200 USD kredi kaldırılmış, SKU bazlı ücretsiz kotalara geçilmiştir (Essentials 10.000, Pro 5.000 olay).
- Text Search Pro: **$32 / 1.000 çağrı** | Nearby Search Enterprise: **$35 / 1.000 çağrı**.
- Arama başına en fazla 20 sonuç döner. 1.000 işletmenin tespiti ve detaylarının alınması ~$6,60 ile $18,60 aralığındadır. E-posta adresi sunmaz.

### 3.2. Açık Kaynak Küresel POI Alternatifleri

| Kaynak | Hacim & Kapsam | Lisans & Dağıtım | Maliyet | Notlar & Kalite Durumu |
| :--- | :--- | :--- | :--- | :--- |
| **Overture Maps Places** *(AWS, Meta, Microsoft, TomTom)* | **88.418.121 yer**, 2,53B bina, 475M adres. Meta (61,2M), BrightQuery (16,7M), Microsoft (5,8M), FSQ (3,6M). | **CDLA-Permissive-2.0, Apache-2.0, CC0-1.0**. AWS S3, Azure Blob, BigQuery (`bigquery-public-data.overture_maps.place`). | **Ücretsiz** *(Ticari kullanım serbest).* | `confidence` skoru ile filtrelenmelidir. Tekrar eden kayıtlar ayıklanmalıdır. |
| **Foursquare OS Places** | **100M+ POI**, 200+ ülke, 1.000+ kategori, 20–22 nitelik. | **Apache-2.0**; DuckDB, SQLRooms, Kepler.gl ekosistemi. | **Ücretsiz** *(Ticari kullanım serbest).* | Kayıtların yaklaşık %40'ı güncellik doğrulaması gerektirir. |
| **Hazır SERP / Scraper API'ler** | Google Maps SERP satırları ve zenginleştirilmiş profiller. | Yönetilen API (DataForSEO, SerpApi, Outscraper, Bright Data). | 1.000 yer başına ham SERP ~$0,006–$0,098, zenginleştirilmiş $0,40–$1,30. | Kendi tarayıcı altyapınızı yönetmek istemediğinizde ara çözümdür. |

> [!TIP]
> **Placekey Mekânsal Birleştirme:** Overture Maps Places ve Foursquare OS Places veri setleri Placekey standardı ile birleştirildiğinde ~7,8 milyon kayıt doğrudan çakışır ve çift yönlü teyit edilmiş yüksek kaliteli bir POI katmanı elde edilir.

---

## 4. Beş Hedef Ülkenin Resmi Kayıt ve Açık Veri Envanteri

### Karşılaştırmalı Genel Bakış

| Ülke | Kazımasız Ana Veri Kaynağı | Scrapling Gerektiren Kaynaklar | İletişim Bilgisi Durumu | Büyük Şehir Kapsamı |
| :--- | :--- | :--- | :--- | :--- |
| **Türkiye 🇹🇷** | `musteri_listesi.json`, ULASAV (264 belediye seti) | Ticaret Sicili Gazetesi, MERSİS, İTO, İZTO, ATSO, BTSO | Oda portallarında kısmi unvan/adres/telefon; e-posta kısıtlı | İstanbul, İzmir, Antalya, Bursa portalları aktif |
| **Almanya 🇩🇪** | OffeneRegister.de (SQLite/JSON), GovData.de, Destatis | `handelsregister.de` (toplu indirme kısıtlıdır) | Resmi sicilde telefon/e-posta yok; Impressum taraması gerekir | Berlin (IHK Berlin CSV), Hamburg, Münih güçlü |
| **Hollanda 🇳🇱** | KVK API (Zoeken €0; profiller €0,02), ulusal portal | Düşük maliyetli resmi API ve açık POI nedeniyle öncelikli kazıma gerekmez | KVK açık finansal seti anonimdir; temel API sicil/adres odaklıdır | Amsterdam, Rotterdam, Den Haag, Eindhoven açık |
| **İngiltere 🇬🇧** | Companies House (~471 MB ZIP / ~5M şirket), FSA API | Dağınık belediye NNDR sayfalarından dosya bağlantısı toplama | Sicil adresi tamdır, telefon/e-posta içermez; FSA tabela adını ekler | Londra, Leeds doğrulandı; diğer kentler NNDR üzerinden |
| **Fransa 🇫🇷** | Base Sirene (Parquet/CSV, ~30M firma), API Recherche | Şirket web sitelerinden marka ve iletişim bilgisi çıkarma | Sirene telefon/e-posta içermez; statut P şahıslar maskelidir | Paris, Lyon, Marsilya IRIS düzeyinde merkezi veridedir |

---

### Türkiye 🇹🇷 — En Zor Ülke (Merkezi Açık Veri Yok)
- **Merkezi Durum:** Tek bir açık CSV/Parquet dosyası yoktur. Ticaret Sicili Gazetesi (`ticaretsicil.gov.tr`) ve MERSİS (`mersis.tobb.org.tr`) oturum ve giriş duvarı uygular. TOBB ile veri protokolü en temiz resmi yoldur.
- **Yerel Odalar (Scrapling Hedefleri):**
  - **İstanbul (İTO):** İTO Bilgi Bankası (`bilgibankasi.ito.org.tr`) unvan, ticaret sicil no ve vergi no ile sorgu imkânı verir. Captcha bulunmayan arayüzlerde Scrapling `record_requests=True` ile arka plan JSON uç noktaları yakalanır. İBB Açık Veri Portalı (`data.ibb.gov.tr`) lojistik ve işyeri verilerini sunar.
  - **İzmir (İZTO):** `eportal.izto.org.tr` ASP.NET WebForms arayüzüdür; `DynamicSession` ile viewstate yönetilerek taranır. İzmir BB (`acikveri.bizizmir.com`) CC BY 4.0 ile açıktır.
  - **Antalya (ATSO):** `atso.org.tr/tr/company/` unvan, vergi no, MERSİS no, ticaret sicil no ve oda sicil no ile 5 ayrı parametreden yapılandırılmış sorgu sunar.
  - **Bursa (BTSO):** `btso.org.tr/hizmetler/online-islemler/kayitli-uyeler` kayıtlı üyeler arayüzü.
  - **TOBB Sanayi Veritabanı (`sanayi.org.tr`):** ~70.000 üretici firma, kapasite raporu ve personel sayısı (oturum gerektirir).

---

### Almanya 🇩🇪 — Zengin Açık Veri Ekosistemi
- **OffeneRegister.de:** Open Knowledge Foundation & OpenCorporates ortaklığıyla resmi Handelsregister verilerini tek seferde **~250 MB bzip2 (JSON)** veya **~740 MB gzip (SQLite, FTS5 tam metin aramalı)** olarak ve REST API ile ücretsiz sunar.
- **Resmi Sicil (`handelsregister.de`):** DiRUG sonrası ücretsizdir ancak kullanım koşulları toplu indirmeyi ve serbest ticari yeniden kullanımı yasaklar. Bu nedenle OffeneRegister birincil kaynaktır.
- **Şehirler:**
  - **Berlin:** IHK Berlin Açık Veri Portalı, güncel ticari işletme verilerini (`aktuelle Gewerbedaten`) doğrudan CSV ve GitHub deposu olarak yayımlar. LOR mekansal kodlarıyla eşleşir.
  - **Hamburg & Münih:** Urban Data Platform Hamburg ve `opendata.muenchen.de` (330+ set).

---

### Hollanda 🇳🇱 — KVK Merkezli Hibrit Model
- **KVK Developer API (`developers.kvk.nl`):**
  - `Zoeken (Arama) API`: **€0 (Ücretsiz)**.
  - `Basisprofiel / Vestigingsprofiel`: **€0,02 / sorgu**.
  - **Strateji:** Overture/FSQ ile saptanan işletmeler önce ücretsiz Zoeken API'siyle KVK numarasına bağlanır; yalnızca geçerli kayıtlar için €0,02 ödenerek resmi profil çekilir.
- **KVK Jaarrekeningen:** XBRL mali tabloları açıktır ancak şirket adı ve KVK numarası anonimleştirilmiştir.
- **Şehirler:** Amsterdam Open Data, Rotterdam Stadsarchief (`stadsarchief.rotterdam.nl`), Den Haag ve Eindhoven portalları.

---

### İngiltere 🇬🇧 — En Açık ve Erişilebilir Ülke
- **Companies House (OGL Lisansı — Ticari Kullanım Serbest):**
  - **Free Company Data Product:** Her ay güncellenen `BasicCompanyDataAsOneFile-YYYY-MM-01.zip` (~471 MB ZIP, ~2 GB CSV) paketiyle ~5 milyon aktif İngiliz şirketini tek dosyada sunar.
  - **PSC Snapshot:** Gerçek fayda sahipleri ve ortaklık yapısı (günlük JSON).
  - **Accounts Data:** Yıllık ~2,2 milyon bilançonun %60'ı (iXBRL/XBRL ZIP).
  - **REST API:** 5 dakikada 600 istek limitiyle ücretsiz.
- **Food Standards Agency (FSA) API (`data.food.gov.uk`):** API anahtarı istemez (`x-api-version` başlığı yeterlidir). Restoran, kafe, otel ve pub'ların tabela adlarını (trading name) ve adreslerini verir.
- **NNDR (Business Rates):** Belediye ticari mülk ve vergi tabloları (Londra Datastore, Leeds Data Mill North).

---

### Fransa 🇫🇷 — Base Sirene ve Merkezi API Ekosistemi
- **Base Sirene (INSEE) (`data.gouv.fr` — Licence Ouverte 2.0):**
  - 1973'ten beri tüm şirketler (9 haneli SIREN) ve şubeler (14 haneli SIRET) yer alır (~30M firma, ~43M şube).
  - Aylık Parquet / CSV formatında sunulur (~985 MB sıkıştırılmış). 2027'de tamamen Parquet'ye geçilecektir.
  - SIREN, SIRET ve posta kodları baştaki sıfırların kaybolmaması için `string` olarak saklanmalıdır. NAF 2025 kodları ve çalışan bantları mevcuttur.
- **Merkezi API'ler:**
  - `API Recherche d’entreprises`: Tokensız açık arama, şirket yöneticileri (dirigeants) ve RNE pazarlama itirazı kontrolü.
  - `API Sirene`: Günlük tescil ve unvan değişiklikleri.
- **Şehirler:** Paris, Marsilya, Lyon ve Nice için belediye portalına gerek yoktur; Base Sirene tüm komünleri ve 15.500 IRIS istatistik bölgesini adres düzeyinde kapsar.

---

## 5. Ülke-Üstü ve Sınır Ötesi Doğrulama Kaynakları

1. **GLEIF LEI (`api.gleif.org`):** CC0 lisanslı global tüzel kişi kimliği (LEI) ve ana-bağlı şirket hiyerarşi grafiği.
2. **OpenCorporates (`api.opencorporates.com`):** 200M+ şirket, 100+ yargı alanı; uluslararası unvan tekilleştirme standardı.
3. **AB VIES (`ec.europa.eu/taxation_customs/vies`):** Avrupa Birliği KDV numarası doğrulama servisi; pasif/paravan şirket elemede kritik.
4. **OpenStreetMap Overpass API (`overpass-turbo.eu`):** Tersane havuzları, liman koordinatları, marinalar ve endüstriyel POI doğrulaması.
5. **e-Justice BRIS (`e-justice.europa.eu`):** Avrupa Birliği resmi ticaret sicilleri tek kapı sorgu ağı.

---

## 6. Uçtan Uca B2B Veri Boru Hattı ve Entity Resolution

### 6.1. Entity Resolution (Deterministik Tekilleştirme Sırası)
Farklı kaynaklardan gelen veriler aşağıdaki hiyerarşiyle tek bir kimlik grafiğinde birleştirilir:
1. **VKN / KVK / SIREN / Company Number Eşleşmesi:** Doğrudan otomatik birleştir (Kesin Kimlik).
2. **Domain Kökü Eşleşmesi (`example.com`):** Otomatik birleştir.
3. **Normalize Telefon Hash'i (E.164 `+90...`):** Güçlü sinyal ile birleştir.
4. **Fuzzy Unvan Eşleşmesi (Jaro-Winkler ≥ 0.92) + Aynı Şehir + Aynı NACE:** Manuel inceleme kuyruğuna aktar.
5. **Çelişkili Veri Durumu:** Kaynak güven puanı (`trust_score`) yüksek olan kazanır; ezilen kayıt silinmez, `merged_into` ile bağlanır.

```sql
-- Ana Şirket Tablosu
CREATE TABLE company (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country TEXT NOT NULL,
  mersis_no TEXT UNIQUE,
  vkn CHAR(10) UNIQUE,
  siren CHAR(9) UNIQUE,
  kvk_no CHAR(8) UNIQUE,
  legal_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  domain TEXT UNIQUE,
  nace_code TEXT,
  province_id INT,
  employee_band SMALLINT,
  status TEXT DEFAULT 'active',
  trust_score NUMERIC(4,2) DEFAULT 0,
  icp_score NUMERIC(4,2) DEFAULT 0,
  merged_into UUID REFERENCES company(id),
  first_seen TIMESTAMPTZ DEFAULT now(),
  last_verified_at TIMESTAMPTZ
);

-- Doğrulanmış İletişim Tablosu
CREATE TABLE contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES company(id) ON DELETE CASCADE,
  type TEXT CHECK (type IN ('email','phone','mobile','address','social')),
  value TEXT NOT NULL,
  normalized TEXT NOT NULL,
  is_verified BOOLEAN DEFAULT false,
  verification_method TEXT,
  legal_basis TEXT,
  confidence NUMERIC(3,2),
  last_checked_at TIMESTAMPTZ
);

-- Kaynak Kanıt İzi (KVKK ve Güvenilirlik İçin Şart)
CREATE TABLE source_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES company(id),
  source_name TEXT NOT NULL,
  source_class CHAR(1) CHECK (source_class IN ('A','B','C')),
  url TEXT,
  raw_hash CHAR(64),
  fetched_at TIMESTAMPTZ DEFAULT now()
);
```

### 6.2. Hukuki Sayfa Taraması (En Yüksek ROI)
Şirket web sitelerinin tamamını taramak yerine yalnızca yasal zorunluluk olan sayfalar taranır:
- **Almanya:** `Impressum` sayfası (Telemediengesetz §5 gereği şirket yöneticisi, tam unvan, adres, vergi no, telefon ve e-posta içermek zorundadır).
- **Fransa:** `Mentions légales` sayfası (LCEN kanunu gereği zorunludur).
- Bu tek sayfa Scrapling ile çekildiğinde, tüm siteyi kazımaktan %90 daha hızlı ve %100 doğrulanmış iletişim verisi elde edilir.

### 6.3. Sıralama ve ICP Skorlama Formülü
Satış ekibine filtrelenmemiş yüz binlerce kayıt vermek işe yaramaz. Önceliklendirme formülü:

$$	ext{Skor} = 0.30\cdot 	ext{ICP Uyumu} + 0.20\cdot 	ext{Veri Tazeliği} + 0.20\cdot 	ext{İletişim Doluluğu} + 0.20\cdot 	ext{Niyet Sinyali} + 0.10\cdot 	ext{Erişilebilirlik}$$

**Niyet Sinyalleri (Zamanla Sönen / Decay Eden Olaylar):**
- Son 90 günde EKAP'ta tekne/gemi ihalesine teklif verme veya kazanma.
- Uluslararası yat/denizcilik fuarı katılımcılığı (Monaco, Cannes, METSTRADE, TÜYAP).
- Kariyer sayfalarında CAD/CFD mühendisi veya gemi inşa mimarı ilanı açma.
- Yeni şube tescili, sermaye artırımı, tersane sahası genişletme.

---

## 7. Scrapling Üretim Hazır Kod İskeleti

Aşağıdaki modül; adaptive seçiciler, Cloudflare aşımı, arka plan ağ yanıtı yakalama ve oturum yönetimi içeren uçtan uca üretim şablonudur:

```python
"""
NautiGraph B2B - Scrapling Hibrit Toplayıcı ve Ağ Yakalama Modülü
"""
import asyncio
from typing import Dict, Any, List
from scrapling.fetchers import Fetcher, DynamicSession, StealthySession
from scrapling.spiders import Spider


class B2BRegistrySpider(Spider):
    name = "b2b_registry"
    crawldir = "./crawlstate"
    robots_txt_obey = True
    concurrent_requests = 4
    
    # Adaptive DOM seçici yapılandırması
    selector_config = {
        "adaptive": True,
        "auto_save": True
    }

    async def parse(self, response):
        # 1. Liste satırlarını çek
        for row in response.css("table.company-table tr.item"):
            company = {
                "legal_name": row.css("td.title::text").get(),
                "city": row.css("td.location::text").get(),
                "reg_no": row.css("td.reg::text").get(),
                "detail_url": response.urljoin(row.css("a.link::attr(href)").get())
            }
            if company["detail_url"]:
                yield response.follow(
                    company["detail_url"],
                    callback=self.parse_detail,
                    meta={"company": company}
                )

        # 2. Sonraki sayfa takibi
        next_url = response.css("a.next-page::attr(href)").get()
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    async def parse_detail(self, response):
        company = response.meta["company"]
        company["website"] = response.css("a.website::attr(href)").get()
        company["phone"] = response.css("span.phone::text").get()
        company["email"] = response.css("a[href^='mailto:']::text").get()
        yield company


# =============================================================================
# Arka Plan Ağ İsteklerini Yakalama (XHR / JSON API Sniffing)
# =============================================================================

async def capture_chamber_ajax_api(target_portal_url: str, search_query: str) -> List[Dict[str, Any]]:
    """
    Oda arama sayfasının arka planda çağırdığı gizli JSON uç noktasını
    HTML ayrıştırmaya gerek kalmadan record_requests ile yakalar.
    """
    async with DynamicSession(headless=True, record_requests=True) as session:
        await session.goto(target_portal_url)
        await session.fill("#txtSearch", search_query)
        await session.click("#btnSubmit")
        await session.wait_for_selector(".results-grid")

        # Arka plandaki JSON yanıtlarını ara
        api_responses = session.network.search(url_pattern=r"/api/v1/companies")
        results = []
        for r in api_responses:
            try:
                results.extend(r.json().get("items", []))
            except Exception:
                pass
        return results


# =============================================================================
# Cloudflare Turnstile ve Bot Korumalı Dizinleri Aşma
# =============================================================================

async def fetch_protected_supplier_directory(target_url: str):
    """
    StealthySession ile Turnstile / Interstitial korumasını aşarak HTML çeker.
    """
    async with StealthySession(solve_cloudflare=True, humanize=True, geoip=True) as session:
        response = await session.get(target_url)
        # Adaptive seçici ile öğeyi çek
        return response.adaptive_select("div.supplier-card")


# =============================================================================
# Hukuki Sayfa Taraması (Impressum / Mentions Légales)
# =============================================================================

async def extract_legal_page_contacts(domain: str) -> Dict[str, Any]:
    """
    Bir firmanın Impressum veya İletişim sayfasından teyitli iletişim verisi çıkarır.
    """
    fetcher = Fetcher()
    endpoints = ["/impressum", "/mentions-legales", "/iletisim", "/contact"]
    for ep in endpoints:
        try:
            url = f"https://{domain}{ep}"
            resp = fetcher.get(url, timeout=6)
            if resp.status == 200:
                emails = resp.css("a[href^='mailto:']::text").getall()
                phones = resp.css("a[href^='tel:']::text").getall()
                if emails or phones:
                    return {
                        "domain": domain,
                        "source_url": url,
                        "emails": list(set(emails)),
                        "phones": list(set(phones))
                    }
        except Exception:
            continue
    return {"domain": domain, "emails": [], "phones": []}
```

---

## 8. Hukuki Çerçeve ve Uyumluluk (KVKK, GDPR, İYS)

- **KVKK (6698 sayılı Kanun):** Tüzel kişi kayıtları (A.Ş., Ltd. Şti.) kişisel veri kapsamı dışındadır. Ancak şahıs işletmeleri, tacirler ve çalışan e-postaları (`ad.soyad@`) kişisel veridir. Hukuki dayanak: **KVKK md. 5/2-f (Meşru Menfaat)**. Denge testi dokümante edilmelidir.
- **İYS (İleti Yönetim Sistemi) ve 6563 sayılı Kanun:** Ticari elektronik iletilerde 2020 değişikliği tacirleri de kapsar. Soğuk e-posta gönderiminde onay durumu (`consent_status`) tutulmalı ve ret edenler için **ROKS** kontrolü uygulanmalıdır.
- **GDPR (Genel Veri Koruma Tüzüğü):** AB vatandaşlarına ait verilerde *Article 6(1)(f)* meşru menfaat işletilir; her e-postada tek tıkla abonelikten çıkma (*opt-out*) ve *Impressum* bilgisi zorunludur.
- **Telif ve Veritabanı Hakkı:** Sadece kamuya açık veriler toplanmalı, `robots.txt` kurallarına uyulmalı ve sunucuları çökertecek agresif eşzamanlı isteklerden kaçınılmalıdır.

---

## 9. NautiGraph TR Sistem Entegrasyonu

NautiGraph platformunda bu strateji şu dosya ve modüllerle tam uyumlu çalışır:
1. **`business_manager/run.bat`:** Python HTTP sunucusunu görünür CMD ekranında başlatır, tarayıcıyı `http://127.0.0.1:8765/` adresinde açar ve CMD kapatıldığında süreci sonlandırır.
2. **`business_manager/app.py`:** Toplayıcı kuyruk motoru (`CRAWLER_STATE`), arka plan iş parçacığı (`_crawler_worker`), analitik paneli (`/api/analytics/panel`) ve toplayıcı denetimi (`/api/crawler/start`, `/api/crawler/stop`).
3. **`business_manager/database.py` & `schema.sql`:** `companies`, `contacts`, `source_evidence`, `crawler_jobs` tabloları ve `country`, `industry_sector` endeksleri.
4. **`musteri_listesi.json`:** 1.629 adet resmi Tuzla / İstanbul ticaret sicil kaydı ile yerel veri tohumlama.
5. **Arayüz (`index.html`):** Canlı üst toplayıcı durumu (ticker & countdown bar), 30 günlük çift çubuklu akış histogramı, ülke donut grafiği, sektör barları ve kaynak dağılım kartları.

---

## 10. Doğrulanmış Kaynaklar, Resmi Portallar ve Canlı API Bağlantıları Dizini

Aşağıdaki dizin; planın tüm aşamalarında başvurulacak resmi devlet sicilleri, açık veri portalları, küresel POI katalogları, belediye veri setleri ve teknik kütüphane dokümantasyonlarını içermektedir:

### 10.1. Resmi Ticaret Sicilleri ve Açık Veri Portalları (Ülke Bazlı)

#### 🇬🇧 İngiltere (United Kingdom)
- [Companies House Bulk Data İndirme Portalı](https://download.companieshouse.gov.uk/) — Aylık tam şirket snapshot paketleri (Free Company Data Product).
- [Companies House Ücretsiz Bilanço İndirme (Accounts Data)](https://download.companieshouse.gov.uk/en_accountsdata.html) — Günlük/aylık XBRL mali tabloları.
- [Companies House Data Products Rehberi (GOV.UK)](https://www.gov.uk/guidance/companies-house-data-products) — Resmi veri ürünleri ve API tanımları.
- [CH Guide: Companies House Bulk Data Guide](https://chguide.co.uk/bulk-data/companies) — Topluluk rehberi ve CSV alan ayrıntıları.
- [GetDunlin: How to Export Companies House Data](https://getdunlin.com/companies-house-data-export) — Toplu dışa aktarım stratejileri.
- [FSA Food Hygiene Ratings API (api.gov.uk)](https://www.api.gov.uk/fsa/) — Tabela adları ve işletme hijyen sicilleri API'si.
- [Yug Solutions: Using Food Hygiene Ratings API](https://www.yugsolutions.co.uk/insights/food-hygiene-ratings-api) — Entegrasyon analitiği.
- [UK National NNDR Business Rates (data.gov.uk)](https://www.data.gov.uk/dataset/33e9d8e9-14e5-4f5b-9382-12d76ae05afa/nndr-business-rates) — Ulusal ticari mülk ve vergi sicili.
- [London Datastore Food Hygiene Ratings](https://data.london.gov.uk/dataset/food-hygiene-ratings-scheme-2oggd) — Londra gıda ve işletme sicili.
- [Data Mill North (Leeds & Yorkshire Open Data)](https://datamillnorth.org/dataset/food-hygiene-ratings-for-food-establishments-in-leeds-api-2nqxx) — Leeds ve bölge işletmeleri API'si.
- [Brent Council NNDR Business Rates](https://data.brent.gov.uk/dataset/national-non-domestic-rates-nndr-e59zx) — Londra Brent ilçesi ticari mülk kayıtları.
- [Barnet Council Business Rates](https://open.barnet.gov.uk/dataset/business-rates-nndr-accounts-in-credit-e18p2) — Londra Barnet işletme kayıtları.
- [Hounslow Council Business Rates](https://data.hounslow.gov.uk/@london-borough-of-hounslow/business-rates) — Hounslow ticari mülk tabloları.
- [Adur & Worthing Business Rates Open Data](https://www.adur-worthing.gov.uk/business-rates/business-rates-open-data/) — Bölgesel NNDR verisi.
- [Herefordshire Business Rates Datasets](https://www.herefordshire.gov.uk/your-council/our-open-data/business-rates-datasets/) — Herefordshire işletme verisi.
- [York Open Data NNDR](https://data.yorkopendata.org/dataset/groups/nndr-business-rates) — York kenti ticari işletme kayıtları.
- [Open Innovations UK Open Data Directory](https://open-innovations.org/data/list) — Açık inovasyon veri listeleri.

#### 🇫🇷 Fransa (France)
- [Base Sirene des entreprises et de leurs établissements (data.gouv.fr)](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret) — Aylık tam SIREN/SIRET Parquet ve CSV veri seti.
- [API Recherche d’Entreprises (data.gouv.fr)](https://www.data.gouv.fr/dataservices/api-recherche-dentreprises) — Tokensız açık şirket ve yönetici sorgu servisi.
- [INSEE Base Sirene Bilgilendirme Portalı](https://www.insee.fr/fr/information/3591226) — Resmi metodoloji ve NAF kod kılavuzu.
- [ContactsEntreprises: Sirene Database Guide](https://contactsentreprises.fr/en/blog/sirene-database-siren-siret-public-data.html) — SIREN, SIRET ve kamu verileri kullanım rehberi.
- [Base de Contacts: SIREN, SIRET et données publiques](https://basedecontacts.fr/blog/base-sirene-siren-siret-donnees-publiques.html) — Fransız ticari sicil mimarisi.
- [Pharow: Base SIRENE erişim rehberi](https://www.pharow.com/blog/comment-acceder-a-la-base-sirene-des-entreprises) — Ücretsiz ve toplu erişim yöntemleri.
- [data.gouv.fr: SIREN/SIRET Arama Uygulaması](https://www.data.gouv.fr/reuses/rechercher-un-siret-en-ligne-par-nom-siren-ou-siret-dans-la-base-sirene) — Çevrimiçi unvan ve tescil aracı.
- [data.gouv.fr: Komün Bazlı İşletme ve Dernekler](https://www.data.gouv.fr/reuses/entreprises-et-associations-commune-par-commune-base-sirene) — Yerel belediye kırılımları.

#### 🇩🇪 Almanya (Germany)
- [OffeneRegister.de Portalı](https://offeneregister.de/) — Handelsregister verilerinin CC BY 4.0 lisanslı SQLite ve JSON indirme aynası.
- [Registerportal der Länder (handelsregister.de Normal Arama)](https://www.handelsregister.de/rp_web/normalesuche/welcome.xhtml) — Resmi federal eyaletler sicil arama sayfası.
- [Registerbekanntmachungen (handelsregister.de İlanlar)](https://www.handelsregister.de/rp_web/bekanntmachungen/welcome.xhtml) — Resmi tescil ve tasfiye ilanları.
- [IHK Berlin Open Data Gewerbedaten](https://www.ihk.de/berlin/service-und-beratung/digitalisierung/open-data-5691102) — Berlin Ticaret ve Sanayi Odası açık ticari işletme CSV veri seti.
- [GovData Kataloğu (data.europa.eu)](https://data.europa.eu/data/catalogues/govdata?locale=en) — Almanya federal ve yerel açık veri arşivi.
- [Open Data Germany Harita Portalı](https://open-data-germany.org/en/dataset/) — Eyalet bazlı açık veri setleri.
- [Destatis Open Data (Federal İstatistik Ofisi)](https://www.destatis.de/EN/Service/OpenData/_node.html) — Almanya makroekonomik ve sektörel istatistikler.
- [Urban Data Platform Hamburg](https://www.en.urbandataplatform.hamburg/) — Hamburg kentsel veri altyapısı ve 3B bina verileri.
- [Open Data München](https://opendata.muenchen.de/pages/links) — Münih Belediyesi açık veri portalları.
- [Fraunhofer MobilityDataMap](https://mobilitydatamap.iis.fraunhofer.de/) — RheinMain ve Frankfurt akıllı ulaşım/işyeri verileri.
- [OpenStreetMap Deutschland](https://openstreetmap.de/karte/) — Almanya yerel harita ve POI altyapısı.

#### 🇳🇱 Hollanda (Netherlands)
- [KVK Developer Portal Pricing](https://developers.kvk.nl/pricing) — Zoeken API (€0) ve Profil API (€0,02) fiyatlandırma koşulları.
- [KVK Handelsregister Open Dataset Jaarrekeningen](https://www.kvk.nl/producten-bestellen/kvk-jaarrekeningen-open-data-set/) — XBRL yıllık bilanço açık veri paketi.
- [European Open Data: KVK Jaarrekeningen Metadata](https://data.europa.eu/data/datasets/kvk-handelsregister-open-dataset-jaarrekeningen?locale=en) — AB veri portalı KVK metaveri kaydı.
- [CBS Open Data (Hollanda İstatistik Ofisi)](https://www.cbs.nl/en-gb/our-services/open-data) — CBS StatLine B2B sektör istatistikleri.
- [RDW Open Data Portal](https://opendata.rdw.nl/en/d/qane-5xqj/visualization) — Araç ve tescil açık verisi.
- [Amsterdam Open Data](https://dataportals.org/catalog/amsterdam_open_data) — Amsterdam kentsel açık veri kataloğu.
- [Stadsarchief Rotterdam Open Datasets](https://stadsarchief.rotterdam.nl/en/open-datasets) — Rotterdam kurumsal ve tarihsel açık veri arşivi.
- [Den Haag en Open Data](https://www.denhaag.nl/nl/digitaal-den-haag/den-haag-en-open-data/) — Lahey kenti açık veri arşivi.
- [Eindhoven Open Data](https://data.eindhoven.nl/pages/home/) — Eindhoven açık veri portalı.
- [OVapi Real-Time Transit](https://trains.fyi/networks/ovapi/) — Hollanda yerel ve bölgesel ulaşım/lokasyon API'si.
- [CompanyData NL](https://companydata.com/nl/zakelijke-adressen-kopen/) — Hollanda ve Belçika B2B ticari liste piyasa kıyaslaması.

#### 🇹🇷 Türkiye
- [Türkiye Ticaret Sicili Gazetesi İlan Görüntüleme](https://www.ticaretsicil.gov.tr/view/hizlierisim/ilangoruntuleme.php) — Tescil, unvan ve sermaye ilanları arayüzü.
- [Türkiye Ticaret Sicili Gazetesi Unvan Sorgulama](https://www.ticaretsicil.gov.tr/view/hizlierisim/unvansorgulama.php) — Hızlı şirket unvanı sorgulama sayfası.
- [Ticaret Bakanlığı & TOBB MERSİS Protokolü](https://ticaret.gov.tr/haberler/tobb-ile-mersi%CC%87s-i%CC%87sbirligi-protokolu-i%CC%87mzalandi) — MERSİS veri paylaşım esasları.
- [MERSİS Kullanıcı Girişi (mersis.tobb.org.tr)](http://mersis.tobb.org.tr/_layouts/CustomFbaPage/Login6fdb.html) — Merkezi sicil giriş portalı.
- [TOBB Sanayi Veritabanı (sanayi.org.tr)](https://sanayi.org.tr/) — 70.000+ sanayi ve üretim tesisi kapasite raporları portalı.
- [İTO Bilgi Bankası Firma Bilgileri Sorgulama](https://bilgibankasi.ito.org.tr/tr/bilgi-bankasi/firma-bilgileri?onlyApp=true) — İstanbul Ticaret Odası sicil sorgu portalı.
- [İTO Bilgi Güncelleme Portalı](https://guncelle.ito.org.tr/) — İstanbul firma güncelleme formu.
- [İTO Online İşlemler Portalı](https://eportal.ito.org.tr/) — İstanbul oda online işlem arayüzü.
- [İZTO Üye Firma Sorgulama (eportal.izto.org.tr)](https://eportal.izto.org.tr/web/Uye_Firmalar_Yeni.aspx) — İzmir Ticaret Odası ASP.NET sorgu sayfası.
- [ATSO Üye Sorgulama (atso.org.tr/tr/company)](https://www.atso.org.tr/tr/company/) — Antalya Ticaret ve Sanayi Odası 5 alanlı sorgulama portali.
- [BTSO Kayıtlı Üyeler Portalı](https://www.btso.org.tr/hizmetler/online-islemler/kayitli-uyeler) — Bursa Ticaret ve Sanayi Odası üye sorgulama.
- [ULASAV Ekonomi Açık Veri Portalı (ÇŞB)](https://ulasav.csb.gov.tr/group/28d23837-9051-4f97-b5c2-12d27499db45?groups=ekonomi&_groups_limit=0&tags=ekonomi) — Ulusal Akıllı Şehir ekonomi açık veri setleri.
- [İBB Açık Veri Portalı](https://data.ibb.gov.tr) — İstanbul Büyükşehir Belediyesi açık veri kataloğu.
- [İzmir BB Açık Veri Portalı](https://acikveri.bizizmir.com/) — İzmir kentsel açık veri portalı.
- [İzmir Açık Veri CC BY 4.0 Lisansı](https://acikveri.bizizmir.com/tr/license) — Ticari yeniden kullanım koşulları.
- [Türkiye'deki Açık Veri Portalları Dizini (GitHub)](https://github.com/ozancanozdemir/Turkiye-deki-Acik-Veri-Portallari-Open-Data-Portals-in-Turkey-) — İl ve belediye açık veri dizini derlemesi.
- [URBASED Açık Veri Portalları Analizi](https://www.urbased.com/acik-veri-portallari/) — Türkiye açık veri olgunluk analizi.

---

### 10.2. Küresel POI, Açık Harita ve Mekânsal Veri Setleri
- [Overture Maps Places Guide & Dokümantasyonu](https://docs.overturemaps.org/guides/places/) — Overture 88.4M küresel POI veri şeması ve erişim rehberi.
- [OvertureMapsAPI: What Is Overture Maps?](https://www.overturemapsapi.com/docs/what-is-overture-maps) — Temalar, veri mimarisi ve sorgulama rehberi.
- [Google Earth Engine Overture Maps Places Kataloğu](https://developers.google.com/earth-engine/datasets/catalog/overture-maps_places_place) — Cloud ortamında mekânsal analiz.
- [Foursquare OS Places Resmi Açık Kaynak Portalı](https://opensource.foursquare.com/os-places/) — 100M+ Apache-2.0 lisanslı POI veri indirme sayfası.
- [OpenStreetMap Topluluğu: Foursquare 100M+ POI Duyurusu](https://community.openstreetmap.org/t/foursquare-releases-100m-poi-dataset-under-apache-2-0/121883) — Veri yapısı ve lisans tartışması.
- [Placekey: Foursquare ve Overture Places Birleştirme](https://www.placekey.io/blog/joining-foursquare-places-with-overture-places-using-placekey) — Mekânsal ID eşleştirme ve 7.8M kayıt çakışma analizi.
- [Reprompt AI: Foursquare OS Places vs. Overture Maps](https://repromptai.com/blog/foursquare-vs-overture) — Kapsam, tazelik ve doluluk kıyaslaması.

---

### 10.3. Google Places API ve Ticari Harita Maliyet Karşılaştırmaları
- [Google Maps Platform Fiyatlandırma Listesi (Resmi)](https://developers.google.com/maps/billing-and-pricing/pricing) — Temel servisler ve 1 Mart 2025 fiyat modelleri.
- [Google Places API Usage & Billing Rehberi](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing) — SKU bazlı faturalandırma ve kota esasları.
- [SafeGraph: Google Places API Pricing Guide (2026)](https://www.safegraph.com/guides/google-places-api-pricing/) — Gerçek maliyetler ve alternatif analizi.
- [MapAtlas: Google Maps API Pricing and Licensing (2026)](https://mapatlas.eu/blog/google-maps-api-pricing-2026) — 1.000 çağrı başına net birim maliyet hesapları.
- [APISerpent: How Much Does Google Maps API Cost in 2026?](https://apiserpent.com/blog/google-maps-api-pricing-comparison) — SERP kazıyıcılar ile resmi API maliyet tablosu.
- [APIs.io Google Places Plans](https://apis.io/plans/google-places/google-places-plans-pricing/) — Kota ve kademe modelleri.

---

### 10.4. Çok Ülkeli Sicil Dizinleri ve Fiyatlandırma
- [OpenCorporates Resmi Fiyatlandırma](https://opencorporates.com/pricing/) — Ticari planlar (£225 - £1.200/ay) ve açık veri şartları.
- [Find My Moat: OpenCorporates İncelemesi](https://www.findmymoat.com/tools/opencorporates) — Özellikler ve kurumsal maliyet değerlendirmesi.
- [PublicAPIs: OpenCorporates API Kurulum Rehberi](https://publicapis.io/opencorporates-api) — Ücretsiz kamu katmanı kullanım kılavuzu.

---

### 10.5. Scrapling Kütüphanesi ve Anti-Bot Teknolojisi Dokümantasyonu
- [Scrapling Resmi Dokümantasyonu (Read the Docs)](https://scrapling.readthedocs.io/en/latest/) — StealthySession, DynamicSession, Adaptive Seçiciler kılavuzu.
- [Scrapling GitHub Deposu (D4Vinci/Scrapling)](https://github.com/d4vinci/Scrapling) — Kaynak kod, issues ve sürüm notları.
- [Scrapling Agent Skill Belgesi (GitHub)](https://github.com/D4Vinci/Scrapling/blob/main/agent-skill/Scrapling-Skill/SKILL.md) — Otonom AI ajanları için Scrapling kullanım becerisi.
- [ScrapingBee: Adaptive Python Web Scraping with Scrapling](https://www.scrapingbee.com/blog/scrapling-adaptive-python-web-scraping/) — Adaptif seçiciler ve DOM kırılması analizi.
- [Scrapeless: Scrapling Agent Browser Entegrasyonu](https://docs.scrapeless.com/en/integrations/scrapling/) — Uzak tarayıcı ve proxy rotasyonu.
- [The Web Scraping Wiki: Scrapling Hands-on Guide (Obsidian)](https://publish.obsidian.md/twsc-public/Web+Scraping/Articles/scrapling-hands-on-guide) — Pratik uygulama notları.
- [Global AI Force: Scrapling Installation & Setup (2026 Guide)](https://globalaiforce.com/scrapling-how-to-install-and-set-up-2026-guide/) — Kurulum ve bağımlılık yönetimi.
- [Medium: Unlocking Adaptive Web Scraping Power with Scrapling](https://medium.com/@gemQueenx/unlocking-adaptive-web-scraping-power-with-scrapling-in-python-efa9404c9a74) — Python ile adaptif kazıma mimarisi.
- [YouTube: Adaptive Web Scraping Framework (Scrapling Video Guide)](https://www.youtube.com/watch?v=HQCCTC5kih0) — Canlı kodlama ve demo anlatımı.

---

### 10.6. AB Yüksek Değerli Veri Setleri (HVD) ve Mevzuat Kaynakları
- [Avrupa Komisyonu: High-Value Datasets SSS](https://digital-strategy.ec.europa.eu/en/faqs/high-value-datasets-questions-and-answers) — (AB) 2023/138 Yönetmeliği şirket sahipliği ve sicil açma zorunlulukları.
- [data.europa.eu: High Value Datasets Durum Raporu](https://data.europa.eu/en/news-events/news/high-value-datasets-what-has-changed-and-what-will-come-next) — 9 Haziran 2024 sonrası üye ülke uygulamaları.
- [GitLab Data Provider Manual: HVD Teknik Rehberi](https://dataeuropa.gitlab.io/data-provider-manual/hvd/) — Makine okunabilir format ve API teslim standartları.
