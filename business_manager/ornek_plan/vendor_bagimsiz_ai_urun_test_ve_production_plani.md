# Vendor-Bağımsız AI/Web Ürünü Test ve Production’a Geçiş Planı

> **Amaç:** Küçük bir ürün/MVP’yi birkaç tester ile güvenli şekilde yayına almak; sistemi en baştan genel ve yaygın teknolojilerle kurmak; ileride Cloudflare, AWS, GCP, Azure, Hetzner, Railway, Render, DigitalOcean veya kendi sunucuna taşırken uygulamayı yeniden yazmak zorunda kalmamak.

---

# 0. Temel Mimari Prensibi

Bu projede en önemli karar:

> **Uygulamanın çekirdeği hiçbir hosting sağlayıcısına özel olmayacak.**

Kullanacağımız temel teknoloji seti:

- **Frontend:** React + Vite  
  - Alternatif: Next.js
- **Backend:** Python + FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Migration:** Alembic
- **Container:** Docker
- **Local orchestration:** Docker Compose
- **Reverse proxy:** Nginx veya Caddy
- **Source control:** Git + GitHub
- **CI/CD:** GitHub Actions
- **Object storage API standardı:** S3-compatible
- **Authentication:** JWT / OAuth2 / OpenID Connect
- **API format:** REST + JSON
- **Config:** `.env` / environment variables
- **Logging:** Python logging / structlog
- **Monitoring:** `/health`, uptime monitor, daha sonra Prometheus/Grafana/Sentry
- **DNS/CDN/SSL:** Cloudflare kullanılabilir ama uygulama buna bağımlı olmayacak.

---

# 1. Nihai Hedef Mimari

```text
                         INTERNET
                            │
                            ▼
                    domain.com
                            │
                            ▼
                ┌────────────────────┐
                │ DNS / CDN / SSL    │
                │ Cloudflare         │
                │ veya başka CDN     │
                └─────────┬──────────┘
                          │
              ┌───────────┴────────────┐
              │                        │
              ▼                        ▼
        app.domain.com            api.domain.com
              │                        │
              ▼                        ▼
        React Frontend             FastAPI
                                       │
                         ┌─────────────┼─────────────┐
                         │             │             │
                         ▼             ▼             ▼
                    PostgreSQL      S3 Storage     External APIs
                                                  OpenRouter
                                                  OpenAI
                                                  Anthropic
                                                  Gemini
                                       │
                                       ▼
                                  Background Jobs
                                       │
                                       ▼
                                  Python Worker
                                       │
                                       ▼
                                   GPU / ML
```

Bu yapının önemli özelliği:

```text
Cloudflare gider → uygulama çalışmaya devam eder.
AWS'ye geçersin → uygulama kodu değişmez.
Hetzner'a geçersin → Docker container'larını taşırsın.
Local sunucuya geçersin → yine aynı container'ları çalıştırırsın.
```

---

# 2. Geliştirme Aşamaları

Proje 10 ana fazda kurulacak.

```text
FAZ 1
Repository + klasör yapısı
        ↓
FAZ 2
FastAPI backend
        ↓
FAZ 3
PostgreSQL
        ↓
FAZ 4
Frontend
        ↓
FAZ 5
Docker
        ↓
FAZ 6
Authentication
        ↓
FAZ 7
AI / external API entegrasyonu
        ↓
FAZ 8
Test ortamı
        ↓
FAZ 9
CI/CD + monitoring
        ↓
FAZ 10
Production'a geçiş
```

---

# FAZ 1 — Proje İskeletini Kur

## 1.1 GitHub repository oluştur

Örnek isim:

```text
my-ai-product
```

Repository başta private olabilir.

---

## 1.2 Monorepo kullan

Önerilen yapı:

