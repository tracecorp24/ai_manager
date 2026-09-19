const app = document.getElementById('app');

// ─── Yardımcı: HTML kaçışı ───────────────────────────────────────
const esc = (v = '') => String(v).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = { view: 'dashboard' };

// ─── Supabase API Katmanı ─────────────────────────────────────────

async function sbDashboard() {
  const { data, error } = await supabaseClient
    .from('dashboard_stats')
    .select('*')
    .single();
  if (error) throw new Error(error.message);
  return {
    companies: data.total_companies || 0,
    opportunities: data.total_opportunities || 0,
    demo_companies: data.demo_companies || 0,
    active_jobs: data.active_jobs || 0,
  };
}

async function sbCompanies(q = '') {
  let query = supabaseClient.from('companies').select('*').order('name').limit(200);
  if (q) query = query.or(`name.ilike.%${q}%,registration_no.ilike.%${q}%`);
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return data || [];
}

async function sbOpportunities(q = '') {
  const { data, error } = await supabaseClient
    .from('opportunities')
    .select('*, companies(name)')
    .order('id', { ascending: false });
  if (error) throw new Error(error.message);
  const list = (data || []).map(o => ({
    ...o,
    company_name: o.companies?.name || '-',
  }));
  if (!q) return list;
  const lq = q.toLocaleLowerCase('tr-TR');
  return list.filter(x => `${x.name} ${x.company_name}`.toLocaleLowerCase('tr-TR').includes(lq));
}

async function sbInsertCompany(payload) {
  const { data, error } = await supabaseClient.from('companies').insert(payload).select().single();
  if (error) throw new Error(error.message);
  return data;
}

async function sbInsertOpportunity(payload) {
  const { data, error } = await supabaseClient.from('opportunities').insert(payload).select().single();
  if (error) throw new Error(error.message);
  return data;
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
      <div class="card">Veritabanı<strong>Supabase</strong></div>
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
      <div><h1>Şirketler</h1><span class="muted">Supabase'deki şirket kayıtları</span></div>
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

// ─── Başlatma: Auth + Supabase Bağlantı Kontrolü ────────────────

(async () => {
  // Auth guard
  const authed = await initAuth();
  if (!authed) return;

  // Supabase health check
  const healthEl = document.getElementById('health');
  try {
    const { error } = await supabaseClient.from('companies').select('id').limit(1);
    healthEl.textContent = error ? '● Supabase bağlantı hatası' : '● Supabase bağlı';
    healthEl.style.color = error ? '#f87171' : '#4ade80';
  } catch {
    healthEl.textContent = '● Bağlantı bekleniyor';
    healthEl.style.color = '#fbbf24';
  }

  // İlk render
  render();
})();

