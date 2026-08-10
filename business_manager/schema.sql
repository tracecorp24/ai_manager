PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_no TEXT UNIQUE,
    name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    status TEXT NOT NULL DEFAULT 'Faal',
    phone TEXT,
    email TEXT,
    sector TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    location TEXT,
    work_type TEXT NOT NULL DEFAULT 'Tam Zamanlı',
    description TEXT,
    requirements TEXT,
    salary TEXT,
    status TEXT NOT NULL DEFAULT 'Aktif',
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deadline TEXT
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'Yeni',
    amount REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    note TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_postings(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_postings(company_id);
