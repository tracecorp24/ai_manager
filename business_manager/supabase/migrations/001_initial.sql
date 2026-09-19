-- AI Manager — Supabase PostgreSQL Migration
-- SQLite schema'dan çevrildi: business_manager/schema.sql

CREATE TABLE IF NOT EXISTS companies (
    id BIGSERIAL PRIMARY KEY,
    registration_no TEXT UNIQUE,
    name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    status TEXT NOT NULL DEFAULT 'Faal',
    phone TEXT,
    email TEXT,
    sector TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_postings (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    location TEXT,
    work_type TEXT NOT NULL DEFAULT 'Tam Zamanlı',
    description TEXT,
    requirements TEXT,
    salary TEXT,
    status TEXT NOT NULL DEFAULT 'Aktif',
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline DATE
);

CREATE TABLE IF NOT EXISTS opportunities (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'Yeni',
    amount NUMERIC NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS interactions (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    note TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_postings(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_postings(company_id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE VIEW dashboard_stats AS
SELECT
    (SELECT COUNT(*) FROM companies) AS total_companies,
    (SELECT COUNT(*) FROM job_postings WHERE status = 'Aktif') AS active_jobs,
    (SELECT COUNT(*) FROM opportunities) AS total_opportunities,
    (SELECT COUNT(*) FROM companies WHERE registration_no LIKE 'BM-DEMO-%') AS demo_companies;

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_postings ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "auth_read_companies" ON companies FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth_insert_companies" ON companies FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "auth_update_companies" ON companies FOR UPDATE TO authenticated USING (true);
CREATE POLICY "auth_delete_companies" ON companies FOR DELETE TO authenticated USING (true);

CREATE POLICY "auth_read_jobs" ON job_postings FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth_insert_jobs" ON job_postings FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "auth_update_jobs" ON job_postings FOR UPDATE TO authenticated USING (true);
CREATE POLICY "auth_delete_jobs" ON job_postings FOR DELETE TO authenticated USING (true);

CREATE POLICY "auth_read_opps" ON opportunities FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth_insert_opps" ON opportunities FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "auth_update_opps" ON opportunities FOR UPDATE TO authenticated USING (true);

CREATE POLICY "auth_read_interactions" ON interactions FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth_insert_interactions" ON interactions FOR INSERT TO authenticated WITH CHECK (true);