```text
my-ai-product/
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── workers/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── migrations/
│   ├── requirements.txt
│   ├── alembic.ini
│   └── Dockerfile
│
├── infrastructure/
│   ├── nginx/
│   ├── docker/
│   └── scripts/
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── deployment.md
│
├── .github/
│   └── workflows/
│
├── docker-compose.yml
├── docker-compose.test.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# FAZ 2 — Backend'i Kur

## 2.1 Python virtual environment

```bash
python -m venv .venv
```

Aktifleştir:

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

---

## 2.2 Temel paketleri yükle

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary alembic pydantic-settings python-dotenv
```

Development için:

```bash
pip install pytest httpx ruff black
```

---

## 2.3 İlk FastAPI uygulaması

`backend/app/main.py`

```python
from fastapi import FastAPI

app = FastAPI(
    title="My AI Product API",
    version="0.1.0"
)

@app.get("/health")
def health():
    return {
        "status": "ok"
    }
```

Çalıştır:

```bash
uvicorn app.main:app --reload
```

Test:

```text
http://localhost:8000/health
```

Beklenen:

```json
{
  "status": "ok"
}
```

---

# 3. API Katmanlarını Ayır

Backend büyürken her şeyi `main.py` içine koyma.

Önerilen yapı:

```text
backend/app/

api/
    users.py
    auth.py
    jobs.py
    ai.py

services/
    ai_service.py
    user_service.py

repositories/
    user_repository.py
    job_repository.py

models/
    user.py
    job.py

schemas/
    user.py
    job.py

core/
    config.py
    security.py
```

Mantık:

```text
HTTP request
    ↓
API Route
    ↓
Service
    ↓
Repository
    ↓
Database
```

Bu yapı provider bağımsızlığı açısından çok değerlidir.

---

# FAZ 3 — PostgreSQL

## Neden PostgreSQL?

Çünkü:

- açık kaynak
- endüstri standardı
- AWS destekler
- GCP destekler
- Azure destekler
- Supabase PostgreSQL kullanır
- Neon PostgreSQL kullanır
- Railway destekler
- Render destekler
- Docker ile local çalışır
- kendi VPS'inde çalışır

Yani veritabanını değiştirmek zorunda kalmazsın.

---

## 3.1 Docker ile local PostgreSQL

`docker-compose.yml`

```yaml
services:

  postgres:
    image: postgres:16

    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app

    ports:
      - "5432:5432"

    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Başlat:

```bash
docker compose up -d
```

---

# 4. Database URL

`.env`

```env
DATABASE_URL=postgresql://app:app@localhost:5432/app
```

Uygulama hiçbir zaman şunu bilmemeli:

```text
Supabase kullanıyorum
AWS kullanıyorum
Neon kullanıyorum
```

Sadece:

```text
DATABASE_URL
```

bilmeli.

Bu çok önemli bir tasarım prensibidir.

---

# 5. ORM — SQLAlchemy

Örnek:

```python
class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    email = Column(String, unique=True)

    created_at = Column(DateTime)
```

Kodun doğrudan PostgreSQL SQL sorgularına bağımlı olmaması bakım ve test işini kolaylaştırır.

---

# 6. Migration — Alembic

Database şemasını elle değiştirme.

Kullan:

```text
Alembic
```

Örneğin:

```bash
alembic revision --autogenerate -m "create users"
```

sonra:

```bash
alembic upgrade head
```

Production deployment sırasında:

```text
Container başlat
    ↓
Migration
    ↓
Backend başlat
```

---

# FAZ 4 — Frontend

## 7.1 React + Vite

Kur:

```bash
npm create vite@latest frontend
```

Seç:

```text
React
TypeScript
```

---

## Frontend yapısı

```text
frontend/src/

components/
pages/
services/
hooks/
contexts/
types/
utils/
```

API bağlantıları:

```text
frontend
    ↓
services/api.ts
    ↓
