-- ============================================================
-- AI Manager — Migration 002: Gerçek Auth + RLS
-- Supabase SQL Editor'da çalıştır
-- ============================================================

-- ---- 1. Profiles tablosu (kullanıcı metadata) ----
CREATE TABLE IF NOT EXISTS profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name        TEXT,
    role        TEXT NOT NULL DEFAULT 'user',   -- 'admin' | 'user' | 'client'
    title       TEXT,
    customer_id TEXT,   -- 'client' rolü için: hangi CUST-X kodunu görebilir
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Kullanıcı kendi profilini okuyabilir
CREATE POLICY "profiles_select_own"
    ON profiles FOR SELECT TO authenticated
    USING (id = auth.uid());

-- Kullanıcı kendi profilini güncelleyebilir (adı, unvanı)
CREATE POLICY "profiles_update_own"
    ON profiles FOR UPDATE TO authenticated
    USING (id = auth.uid());

-- Admin tüm profilleri okuyabilir
CREATE POLICY "profiles_admin_read_all"
    ON profiles FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = auth.uid() AND p.role = 'admin'
        )
    );

-- ---- 2. Mevcut tablolara owner_id ekle ----
ALTER TABLE companies      ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id);
ALTER TABLE job_postings   ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id);
ALTER TABLE opportunities  ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id);
ALTER TABLE interactions   ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id);

-- ---- 3. Mevcut RLS politikalarını temizle ----
DROP POLICY IF EXISTS "auth_read_companies"         ON companies;
DROP POLICY IF EXISTS "auth_insert_companies"       ON companies;
DROP POLICY IF EXISTS "auth_update_companies"       ON companies;
DROP POLICY IF EXISTS "auth_delete_companies"       ON companies;
DROP POLICY IF EXISTS "auth_read_jobs"              ON job_postings;
DROP POLICY IF EXISTS "auth_insert_jobs"            ON job_postings;
DROP POLICY IF EXISTS "auth_update_jobs"            ON job_postings;
DROP POLICY IF EXISTS "auth_delete_jobs"            ON job_postings;
DROP POLICY IF EXISTS "auth_read_opps"              ON opportunities;
DROP POLICY IF EXISTS "auth_insert_opps"            ON opportunities;
DROP POLICY IF EXISTS "auth_update_opps"            ON opportunities;
DROP POLICY IF EXISTS "auth_read_interactions"      ON interactions;
DROP POLICY IF EXISTS "auth_insert_interactions"    ON interactions;

-- ---- 4. Companies — yeni RLS ----
CREATE POLICY "companies_select"
    ON companies FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()
        OR
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
        OR
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = auth.uid()
              AND p.role = 'client'
              AND p.customer_id IS NOT NULL
              AND companies.registration_no LIKE '%' || p.customer_id || '%'
        )
    );

CREATE POLICY "companies_insert"
    ON companies FOR INSERT TO authenticated
    WITH CHECK (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin','user'))
    );

CREATE POLICY "companies_update"
    ON companies FOR UPDATE TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "companies_delete"
    ON companies FOR DELETE TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

-- ---- 5. Job Postings — yeni RLS ----
CREATE POLICY "jobs_select"
    ON job_postings FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "jobs_insert"
    ON job_postings FOR INSERT TO authenticated
    WITH CHECK (owner_id = auth.uid());

CREATE POLICY "jobs_update"
    ON job_postings FOR UPDATE TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "jobs_delete"
    ON job_postings FOR DELETE TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

-- ---- 6. Opportunities — yeni RLS ----
CREATE POLICY "opps_select"
    ON opportunities FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "opps_insert"
    ON opportunities FOR INSERT TO authenticated
    WITH CHECK (owner_id = auth.uid());

CREATE POLICY "opps_update"
    ON opportunities FOR UPDATE TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

-- ---- 7. Interactions — yeni RLS ----
CREATE POLICY "interactions_select"
    ON interactions FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "interactions_insert"
    ON interactions FOR INSERT TO authenticated
    WITH CHECK (owner_id = auth.uid());

-- ---- 8. Yeni kullanıcı kaydında profiles'a otomatik satır ekle ----
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, name, role, title)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
        COALESCE(NEW.raw_user_meta_data->>'role', 'user'),
        COALESCE(NEW.raw_user_meta_data->>'title', 'Ekip Üyesi')
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ---- 9. Profiles updated_at trigger ----
CREATE OR REPLACE FUNCTION update_profiles_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_profiles_updated_at();
