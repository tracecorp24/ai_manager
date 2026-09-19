const app = document.getElementById('app');

// ─── Yardımcı: HTML kaçışı ───────────────────────────────────────
const esc = (v = '') => String(v).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = { view: 'dashboard' };

// ─── Demo veri katmanı ────────────────────────────────────────────

const DEMO_COMPANIES_KEY = 'ai_manager_demo_companies';
const DEMO_OPPORTUNITIES_KEY = 'ai_manager_demo_opportunities';

function savedCompanies() {
  try { return JSON.parse(localStorage.getItem(DEMO_COMPANIES_KEY) || '[]'); }
  catch { return []; }
}

function savedOpportunities() {
  try { return JSON.parse(localStorage.getItem(DEMO_OPPORTUNITIES_KEY) || '[]'); }
  catch { return []; }
}

let sampleCompaniesPromise;
function sampleCompanies() {
  if (!sampleCompaniesPromise) {
    sampleCompaniesPromise = fetch('musteri_listesi.json')
      .then(response => {
        if (!response.ok) throw new Error('Örnek şirket listesi yüklenemedi.');
        return response.json();
      })
      .then(rows => rows.map((row, id) => ({
        id,
        name: row['Ünvan'],
        registration_no: row['Sicil No'],
        district: row['İlçe'],
        sector: '',
        status: row['Durum'] || 'Faal',
      })));
  }
  return sampleCompaniesPromise;
}

async function sbDashboard() {
  const companies = await sbCompanies();
  const opportunities = savedOpportunities();
  return {
    companies: companies.length,
    opportunities: opportunities.length,
    active_jobs: opportunities.filter(opportunity => !['Kazanıldı', 'Kaybedildi'].includes(opportunity.stage)).length,
  };
}

async function sbCompanies(q = '') {
  const list = [...savedCompanies(), ...await sampleCompanies()];
  if (!q) return list;
  const needle = q.toLocaleLowerCase('tr-TR');
  return list.filter(company => `${company.name} ${company.registration_no || ''}`
    .toLocaleLowerCase('tr-TR').includes(needle));
}

async function sbOpportunities(q = '') {
  const companies = await sbCompanies();
  const list = savedOpportunities().map(opportunity => ({
    ...opportunity,
    company_name: companies.find(company => String(company.id) === String(opportunity.company_id))?.name || '-',
  }));
  if (!q) return list;
  const needle = q.toLocaleLowerCase('tr-TR');
  return list.filter(opportunity => `${opportunity.name} ${opportunity.company_name}`
    .toLocaleLowerCase('tr-TR').includes(needle));
}

async function sbInsertCompany(payload) {
  const company = { ...payload, id: Date.now() };
  localStorage.setItem(DEMO_COMPANIES_KEY, JSON.stringify([company, ...savedCompanies()]));
  return company;
}

async function sbInsertOpportunity(payload) {
  const opportunity = { ...payload, id: Date.now() };
  localStorage.setItem(DEMO_OPPORTUNITIES_KEY, JSON.stringify([opportunity, ...savedOpportunities()]));
  return opportunity;
}

// ─── Sayfalar ────────────────────────────────────────────────────

async function dashboard() {
  const d = await sbDashboard();
  app.innerHTML = `
    <section class="hero">
      <div><h1>Genel Bakış</h1>
      <span class="muted">Şirketlerinizi ve sunduğunuz hizmetleri tek ekrandan yönetin.</span></div>
    </section>
    <div class="cards">
      <div class="card">Toplam Şirket<strong>${d.companies}</strong></div>
      <div class="card">Aktif İş İlanı<strong>${d.active_jobs}</strong></div>
      <div class="card">Fırsatlar<strong>${d.opportunities}</strong></div>
      <div class="card">Çalışma Modu<strong>Demo</strong></div>
    </div>
    <div class="grid">
      <div class="panel">
        <h2>Hızlı Başlangıç</h2>
        <p class="muted">Müşteri ilişkileri, hizmet işleri, teklifler ve finans takibini CRM modülünden yönetin.</p>
        <button class="btn" data-go="crm">Müşteri CRM'i Aç</button>
      </div>
      <div class="panel">
        <h2>Ürün Modülleri</h2>
        <p class="muted">Şirket yönetimi, hizmet/iş takibi ve Marketing Stüdyosu aynı Business Manager ürünü içinde çalışır.</p>
      </div>
    </div>`;
}