FastAPI
```

---

# 8. Backend URL hardcode etme

Yanlış:

```javascript
fetch("https://api.myserver.com/users")
```

Doğru:

```env
VITE_API_URL=https://api.example.com
```

Kod:

```javascript
fetch(`${import.meta.env.VITE_API_URL}/users`)
```

Local:

```env
VITE_API_URL=http://localhost:8000
```

Test:

```env
VITE_API_URL=https://api-test.example.com
```

Production:

```env
VITE_API_URL=https://api.example.com
```

---

# FAZ 5 — Docker

Burada gerçek taşınabilirlik başlıyor.

---

# 9. Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]
```

---

# 10. Frontend Dockerfile

Örneğin:

```dockerfile
FROM node:22 AS build

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build


FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
```

---

# 11. Tüm sistemi Docker Compose ile çalıştır

```text
docker compose
     │
     ├── frontend
     │
     ├── backend
     │
     └── postgres
```

Örnek:

```yaml
services:

  frontend:
    build: ./frontend

    ports:
      - "3000:80"

  backend:
    build: ./backend

    ports:
      - "8000:8000"

    env_file:
      - .env

    depends_on:
      - postgres

  postgres:
    image: postgres:16

    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app

    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Çalıştır:

```bash
docker compose up --build
```

---

# 12. Local sistem artık şöyle olur

```text
localhost:3000
       │
       ▼
     React
       │
       ▼
localhost:8000
       │
       ▼
    FastAPI
       │
       ▼
 PostgreSQL
```

Bu noktadan sonra aynı Docker image başka sunucuya taşınabilir.

---

# FAZ 6 — Authentication

Başlangıçta karmaşık authentication sistemi yazma.

Kullan:

```text
JWT
+
OAuth2
```

Temel akış:

```text
Login
  │
  ▼
Backend
  │
  ▼
Verify user
  │
  ▼
JWT
  │
  ▼
Browser
```

Sonraki request:

```text
Browser

Authorization:
Bearer eyJ...

      │
      ▼

FastAPI

      │

verify JWT

      ▼

request allowed
```

---

# 13. Tester sistemi

İlk sürümde public registration açma.

Database:

```text
testers

id
email
enabled
created_at
```

Akış:

```text
User login
    │
    ▼
email whitelist
    │
 ┌──┴───┐
 │      │
YES     NO
 │      │
 ▼      ▼
APP    403
```

Bu sistem test aşamasında son derece kullanışlıdır.

---

# FAZ 7 — External API / AI Layer

LLM sağlayıcısını doğrudan route içinde çağırma.

Yanlış:

```text
/api/generate
      │
      ▼
OpenRouter code
```

Doğru:

```text
API
 │
 ▼
AI Service
 │
 ▼
Provider Adapter
 │
 ├── OpenRouter
 ├── OpenAI
 ├── Anthropic
 └── Gemini
```

---

# 14. Provider Adapter Pattern

Örneğin:

```python
class LLMProvider:

    def generate(self, prompt):
        raise NotImplementedError
```

OpenRouter:

```python
class OpenRouterProvider(LLMProvider):

    def generate(self, prompt):
        ...
```

OpenAI:

```python
class OpenAIProvider(LLMProvider):

    def generate(self, prompt):
        ...
```

Uygulama:

```python
provider.generate(prompt)
```

der.

Böylece provider değiştirmek kolaylaşır.

---

# 15. Secrets

Asla GitHub'a koyma:

```text
OPENAI_API_KEY
OPENROUTER_API_KEY
DATABASE_PASSWORD
JWT_SECRET
```

`.gitignore`:

```text
.env
```

Repository'ye sadece:

```text
.env.example
```

koy.

Örnek:

```env
DATABASE_URL=
OPENROUTER_API_KEY=
JWT_SECRET=
```

---

# FAZ 8 — Background Jobs

Her işlem HTTP request içinde yapılmamalı.

Örneğin:

```text
PDF oluştur
video analiz et
50 web sayfası tara
LLM batch çalıştır
embedding üret
dataset işle
```

gibi işler background job olmalı.

---

# 16. Job mimarisi

```text
USER
 │
 │ POST /jobs
 ▼
FastAPI
 │
 ▼
