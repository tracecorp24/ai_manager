const app = document.getElementById('app');
const api = async (path, options) => { const r = await fetch(path, options); const data = await r.json(); if (!r.ok) throw new Error(data.error || 'İstek başarısız'); return data; };
const esc = (v='') => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { view:'dashboard' };

async function dashboard(){
  const d=await api('/api/dashboard');
  app.innerHTML=`<section class="hero"><div><h1>Genel Bakış</h1><span class="muted">Şirketlerinizi ve sunduğunuz hizmetleri tek ekrandan yönetin.</span></div></section>
  <div class="cards"><div class="card">Toplam Şirket<strong>${d.companies}</strong></div><div class="card">Aktif Hizmet İşi<strong>${d.opportunities}</strong></div><div class="card">Müşteri CRM<strong>${d.demo_companies}</strong></div><div class="card">Veritabanı<strong>SQLite</strong></div></div>
  <div class="grid"><div class="panel"><h2>Hızlı Başlangıç</h2><p class="muted">Müşteri ilişkileri, hizmet işleri, teklifler ve finans takibini CRM modülünden yönetin.</p><button class="btn" data-go="crm">Müşteri CRM'i Aç</button></div><div class="panel"><h2>Ürün Modülleri</h2><p class="muted">Şirket yönetimi, hizmet/iş takibi ve Marketing Stüdyosu aynı Business Manager ürünü içinde çalışır.</p></div></div>`;
}
async function companies(){
  const q=state.q||''; const list=await api('/api/companies?q='+encodeURIComponent(q));
  app.innerHTML=`<section class="hero"><div><h1>Şirketler</h1><span class="muted">Veritabanındaki şirket kayıtları</span></div></section><div class="panel"><div class="toolbar"><input id="search" class="input" placeholder="Şirket adı veya sicil no ara…" value="${esc(q)}"><button class="btn" id="searchBtn">Ara</button></div><div class="table-wrap"><table class="table"><thead><tr><th>Şirket</th><th>Sicil No</th><th>Konum</th><th>Sektör</th><th>Durum</th></tr></thead><tbody>${list.map(c=>`<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.registration_no||'-')}</td><td>${esc(c.district||'-')}</td><td>${esc(c.sector||'-')}</td><td><span class="badge">${esc(c.status)}</span></td></tr>`).join('')}</tbody></table></div></div>`;
  document.getElementById('searchBtn').onclick=()=>{state.q=document.getElementById('search').value; companies()};
  document.getElementById('search').onkeydown=e=>{if(e.key==='Enter')document.getElementById('searchBtn').click()};
}
async function services(){
  const q=state.q||''; const all=await api('/api/opportunities'); const list=all.filter(x=>!q || `${x.name} ${x.company_name}`.toLocaleLowerCase('tr-TR').includes(q.toLocaleLowerCase('tr-TR')));
  app.innerHTML=`<section class="hero"><div><h1>Hizmetler ve İşler</h1><span class="muted">Şirketlere verilen hizmetleri ve aktif işleri yönetin.</span></div></section><div class="panel"><div class="toolbar"><input id="search" class="input" placeholder="Hizmet veya şirket ara…" value="${esc(q)}"><button class="btn" id="searchBtn">Ara</button></div><div class="job-list">${list.length?list.map(j=>`<article class="job card"><h3>${esc(j.name)}</h3><div class="meta">${esc(j.company_name)} · ${esc(j.stage)}</div><p>${esc(j.notes||'Not eklenmemiş')}</p><span class="badge">₺${Number(j.amount||0).toLocaleString('tr-TR')}</span></article>`).join(''):'<div class="empty">Aktif hizmet işi bulunamadı.</div>'}</div></div>`;
  document.getElementById('searchBtn').onclick=()=>{state.q=document.getElementById('search').value;services()};
  document.getElementById('search').onkeydown=e=>{if(e.key==='Enter')document.getElementById('searchBtn').click()};
}
function marketing(){ app.innerHTML='<iframe class="marketing-frame" src="marketing.html" title="Marketing Sunum Stüdyosu"></iframe>'; }
function crm(){ app.innerHTML='<iframe class="marketing-frame" src="crm.html" title="Müşteri CRM"></iframe>'; }
async function render(){ try { if(state.view==='dashboard')await dashboard(); else if(state.view==='crm')crm(); else if(state.view==='companies')await companies(); else if(state.view==='services')await services(); else marketing(); } catch(e){app.innerHTML=`<div class="panel"><h2>Bir hata oluştu</h2><p class="muted">${esc(e.message)}</p></div>`;} }
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>{document.querySelectorAll('.nav').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.view=b.dataset.view;state.q='';render()});
app.addEventListener('click',e=>{const b=e.target.closest('[data-go]');if(b){state.view=b.dataset.go;document.querySelector(`[data-view="${state.view}"]`).click()}});
api('/api/health').then(()=>document.getElementById('health').textContent='● Yerel DB bağlı').catch(()=>document.getElementById('health').textContent='● Bağlantı bekleniyor');
render();