async function companies() {
  const q = state.q || '';
  const list = await sbCompanies(q);
  app.innerHTML = `
    <section class="hero">
      <div><h1>Şirketler</h1><span class="muted">Örnek şirket listesi ve bu tarayıcıdaki kayıtlar</span></div>
    </section>
    <div class="panel">
      <div class="toolbar">
        <input id="search" class="input" placeholder="Şirket adı veya sicil no ara…" value="${esc(q)}">
        <button class="btn" id="searchBtn">Ara</button>
        <button class="btn" id="addCompanyBtn" style="margin-left:auto">+ Şirket Ekle</button>
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>Şirket</th><th>Sicil No</th><th>Konum</th><th>Sektör</th><th>Durum</th></tr></thead>
          <tbody>
            ${list.map(c => `<tr>
              <td><b>${esc(c.name)}</b></td>
              <td>${esc(c.registration_no || '-')}</td>
              <td>${esc(c.district || '-')}</td>
              <td>${esc(c.sector || '-')}</td>
              <td><span class="badge">${esc(c.status)}</span></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;

  document.getElementById('searchBtn').onclick = () => { state.q = document.getElementById('search').value; companies(); };
  document.getElementById('search').onkeydown = e => { if (e.key === 'Enter') document.getElementById('searchBtn').click(); };
  document.getElementById('addCompanyBtn').onclick = () => showAddCompanyModal();
}

async function services() {
  const q = state.q || '';
  const list = await sbOpportunities(q);
  app.innerHTML = `
    <section class="hero">
      <div><h1>Hizmetler ve İşler</h1>
      <span class="muted">Şirketlere verilen hizmetleri ve aktif işleri yönetin.</span></div>
    </section>
    <div class="panel">
      <div class="toolbar">
        <input id="search" class="input" placeholder="Hizmet veya şirket ara…" value="${esc(q)}">
        <button class="btn" id="searchBtn">Ara</button>
        <button class="btn" id="addOpportunityBtn" style="margin-left:auto">+ Fırsat Ekle</button>
      </div>
      <div class="job-list">
        ${list.length ? list.map(j => `
          <article class="job card">
            <h3>${esc(j.name)}</h3>
            <div class="meta">${esc(j.company_name)} · ${esc(j.stage)}</div>
            <p>${esc(j.notes || 'Not eklenmemiş')}</p>
            <span class="badge">₺${Number(j.amount || 0).toLocaleString('tr-TR')}</span>
          </article>`).join('') : '<div class="empty">Aktif hizmet işi bulunamadı.</div>'}
      </div>
    </div>`;

  document.getElementById('searchBtn').onclick = () => { state.q = document.getElementById('search').value; services(); };
  document.getElementById('search').onkeydown = e => { if (e.key === 'Enter') document.getElementById('searchBtn').click(); };
  document.getElementById('addOpportunityBtn').onclick = () => showAddOpportunityModal();
}

function marketing() { app.innerHTML = '<iframe class="marketing-frame" src="marketing.html" title="Marketing Sunum Stüdyosu"></iframe>'; }
function crm() { app.innerHTML = '<iframe class="marketing-frame" src="crm.html" title="Müşteri CRM"></iframe>'; }

// ─── Şirket Ekle Modal ─────────────────────────────────────────
function showAddCompanyModal() {
  const existing = document.getElementById('addCompanyModal');
  if (existing) existing.remove();
  const modal = document.createElement('div');
  modal.id = 'addCompanyModal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000';
  modal.innerHTML = `
    <div style="background:#1e2535;border-radius:16px;padding:32px;width:100%;max-width:440px;color:#fff">
      <h2 style="margin-bottom:20px">Yeni Şirket Ekle</h2>
      <label style="display:block;margin-bottom:8px;font-size:0.85rem;opacity:0.7">Şirket Adı *</label>
      <input id="mc_name" placeholder="Şirket adı" style="width:100%;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;margin-bottom:12px">
      <label style="display:block;margin-bottom:8px;font-size:0.85rem;opacity:0.7">Sicil No</label>
      <input id="mc_reg" placeholder="Sicil numarası" style="width:100%;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;margin-bottom:12px">
      <label style="display:block;margin-bottom:8px;font-size:0.85rem;opacity:0.7">İlçe / Şehir</label>
      <input id="mc_district" placeholder="İstanbul" style="width:100%;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;margin-bottom:12px">
      <label style="display:block;margin-bottom:8px;font-size:0.85rem;opacity:0.7">Sektör</label>
      <input id="mc_sector" placeholder="Makine / Yazılım / vb." style="width:100%;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;margin-bottom:20px">
      <div id="mc_err" style="color:#f87171;margin-bottom:12px;display:none"></div>
      <div style="display:flex;gap:12px;justify-content:flex-end">
        <button id="mc_cancel" style="padding:10px 20px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#fff;cursor:pointer">İptal</button>
        <button id="mc_save" style="padding:10px 20px;border-radius:8px;border:none;background:#667eea;color:#fff;cursor:pointer;font-weight:600">Kaydet</button>
      </div>
    </div>`;
  document.body.appendChild(modal);
  document.getElementById('mc_cancel').onclick = () => modal.remove();
  modal.onclick = e => { if (e.target === modal) modal.remove(); };
  document.getElementById('mc_save').onclick = async () => {
    const name = document.getElementById('mc_name').value.trim();
    const errEl = document.getElementById('mc_err');
    if (!name) { errEl.textContent = 'Şirket adı zorunludur.'; errEl.style.display = 'block'; return; }
    document.getElementById('mc_save').disabled = true;
    document.getElementById('mc_save').textContent = 'Kaydediliyor…';
    try {
      await sbInsertCompany({
        name,
        registration_no: document.getElementById('mc_reg').value.trim() || null,
        district: document.getElementById('mc_district').value.trim() || null,
        sector: document.getElementById('mc_sector').value.trim() || null,
        status: 'Faal',
      });
      modal.remove();
      await companies();
    } catch (e) {
      errEl.textContent = 'Hata: ' + e.message;
      errEl.style.display = 'block';
      document.getElementById('mc_save').disabled = false;
      document.getElementById('mc_save').textContent = 'Kaydet';
    }
  };
}