PostgreSQL

status=queued
 │
 ▼
Queue
 │
 ▼
Python Worker
 │
 ▼
JOB
 │
 ▼
PostgreSQL

status=completed
```

---

# 17. Başlangıçta Queue

Başlangıçta:

```text
Redis + RQ
```

veya:

```text
Redis + Celery
```

kullanabilirsin.

Daha basit başlangıç:

```text
Redis + RQ
```

Daha büyük sistem:

```text
Redis + Celery
```

---

# 18. Neden Redis?

Çünkü Redis:

- open source
- Docker ile çalışır
- AWS'de bulunur
- GCP'de bulunur
- Azure'da bulunur
- VPS'te çalışır

Yani yine vendor bağımsızdır.

---

# FAZ 9 — Storage

Dosya yüklemeleri database'e konulmamalı.

Örneğin:

```text
PDF
image
video
dataset
model
export
```

Object storage kullanılmalı.

---

# 19. S3 standardını kullan

S3 API endüstri standardına dönüşmüştür.

Kod:

```text
Application
     │
     ▼
S3 API
     │
 ┌───┼─────────────┐
 ▼   ▼             ▼
AWS Cloudflare   MinIO
S3      R2
```

Yani kod aynı kalır.

Sadece:

```env
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=
```

değişir.

---

# 20. Local development storage

Local için:

```text
MinIO
```

kullanılabilir.

Docker Compose:

```text
frontend
backend
postgres
redis
minio
```

Bu küçük production sisteminin local kopyası olur.

---

# FAZ 10 — Reverse Proxy

Production'da:

```text
Internet
   │
   ▼
Nginx
   │
 ┌─┴────────────┐
 ▼              ▼
Frontend       FastAPI
```

veya:

```text
Caddy
```

kullanılabilir.

Caddy'nin avantajı SSL işlerini kolaylaştırmasıdır.

Cloudflare kullanıyorsan çoğu zaman:

```text
Cloudflare
    │
    ▼
Nginx/Caddy
    │
    ▼
Docker
```

olur.

---

# TEST ORTAMI

Testerlar doğrudan production kullanmamalı.

Üç environment oluştur:

```text
LOCAL
 │
 ▼
TEST
 │
 ▼
PRODUCTION
```

---

# 21. Domain yapısı

Örnek:

```text
app.domain.com

api.domain.com
```

Test:

```text
test.domain.com

api-test.domain.com
```

Admin:

```text
admin.domain.com
```

---

# 22. Environment config

Local:

```env
APP_ENV=local
```

Test:

```env
APP_ENV=test
```

Production:

```env
APP_ENV=production
```

Her ortam:

```text
ayrı database
ayrı secret
ayrı API key
```

kullanmalı.

---

# 23. Database ayrımı

Kesinlikle:

```text
test DB
```

ve:

```text
production DB
```

aynı olmamalı.

Örnek:

```text
product_test
product_prod
```

---

# 24. İlk Test Deployment

İlk test için basit bir sağlayıcı seçilebilir.

Önemli olan sağlayıcı değil:

> Docker image çalıştırabilmesi.

Örnekler:

```text
Railway
Render
Fly.io
Hetzner
DigitalOcean
AWS
GCP
Azure
```

Deployment:

```text
GitHub
   │
   ▼
Docker build
   │
   ▼
Container Registry
   │
   ▼
Test Server
```

---

# 25. CI/CD

GitHub Actions kullan.

Akış:

```text
Developer
   │
git push
   │
   ▼
GitHub
   │
   ▼
CI
   │
   ├── lint
   ├── tests
   ├── docker build
   └── security checks
          │
          ▼
       deploy
```

---

# 26. Branch Strategy

Basit tut:

```text
main
 │
 └── production

develop
 │
 └── test
```

Feature:

```text
feature/auth
feature/book-generator
feature/dashboard
```

Akış:

```text
feature
   ↓
develop
   ↓
TEST
   ↓
Pull Request
   ↓
