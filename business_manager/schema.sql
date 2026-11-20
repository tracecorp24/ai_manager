PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. ANA ŞİRKET KİMLİK GRAFİĞİ (COMPANIES)
-- ============================================================================
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,                       -- UUID / Benzersiz slug (örn: 'cmp-01')
    vkn TEXT UNIQUE,                           -- 10 Haneli Vergi Kimlik No (Deterministik #1)
    mersis_no TEXT UNIQUE,                     -- 16 Haneli MERSİS No
    legal_name TEXT NOT NULL,                  -- Tam Ticaret Sicil Resmi Ünvanı
    short_name TEXT NOT NULL,                  -- Pazar / Marka Adı
    normalized_name TEXT NOT NULL,             -- Fuzzy eşleşme & arama için normalize isim
    domain TEXT UNIQUE,                        -- Web Alan Adı Kökü (Deterministik #2)
    nace_code TEXT NOT NULL,                   -- '30.12' (Yat/Tekne İnşa) veya '71.12' (Tasarım/Mühendislik)
    nace_desc TEXT,                            -- NACE faaliyet metni
    province TEXT NOT NULL,                    -- İl (İstanbul, Antalya, Muğla, Yalova, İzmir)
    district TEXT,                             -- İlçe / Serbest Bölge / Tersaneler Bölgesi
    employee_band TEXT,                        -- '1-10', '11-50', '51-200', '200+'
    employee_est TEXT,                         -- Tahmin ve gerekçe (örn: '285 Personel')
    trust_score REAL DEFAULT 0,                -- 0-100 Kaynak Güven Skoru
    icp_score REAL DEFAULT 0,                  -- 0-100 Bileşik ICP Skoru
    score_icp REAL DEFAULT 0,                  -- ICP Uyumu (%30)
    score_freshness REAL DEFAULT 0,            -- Veri Tazeliği (%20)
    score_contact REAL DEFAULT 0,              -- İletişim Doluluğu (%20)
    score_intent REAL DEFAULT 0,               -- Satın Alma Niyeti (%20)
    score_reachability REAL DEFAULT 0,         -- Erişilebilirlik (%10)
    icp_reason TEXT,                           -- Satış ve pazarlama için ICP gerekçesi
    tech_stack_json TEXT,                      -- CAD/CFD Teknolojileri JSON array
    status TEXT DEFAULT 'active',              -- 'active', 'lead', 'prospect', 'customer', 'archived'
    merged_into TEXT REFERENCES companies(id), -- Çelişkide ezilen kaydın referansı
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. DOĞRULANMIŞ İLETİŞİM KANALLARI (CONTACTS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    type TEXT CHECK(type IN ('email', 'phone', 'mobile', 'address', 'linkedin', 'social')),
    value TEXT NOT NULL,
    role_title TEXT,                           -- Örn: 'Kurucu Baş Mimar', 'Teknik Müdür'
    is_verified INTEGER DEFAULT 0,             -- 1 = Doğrulanmış
    verification_method TEXT,                  -- 'SMTP 250 OK', 'E.164 Validated', 'Geocode'
    legal_basis TEXT DEFAULT 'KVKK_md5_2f_Tacir', -- 'KVKK_md5_2f_Tacir', 'IYS_Onayli', 'IYS_Muaf'
    consent_status TEXT DEFAULT 'pending',     -- 'pending', 'opt_in', 'opt_out'
    confidence REAL DEFAULT 0.90,              -- 0.00 - 1.00 güven düzeyi
    last_checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. KAYNAK İZİ & KANIT ARŞİVİ (SOURCE_EVIDENCE - MinIO Snapshot Kanıtı)
-- ============================================================================
CREATE TABLE IF NOT EXISTS source_evidence (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,                 -- Örn: 'Ticaret Sicili Gazetesi', 'İMEAK DTO', 'Monaco Yacht Show'
    source_class TEXT CHECK(source_class IN ('A', 'B', 'C')), -- A: Resmi, B: Yarı Yapısal, C: Web/Çıkarım
    resolution_rule TEXT,                      -- 'VKN Kesin Eşleşme', 'Domain Kökü', 'Jaro-Winkler >= 0.92'
    raw_hash TEXT NOT NULL,                    -- SHA-256 snapshot hash
    raw_url TEXT,
    trust_weight REAL DEFAULT 80,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 4. SATIN ALMA NİYETİ SİNYALLERİ (INTENT_SIGNALS - Fuar, Kariyer, Sermaye)
-- ============================================================================
CREATE TABLE IF NOT EXISTS intent_signals (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,                 -- 'Fuar', 'Kariyer', 'Sermaye', 'EKAP', 'Teknoloji'
    label TEXT NOT NULL,
    detail TEXT,
    occurred_at TEXT NOT NULL,
    decay_weight REAL DEFAULT 1.0,             -- Zamanla azalan ağırlık katsayısı
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 5. LİSTELER & LİSTE ÜYELİKLERİ (LISTS & MEMBERSHIPS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS saved_lists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'Statik Liste',  -- 'Dinamik Liste (ICP ≥ 80)', 'Statik Liste'
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS list_memberships (
    list_id TEXT NOT NULL REFERENCES saved_lists(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (list_id, company_id)
);

-- ============================================================================
-- 6. MANUEL TEKİLLEŞTİRME KUYRUĞU (DEDUP_QUEUE - Jaro-Winkler >= 0.92)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dedup_queue (
    id TEXT PRIMARY KEY,
    similarity REAL NOT NULL,
    reason TEXT NOT NULL,
    left_name TEXT NOT NULL,
    left_source TEXT NOT NULL,
    left_address TEXT,
    left_company_id TEXT REFERENCES companies(id),
    right_name TEXT NOT NULL,
    right_source TEXT NOT NULL,
    right_address TEXT,
    right_company_id TEXT REFERENCES companies(id),
    status TEXT DEFAULT 'pending',             -- 'pending', 'merged', 'rejected'
    resolved_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 7. OTOMATİK E-POSTA KAMPANYALARI & SEKANS MOTORU (EMAIL CAMPAIGNS & SEQUENCES)
-- ============================================================================
CREATE TABLE IF NOT EXISTS email_campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                        -- Örn: 'Tersaneler CAD/CFD Soğuk Temas Q4'
    target_list_id TEXT REFERENCES saved_lists(id),
    status TEXT DEFAULT 'running',             -- 'draft', 'running', 'paused', 'completed'
    from_name TEXT NOT NULL DEFAULT 'NautiGraph Denizcilik',
    from_email TEXT NOT NULL DEFAULT 'outreach@nautigraph.marine',
    reply_to TEXT DEFAULT 'iletisim@nautigraph.marine',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sequence_steps (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,              -- 1, 2, 3...
    title TEXT NOT NULL,                       -- 'Adım 1: İlk Temas & Değer Önerisi'
    delay_days INTEGER DEFAULT 0,              -- Gönderim gecikmesi (0 = hemen, 3 = 3 gün sonra)
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL
);

-- ============================================================================
-- 8. GÖNDERİM LOGLARI & ETKİLEŞİM TAKİBİ (EMAIL_LOGS - İYS & ROKS Uyumlu)
-- ============================================================================
CREATE TABLE IF NOT EXISTS email_logs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES email_campaigns(id),
    step_id TEXT REFERENCES sequence_steps(id),
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id TEXT REFERENCES contacts(id),
    recipient_email TEXT NOT NULL,
    recipient_name TEXT,
    rendered_subject TEXT NOT NULL,
    rendered_body TEXT NOT NULL,
    status TEXT DEFAULT 'sent',                -- 'queued', 'sent', 'opened', 'clicked', 'replied', 'bounced', 'opt_out'
    smtp_response TEXT DEFAULT 'SMTP 250 OK: Message accepted for delivery',
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    opened_at TEXT,
    replied_at TEXT,
    opt_out_at TEXT,
    error_message TEXT
);

-- ============================================================================
-- 9. CRM SATIŞ BORU HATTI & KANBAN (CRM_DEALS & INTERACTIONS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'Yeni',        -- 'Yeni', 'İletişim Kuruldu', 'Demo/Keşif', 'Teklif Verildi', 'Kazanıldı', 'Kaybedildi'
    value_amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',      -- Yat sektöründe standart 'EUR' / 'USD'
    assigned_to TEXT DEFAULT 'Emin A.',
    proposal_scope TEXT,                       -- Teklif kapsamı özeti (CAD/CFD, Klas Onay, 3D Render)
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                        -- 'email', 'meeting', 'phone', 'proposal', 'signal_detected'
    note TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 10. SİSTEM & SMTP AYARLARI (SMTP_SETTINGS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- İndeksler (Sorgu performansı)
CREATE INDEX IF NOT EXISTS idx_comp_vkn ON companies(vkn);
CREATE INDEX IF NOT EXISTS idx_comp_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_comp_icp ON companies(icp_score);
CREATE INDEX IF NOT EXISTS idx_comp_province ON companies(province);
CREATE INDEX IF NOT EXISTS idx_comp_nace ON companies(nace_code);
CREATE INDEX IF NOT EXISTS idx_contacts_comp ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_evidence_comp ON source_evidence(company_id);
CREATE INDEX IF NOT EXISTS idx_signals_comp ON intent_signals(company_id);
CREATE INDEX IF NOT EXISTS idx_deals_comp ON crm_deals(company_id);
CREATE INDEX IF NOT EXISTS idx_deals_stage ON crm_deals(stage);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status);
CREATE INDEX IF NOT EXISTS idx_email_logs_comp ON email_logs(company_id);