async function showAddOpportunityModal() {
  const companies = await sbCompanies();
  if (!companies.length) { alert('Önce bir şirket ekleyin.'); return; }
  const modal = document.createElement('div');
  modal.id = 'addOpportunityModal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000';
  modal.innerHTML = `
    <div style="background:#1e2535;border-radius:16px;padding:32px;width:100%;max-width:440px;color:#fff">
      <h2 style="margin:0 0 20px">Yeni Fırsat</h2>
      <label>Şirket</label><select id="mo_company" style="width:100%;margin:7px 0 12px;padding:10px;border-radius:8px">${companies.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select>
      <label>Fırsat adı *</label><input id="mo_name" style="width:100%;margin:7px 0 12px;padding:10px;border-radius:8px" placeholder="Örn. Tasarım projesi">
      <label>Aşama</label><select id="mo_stage" style="width:100%;margin:7px 0 12px;padding:10px;border-radius:8px"><option>Yeni</option><option>Teklif</option><option>Görüşme</option><option>Kazanıldı</option><option>Kaybedildi</option></select>
      <label>Tutar (₺)</label><input id="mo_amount" type="number" min="0" step="0.01" value="0" style="width:100%;margin:7px 0 12px;padding:10px;border-radius:8px">
      <label>Not</label><textarea id="mo_notes" style="width:100%;margin:7px 0 18px;padding:10px;border-radius:8px"></textarea>
      <div id="mo_error" style="color:#f87171;margin-bottom:12px;display:none"></div>
      <div style="display:flex;justify-content:flex-end;gap:12px"><button id="mo_cancel">İptal</button><button class="btn" id="mo_save">Kaydet</button></div>
    </div>`;
  document.body.appendChild(modal);
  document.getElementById('mo_cancel').onclick = () => modal.remove();
  document.getElementById('mo_save').onclick = async () => {
    const name = document.getElementById('mo_name').value.trim();
    const error = document.getElementById('mo_error');
    if (!name) { error.textContent = 'Fırsat adı zorunludur.'; error.style.display = 'block'; return; }
    await sbInsertOpportunity({
      company_id: document.getElementById('mo_company').value,
      name,
      stage: document.getElementById('mo_stage').value,
      amount: Number(document.getElementById('mo_amount').value) || 0,
      notes: document.getElementById('mo_notes').value.trim(),
    });
    modal.remove();
    await services();
  };
}

// ─── Render ──────────────────────────────────────────────────────

async function render() {
  try {
    if (state.view === 'dashboard') await dashboard();
    else if (state.view === 'crm') crm();
    else if (state.view === 'companies') await companies();
    else if (state.view === 'services') await services();
    else marketing();
  } catch (e) {
    app.innerHTML = `<div class="panel"><h2>Bir hata oluştu</h2><p class="muted">${esc(e.message)}</p></div>`;
  }
}

document.querySelectorAll('.nav').forEach(b => b.onclick = () => {
  document.querySelectorAll('.nav').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  state.view = b.dataset.view;
  state.q = '';
  render();
});

app.addEventListener('click', e => {
  const b = e.target.closest('[data-go]');
  if (b) {
    state.view = b.dataset.go;
    document.querySelector(`[data-view="${state.view}"]`).click();
  }
});

// ─── Başlatma: demo giriş kontrolü ────────────────────────────────

(async () => {
  // Auth guard
  const authed = await initAuth();
  if (!authed) return;

  const healthEl = document.getElementById('health');
  healthEl.textContent = '● Demo modu';
  healthEl.style.color = '#4ade80';

  // İlk render
  render();
})();