main
   ↓
PRODUCTION
```

---

# 27. Otomatik Testler

Backend:

```text
pytest
```

Frontend:

```text
Vitest
```

API testleri:

```text
httpx
```

Minimum testler:

```text
health endpoint
auth
database
critical API routes
AI adapter mock
job creation
permission check
```

---

# 28. Health Check

Mutlaka:

```text
GET /health
```

Basit:

```json
{
  "status": "ok"
}
```

Daha gelişmiş:

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "storage": "ok"
}
```

---

# 29. Logging

Her request için:

```text
timestamp
request_id
user_id
endpoint
status
latency
```

AI çağrısı için:

```text
provider
model
input_tokens
output_tokens
latency
estimated_cost
status
```

---

# 30. Request ID

Her request:

```text
abc123
```

gibi ID almalı.

Flow:

```text
Frontend

request_id=abc123
      │
      ▼
FastAPI
      │
      ▼
AI Provider
      │
      ▼
Database
```

Bir hata olduğunda:

```text
abc123
```

ile tüm zinciri takip edebilirsin.

---

# 31. Error Tracking

Başlangıç:

```text
logs
```

Daha sonra:

```text
Sentry
```

eklenebilir.

---

# 32. Monitoring

İlk etap:

```text
Uptime monitor
      │
      ▼
/health
```

Kontrol:

```text
her 5 dakika
```

Eğer:

```text
200
```

geliyorsa:

```text
UP
```

gelmiyorsa:

```text
DOWN
```

---

# 33. Metrics

Ürünün takip etmesi gereken temel metrikler:

```text
requests/min
error rate
p50 latency
p95 latency
p99 latency
active users
AI calls
AI tokens
AI cost
job duration
queue size
```

---

# 34. Security

Minimum güvenlik listesi:

- HTTPS zorunlu
- API key frontend'de tutulmayacak
- JWT expiration
- refresh token
- rate limiting
- input validation
- CORS whitelist
- SQL injection koruması
- file type kontrolü
- file size limiti
- secrets environment variable
- DB backup
- admin endpoint protection

---

# 35. Rate Limiting

Örneğin:

```text
tester

60 request/min
```

AI endpoint:

```text
10 request/min
```

veya günlük:

```text
100 generation/day
```

---

# 36. AI Maliyet Koruması

Her kullanıcı için:

```text
daily_request_limit

daily_token_limit

monthly_cost_limit
```

tut.

Örnek:

```text
tester_1

daily generation: 50

token limit: 100,000

cost limit: $2
```

---

# 37. Backup

En az:

```text
PostgreSQL daily backup
```

yap.

Saklama:

```text
7 günlük
```

başlangıç için yeterli olabilir.

Daha sonra:

```text
30 gün
```

---

# 38. Database Migration Süreci

Deployment:

```text
new version
    │
    ▼
backup
    │
    ▼
database migration
    │
    ▼
deploy
    │
    ▼
health check
```

Migration başarısız:

```text
rollback
```

---

# 39. Production'a Geçmeden Önce Checklist

## Backend

- [ ] API routes tamam
- [ ] error handling
- [ ] validation
- [ ] authentication
- [ ] authorization
- [ ] rate limit
- [ ] logs
- [ ] health endpoint
- [ ] tests

## Database

- [ ] migrations
- [ ] indexes
- [ ] backup
- [ ] test/prod ayrımı

## Frontend

- [ ] environment config
- [ ] loading state
- [ ] error state
- [ ] auth handling
- [ ] mobile test

## Security

- [ ] secrets repository'de değil
- [ ] HTTPS
- [ ] CORS
- [ ] admin protection
- [ ] API limits

## Infrastructure

- [ ] Docker
- [ ] Docker Compose
- [ ] health check
- [ ] restart policy
- [ ] monitoring

---

# 40. Önerilen İlk Gerçek Test Stack'i

