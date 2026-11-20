# NautiGraph TR & Business Manager
> **Türkiye B2B Denizcilik, Tekne İmalatı & Yat Tasarımı Kimlik Grafiği, Otomatik Sequence & CRM Platformu**

NautiGraph TR, Türkiye'de Tuzla, Yalova (Altınova), Antalya Serbest Bölge, Bodrum (İçmeler) ve İzmir denizcilik kümelerinde faaliyet gösteren yat tersaneleri (NACE 30.12) ve naval architecture / gemi ve yat tasarım ofislerini (NACE 71.12) tekilleştiren, satın alma niyet sinyallerine göre skorlayan, otomatik e-posta sekansları ile müşteri çeken ve anlaşmaları CRM Kanban hattında yöneten birleşik B2B büyüme motorudur.

---

## 🌟 Ana Özellikler

1. **Keşif & ICP Motoru (Top of Funnel):**
   - 3 Kalite Sınıflı Kaynak Envanteri (A: Ticaret Sicili, GİB, MERSİS; B: İMEAK DTO, Monaco/Cannes fuar katılımcıları, Google POI; C: Web sitesi JSON-LD, kariyer portalları).
   - 5 Ağırlıklı ICP Skorlama: `Skor = 0.30·ICP + 0.20·Tazelik + 0.20·İletişim + 0.20·Niyet + 0.10·Erişilebilirlik`.
   - VKN, Domain, E.164 Telefon Hash ve Jaro-Winkler $\ge 0.92$ Deterministik Entity Resolution.
   - Her kayıt için MinIO SHA-256 ham kanıt izi (`source_evidence`) ve KVKK md. 5/2-f (Tacir meşru menfaat) uyumu.

2. **Otomasyon & E-Posta Sequence Motoru (Lead Nurturing & Outreach):**
   - Yat tasarım & tersane karar vericilerine özel çok adımlı kişiselleştirilmiş şablonlar (Adım 1: Değer Önerisi, Adım 2: Case Study & Klas Onay Süresi, Adım 3: Son Çağrı).
   - Dinamik Değişken Enterpolasyonu (`{{firma_adi}}`, `{{tespit_edilen_cad}}`, `{{son_sinyal}}`, `{{sehir}}`).
   - Sandbox (Güvenli Simülasyon) ve Canlı SMTP desteği (Gmail App Password, Brevo, AWS SES).
   - Otomatik İYS / ROKS ret linki yönetimi ve yanıt geldiğinde CRM fırsatına otomatik dönüştürme.

3. **Denizcilik CRM & Satış Boru Hattı (Kanban Pipeline):**
   - 5 Aşamalı Satış Hattı: `Yeni` $\to$ `İletişim Kuruldu` $\to$ `Demo/Keşif` $\to$ `Teklif Verildi` $\to$ `Kazanıldı`.
   - Yat sektörüne özel proje teklifleri (EUR para birimi, CFD analiz, klas onay, 3D render kapsamları).

4. **Veri Sağlığı & KVKK Denetim Panosu:**
   - Manuel Tekilleştirme Kuyruğu (Dedup Queue) ile şüpheli kayıtları tek tıkla birleştirme (`merged_into`).

---

## 🚀 Başlatma

1. Klasördeki `run.bat` dosyasına çift tıklayın veya terminalden çalıştırın:
   ```bash
   cd business_manager
   python app.py
   ```
2. Tarayıcınızda otomatik olarak açılır:
   ```
   http://127.0.0.1:8765/
   ```

---

## 🗄️ Veritabanı Mimarisi (`data/business_manager.db`)

- `companies`: Şirket tüzel kişilikleri, VKN, MERSİS, domain, NACE, çalışan bandı, ICP ve güven skorları.
- `contacts`: Doğrulanmış e-posta ve telefonlar, roller, SMTP 250 doğrulama ve KVKK yasal dayanakları.
- `source_evidence`: A, B ve C sınıfı kaynak kanıtları, SHA-256 snapshot hash'leri.
- `intent_signals`: Fuar katılımları, sermaye artışları ve CAD iş ilanı sinyalleri.
- `saved_lists` & `list_memberships`: Hedef müşteri listeleri.
- `dedup_queue`: Jaro-Winkler $\ge 0.92$ çelişki kuyruğu.
- `email_campaigns` & `sequence_steps`: Çok adımlı e-posta dizileri.
- `email_logs`: Gönderim logları, açılma, tıklanma, yanıt ve İYS ret durumları.
- `crm_deals`: Kanban satış anlaşmaları ve teklif kalemleri.
- `system_settings`: SMTP ve sistem konfigürasyonu.