```text
                   DOMAIN
                      │
                      ▼
                 Cloudflare
            DNS + SSL + CDN
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
 test.domain.com            api-test.domain.com
        │                           │
        ▼                           ▼
 React/Vite                   FastAPI
                                  │
                   ┌──────────────┼──────────────┐
                   │              │              │
                   ▼              ▼              ▼
               PostgreSQL       Redis        S3/R2
                                  │
                                  ▼
                             Python Worker
                                  │
                                  ▼
                              AI APIs
```

---

# 41. Production Stack

```text
                        USERS
                          │
                          ▼
                       DOMAIN
                          │
                          ▼
                Cloudflare / CDN
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
           FRONTEND               API
           React                FastAPI
                                    │
                       ┌────────────┼─────────────┐
                       │            │             │
                       ▼            ▼             ▼
                   PostgreSQL     Redis          S3
                       │            │
                       │            ▼
                       │        Job Worker
                       │            │
                       │            ▼
                       │          AI / ML
                       │
                       ▼
                     Data
```

---

# 42. Provider Değiştirme Senaryosu

Diyelim başlangıç:

```text
Cloudflare
+
Railway
+
Supabase
```

Sonra AWS'ye geçtin.

Değişecek:

```text
DNS / deployment / connection strings
```

Çekirdek değişmeyecek:

```text
React

FastAPI

Python

PostgreSQL

Redis

S3 API

Docker
```

Yeni yapı:

```text
AWS CloudFront
      │
      ▼
React
      │
      ▼
ECS / EC2
      │
      ▼
FastAPI
      │
 ┌────┼────────┐
 ▼    ▼        ▼
RDS  ElastiCache S3
```

Uygulama mantığı aynı kalır.

---

# 43. Hetzner'a Geçiş

Örneğin düşük maliyetli VPS:

```text
Hetzner VPS
     │
     ▼
Docker Compose
     │
 ┌───┼───────────────┐
 ▼   ▼               ▼
React FastAPI      Redis
      │
      ▼
 PostgreSQL
```

Tek server ile bile başlangıç yapılabilir.

Kod aynı.

---

# 44. Local Server'a Geçiş

Aynı yapı:

```text
Senin Server
     │
     ▼
Docker
     │
 ┌───┼─────────────┐
 ▼   ▼             ▼
Web API          Worker
     │
     ▼
Database
```

Bu yüzden Docker kritik.

---

# 45. İleride Kubernetes Gerekirse

Başlangıçta Kubernetes kullanma.

Ancak sistem büyürse:

```text
Docker Containers
       │
       ▼
Kubernetes
```

geçiş mümkündür.

Çünkü uygulama zaten container olarak tasarlanmış olacak.

---

# 46. Öğrenme / Uygulama Sırası

Bu sırayı takip et:

## Hafta 1

```text
Git
GitHub
FastAPI
REST API
HTTP
```

## Hafta 2

```text
PostgreSQL
SQLAlchemy
Alembic
```

## Hafta 3

```text
React
API bağlantısı
environment variables
```

## Hafta 4

```text
Docker
Docker Compose
```

## Hafta 5

```text
Authentication
JWT
permissions
```

## Hafta 6

```text
OpenRouter / AI API
provider abstraction
usage logging
```

## Hafta 7

```text
Redis
background workers
jobs
```

## Hafta 8

```text
S3 / R2 / MinIO
file uploads
```

## Hafta 9

```text
GitHub Actions
CI/CD
tests
```

## Hafta 10

```text
test deployment
custom domain
HTTPS
monitoring
```

## Hafta 11

```text
tester onboarding
logs
bug fixing
metrics
```

## Hafta 12

```text
production readiness
backup
security
performance
```

---

# 47. İlk MVP İçin Minimum Gerekenler

Hepsini birden kurmak zorunda değilsin.

İlk versiyon:

```text
React
   │
   ▼
FastAPI
   │
   ├── PostgreSQL
   │
   └── OpenRouter
```

Docker:

```text
YES
```

GitHub:

```text
YES
```

Test deployment:

```text
YES
```

Redis:

```text
LATER
```

Queue:

```text
LATER
```

Object Storage:

```text
LATER
```

Kubernetes:

```text
MUCH LATER
```

---

# 48. MVP Aşaması

```text
                   Tester
                     │
                     ▼
              test.domain.com
                     │
                     ▼
                  React
                     │
                     ▼
                  FastAPI
                     │
             ┌───────┴────────┐
             ▼                ▼
        PostgreSQL        OpenRouter
```

Bu ilk gerçek ürün testin için yeterlidir.

---

# 49. İkinci Aşama

Kullanıcı ve işler artınca:

```text
                  FastAPI
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
 PostgreSQL        Redis          S3
                     │
                     ▼
                  Worker
```

---

# 50. Üçüncü Aşama

AI/ML ağırlaşırsa:

```text
                   FastAPI
                      │
                    Queue
                      │
             ┌────────┴─────────┐
             ▼                  ▼
        CPU Worker          GPU Worker
                                │
                                ▼
                            ML Model
```

---

# 51. Nihai Teknoloji Tablosu

| Katman | Teknoloji | Neden |
|---|---|---|
| Frontend | React + Vite | Yaygın, taşınabilir |
| Language | TypeScript | Frontend güvenliği |
| API | FastAPI | Python + AI için uygun |
| Language | Python | AI/automation ekosistemi |
| Database | PostgreSQL | Evrensel standart |
| ORM | SQLAlchemy | Taşınabilir data access |
| Migration | Alembic | Schema versioning |
| Queue | Redis | Yaygın |
| Worker | RQ/Celery | Python background job |
| Storage | S3 API | Provider bağımsız |
| Local S3 | MinIO | Self-hosted |
| Container | Docker | En kritik taşınabilirlik katmanı |
| Local infra | Docker Compose | Kolay development |
| CI/CD | GitHub Actions | Yaygın |
| DNS/CDN | Cloudflare | Ucuz/kolay, opsiyonel |
| Reverse Proxy | Nginx/Caddy | Standart |
| API Auth | OAuth2/JWT | Standart |
| Monitoring | Health + Uptime | İlk adım |
| Errors | Sentry | İleride |
| Metrics | Prometheus | İleride |
| Dashboard | Grafana | İleride |

---

# 52. Kaçınılması Gereken Vendor Lock-In

Başlangıçta mümkün olduğunca şunlardan kaçın:

```text
business logic içinde provider-specific SDK
```

Örneğin uygulama her yerde:

```python
cloudflare_d1.execute(...)
```

derse kötü.

Bunun yerine:

```python
user_repository.get_user(...)
```

de.

Repository'nin altında hangi DB olduğu uygulamanın geri kalanını ilgilendirmesin.

Aynı şekilde:

```text
storage.upload()
```

kullan.

Altında:

```text
R2
AWS S3
MinIO
```

hangisi olduğu önemli olmasın.

---

# 53. Portability Layer

İdeal yapı:

```text
                   BUSINESS LOGIC
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         Database     Storage     LLM
          Interface   Interface   Interface
              │          │          │
        ┌─────┼───┐  ┌───┼───┐  ┌──┼────────┐
        ▼     ▼   ▼  ▼   ▼   ▼  ▼  ▼        ▼
      Local  AWS ... S3 R2 MinIO GPT Claude Gemini
```

Bu katman seni sağlayıcılardan bağımsız yapar.

---

# 54. Senin İçin Önerilen İlk Yapı

Başlangıç:

```text
GitHub

React/Vite

FastAPI

PostgreSQL

Docker Compose

Cloudflare DNS

1 test server
```

Sonra:

```text
JWT

OpenRouter

usage logging

Redis

background worker

S3 storage

CI/CD
```

Sonra:

```text
monitoring

production

GPU workers

autoscaling
```

---

# 55. En Önemli 10 Kural

1. **Her şeyi Docker içinde çalıştır.**
2. **Database olarak PostgreSQL kullan.**
3. **Business logic'i provider SDK'larından ayır.**
4. **Config'leri environment variable kullanarak ver.**
5. **Test ve production database'lerini ayır.**
6. **Secrets'i Git repository'ye koyma.**
7. **Uzun işleri background job yap.**
8. **Dosyaları database'e koyma; object storage kullan.**
9. **Her deployment öncesi test çalıştır.**
10. **Önce basit MVP kur; Kubernetes gibi teknolojileri ihtiyaç çıkmadan ekleme.**

---

# 56. Önerilen Başlangıç Yol Haritası

```text
DAY 1
Repository
+
FastAPI
+
/health

      ↓

DAY 2
PostgreSQL
+
SQLAlchemy

      ↓

DAY 3
React
+
API connection

      ↓

DAY 4
Docker

      ↓

DAY 5
Authentication

      ↓

DAY 6
AI integration

      ↓

DAY 7
Deployment

      ↓

WEEK 2
Testers

      ↓

WEEK 3
Logs
Monitoring
Rate limits

      ↓

WEEK 4+
Jobs
Redis
Storage
CI/CD
```

---

# 57. Başlangıçta Kuracağımız Sistem

```text
                         INTERNET
                            │
                            ▼
                       Cloudflare
                       DNS + HTTPS
                            │
                  ┌─────────┴──────────┐
                  │                    │
                  ▼                    ▼
            test.domain.com       api-test.domain.com
                  │                    │
                  ▼                    ▼
             React/Vite             FastAPI
                                        │
                              ┌─────────┴──────────┐
                              ▼                    ▼
                         PostgreSQL            OpenRouter
```

Bu yapı:

- gerçek bir web ürünü gibi çalışır,
- kendi domainin vardır,
- birkaç tester kullanabilir,
- Python merkezlidir,
- AI projeleri için uygundur,
- Docker ile paketlenmiştir,
- PostgreSQL kullanır,
- vendor lock-in minimumdur,
- ileride kolayca büyütülebilir.

---

# 58. Daha Sonra Büyüyecek Hali

```text
                           USERS
                             │
                             ▼
                        CDN / WAF
                             │
             ┌───────────────┴───────────────┐
             │                               │
             ▼                               ▼
         Frontend                         FastAPI
                                             │
                 ┌───────────────────────────┼────────────────────────┐
                 │                           │                        │
                 ▼                           ▼                        ▼
             PostgreSQL                    Redis                    S3
                                             │
                                             ▼
                                           Queue
                                             │
                              ┌──────────────┴──────────────┐
                              ▼                             ▼
                          CPU Workers                   GPU Workers
                              │                             │
                              └──────────────┬──────────────┘
                                             ▼
                                         AI / ML
```

---

# Sonuç

Bu proje için önerilen çekirdek:

```text
React
+
FastAPI
+
Python
+
PostgreSQL
+
Docker
+
GitHub
```

Bunları **ürünün değişmeyen çekirdeği** olarak düşün.

Cloudflare, AWS, GCP, Azure, Hetzner, Railway ve diğer sağlayıcılar ise yalnızca:

```text
"Bu container'lar nerede çalışıyor?"
```

sorusunun cevabıdır.

Doğru tasarımda uygulamanın kendisi bunu mümkün olduğunca bilmez.

Bu yüzden hedef mimari:

```text
              PROVIDER-INDEPENDENT APPLICATION

                       React
                         │
                         ▼
                      FastAPI
                         │
               ┌─────────┼─────────┐
               ▼         ▼         ▼
           PostgreSQL   Redis      S3
                         │
                         ▼
                    Python Worker
                         │
                         ▼
                       AI/ML

---------------------------------------------------

                    INFRASTRUCTURE

              Cloudflare / AWS / GCP
              Azure / Hetzner / etc.
```

Bu ayrımı koruduğun sürece ürününü ileride istediğin altyapıya taşımak çok daha kolay olacaktır.
