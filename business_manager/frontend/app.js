/**
 * AI Manager — Unified Business & CRM Manager Engine
 * drk3.html temel alınarak tüm eksikleri giderilmiş tam sürüm.
 */

(async function () {
    // 1. Yetki ve Oturum Kontrolü (admin bypass destekli)
    if (!await guardProtectedPage()) return;

    // 2. Global Durum
    let musteriler = [];
    let pdfDosyalari = [];
    let historyStack = [];
    let historyIndex = -1;
    const MAX_HISTORY = 10; // 50 yerine 10 tutarak LocalStorage 5MB patlamasını engelliyoruz

    const state = {
        activeTab: 'tab1',
        page: 1,
        pageSize: 25,
        search: '',
        faaliyet: '',
        ilce: '',
        durum: '',
        jsonDurum: '',
        tarih: '',
    };

    // 3. Yardımcı Fonksiyonlar
    const esc = (v = '') => String(v ?? '').replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function getTumIsler() {
        return musteriler.flatMap(m => (m.isler || []).map(is => ({ ...is, musteriId: m.id })));
    }

    function getTumLinkler() {
        return musteriler.flatMap(m => (m.linkler || []).map(l => ({ ...l, musteriId: m.id })));
    }

    // 4. Veri Yükleme (JSON + LocalStorage + Supabase Hibrit)
    async function loadData() {
        const badge = document.getElementById('backendStatusBadge');
        if (badge) {
            badge.textContent = '● Veriler yükleniyor...';
            badge.style.color = '#fde047';
        }

        let jsonMusteriler = [];
        try {
            const response = await fetch('musteri_listesi.json');
            if (response.ok) {
                const data = await response.json();
                jsonMusteriler = data.map((item, idx) => ({
                    id: String(item["Sicil No"] || `CUST-${idx + 1}`),
                    ad: item["Ünvan"] || 'İsimsiz Şirket',
                    adres: item["Adres"] || '',
                    ilce: item["İlçe"] || 'Belirtilmemiş',
                    durum: item["Durum"] || 'Faal',
                    faaliyet: "Mekanik Tasarım", // Varsayılan sektör
                    telefon: item["Telefon"] || "-",
                    email: item["Email"] || "",
                    sonDurum: "",
                    sonNot: "",
                    sonTarih: "",
                    sonTarihISO: "",
                    isler: [],
                    linkler: []
                }));
            }
        } catch (e) {
            console.warn('[AI Manager] musteri_listesi.json yuklenemedi:', e);
        }

        // Yerel veriyi al
        let stored = localStorage.getItem('mekanikCRM_v2');
        if (stored) {
            try {
                let localData = JSON.parse(stored);
                let localMusteriler = localData.musteriler || [];
                pdfDosyalari = localData.pdfDosyalari || [];

                // Birleştir
                musteriler = jsonMusteriler.map(jm => {
                    let lm = localMusteriler.find(m => String(m.id) === String(jm.id));
                    if (lm) {
                        return {
                            ...jm,
                            telefon: lm.telefon || jm.telefon,
                            email: lm.email || jm.email,
                            faaliyet: lm.faaliyet || jm.faaliyet,
                            sonDurum: lm.sonDurum || "",
                            sonNot: lm.sonNot || "",
                            sonTarih: lm.sonTarih || "",
                            sonTarihISO: lm.sonTarihISO || "",
                            isler: lm.isler || [],
                            linkler: lm.linkler || []
                        };
                    }
                    return jm;
                });

                // JSON'da olmayıp yerelde eklenmiş yeni müşteriler
                localMusteriler.forEach(lm => {
                    if (!musteriler.some(m => String(m.id) === String(lm.id))) {
                        musteriler.unshift(lm);
                    }
                });
            } catch (e) {
                console.error('[AI Manager] Yerel veri parse hatasi:', e);
                musteriler = jsonMusteriler;
            }
        } else {
            musteriler = jsonMusteriler;
        }

        // Supabase durumunu kontrol et
        try {
            const health = await checkSupabaseHealth();
            if (health.online && badge) {
                badge.textContent = '● Supabase Canlı';
                badge.style.color = '#4ade80';
            } else if (badge) {
                badge.textContent = '● Yerel Test Modu';
                badge.style.color = '#38bdf8';
            }
        } catch {
            if (badge) {
                badge.textContent = '● Yerel Test Modu';
                badge.style.color = '#38bdf8';
            }
        }

        renderFiltreSecenekleri();
        renderAll();
        pushHistory();
    }

    // 5. Güvenli History & LocalStorage Saklama (Kotayı patlatmayan mekanizma)
    function pushHistory() {
        if (historyIndex < historyStack.length - 1) {
            historyStack = historyStack.slice(0, historyIndex + 1);
        }
        // Sadece değiştirilen veya dolu olan alanları sakla, devasa veriyi hafiflet
        const snapshot = {
            musteriler: JSON.parse(JSON.stringify(musteriler.slice(0, 300))), // En aktif kayıtlar
            pdfDosyalari: JSON.parse(JSON.stringify(pdfDosyalari))
        };
        historyStack.push(snapshot);
        if (historyStack.length > MAX_HISTORY) historyStack.shift();
        historyIndex = historyStack.length - 1;
    }

    function loadFromHistory(index) {
        if (index < 0 || index >= historyStack.length) return false;
        const snap = historyStack[index];
        snap.musteriler.forEach(sm => {
            const idx = musteriler.findIndex(m => String(m.id) === String(sm.id));
            if (idx !== -1) musteriler[idx] = JSON.parse(JSON.stringify(sm));
        });
        pdfDosyalari = JSON.parse(JSON.stringify(snap.pdfDosyalari));
        historyIndex = index;
        saveAll(false);
        return true;
    }

    function saveAll(addToHistory = true) {
        if (addToHistory) pushHistory();
        try {
            const data = { musteriler, pdfDosyalari };
            localStorage.setItem('mekanikCRM_v2', JSON.stringify(data));
        } catch (e) {
            console.warn('[AI Manager] LocalStorage kotası uyarısı, sadece değiştirilenler saklanıyor:', e);
            try {
                // Kota aşılırsa sadece notu/durumu değişen müşterileri sakla
                const modifiedOnly = musteriler.filter(m => m.sonDurum || m.sonNot || (m.isler && m.isler.length > 0));
                localStorage.setItem('mekanikCRM_v2', JSON.stringify({ musteriler: modifiedOnly, pdfDosyalari }));
            } catch (err) {
                console.error('[AI Manager] Kritik LocalStorage hatasi:', err);
            }
        }
        renderAll();
    }

    // 6. RENDER MOTORU
    function renderAll() {
        renderMusteriListesi();
        renderKanban();
        renderMailMusteriVePdf();
        renderCiroTablo();
        renderLinkler();
    }

    // ---------- 1. SEKME : MÜŞTERİ LİSTESİ & SAYFALAMA ----------
    function getFilteredMusteriler() {
        const arama = state.search.toLocaleLowerCase('tr-TR');
        return musteriler.filter(m => {
            if (arama) {
                const searchCorpus = `${m.ad} ${m.id} ${m.ilce || ''} ${m.telefon || ''} ${m.faaliyet || ''}`.toLocaleLowerCase('tr-TR');
                if (!searchCorpus.includes(arama)) return false;
            }
            if (state.faaliyet && m.faaliyet !== state.faaliyet) return false;
            if (state.ilce && m.ilce !== state.ilce) return false;
            if (state.durum && m.sonDurum !== state.durum) return false;
            if (state.jsonDurum && m.durum !== state.jsonDurum) return false;

            if (state.tarih) {
                const bugun = new Date();
                const birHaftaOnce = new Date(bugun.getTime() - 7 * 24 * 60 * 60 * 1000);
                const birAyOnce = new Date(bugun.getTime() - 30 * 24 * 60 * 60 * 1000);

                if (state.tarih === 'son1hafta') {
                    if (!m.sonTarihISO || new Date(m.sonTarihISO) < birHaftaOnce) return false;
                } else if (state.tarih === 'son1ay') {
                    if (!m.sonTarihISO || new Date(m.sonTarihISO) < birAyOnce) return false;
                } else if (state.tarih === 'eskı1ay') {
                    if (!m.sonTarihISO || new Date(m.sonTarihISO) >= birAyOnce) return false;
                } else if (state.tarih === 'hic') {
                    if (m.sonTarihISO && m.sonTarihISO !== '') return false;
                }
            }
            return true;
        });
    }

    function renderMusteriListesi() {
        const filtreli = getFilteredMusteriler();
        const totalItems = filtreli.length;
        const totalPages = Math.max(1, Math.ceil(totalItems / state.pageSize));

        if (state.page > totalPages) state.page = totalPages;
        if (state.page < 1) state.page = 1;

        const start = (state.page - 1) * state.pageSize;
        const end = Math.min(start + state.pageSize, totalItems);
        const pageItems = filtreli.slice(start, end);

        // Sayaç ve istatistik güncelle
        const infoEl = document.getElementById('paginationInfo');
        if (infoEl) {
            infoEl.textContent = totalItems > 0
                ? `Toplam ${totalItems.toLocaleString('tr-TR')} müşteriden ${start + 1}-${end} arası gösteriliyor`
                : 'Kayıt bulunamadı';
        }

        const pageInd = document.getElementById('pageNumberIndicator');
        if (pageInd) pageInd.textContent = `Sayfa ${state.page} / ${totalPages}`;

        const prevBtn = document.getElementById('prevPageBtn');
        const nextBtn = document.getElementById('nextPageBtn');
        if (prevBtn) prevBtn.disabled = state.page <= 1;
        if (nextBtn) nextBtn.disabled = state.page >= totalPages;

        const badge = document.getElementById('filterStatsBadge');
        if (badge) badge.textContent = `${totalItems.toLocaleString('tr-TR')} firma filtrelendi`;

        // 25 kartı DOM'a bas (hızlı & kasmayan render)
        let html = '';
        if (pageItems.length === 0) {
            html = '<div style="text-align:center; padding:48px 20px; color:#64748b;">Arama kriterlerine uygun müşteri bulunamadı.</div>';
        } else {
            pageItems.forEach(m => {
                const durumClass = m.sonDurum || '';
                const tarihGoster = m.sonTarih
                    ? `<div class="son-tarih-buyuk">📅 Son Temas: ${esc(m.sonTarih)}</div>`
                    : '<div class="son-tarih-buyuk">📅 Henüz görüşme yapılmadı</div>';

                html += `
                <div class="musteri-card ${durumClass}" data-id="${esc(m.id)}">
                    <div class="musteri-card-header">
                        <div class="musteri-info">
                            <strong>${esc(m.ad)}</strong>
                            <small>Sicil: ${esc(m.id)} · ${esc(m.ilce)} · Tel: ${esc(m.telefon || '-')} · Sektör: ${esc(m.faaliyet || '-')}</small>
                        </div>
                        <div class="musteri-not">
                            <input type="text" placeholder="Son görüşme / müşteri notu girin..." value="${esc(m.sonNot || '')}" data-id="${esc(m.id)}" class="notInput">
                        </div>
                        <div class="musteri-butonlar">
                            <button class="btn btn-sari" data-id="${esc(m.id)}" data-durum="sari" title="İletişime geçildi olarak işaretle">📞 İletişim</button>
                            <button class="btn btn-yesil" data-id="${esc(m.id)}" data-durum="yesil" title="İlgileniyor olarak işaretle">✅ İlgili</button>
                            <button class="btn btn-kirmizi" data-id="${esc(m.id)}" data-durum="kirmizi" title="Olumsuz olarak işaretle">❌ Olumsuz</button>
                            <button class="btn btn-secondary" data-id="${esc(m.id)}" data-action="delete" style="padding:6px 10px;" title="Müşteriyi Sil">🗑️</button>
                        </div>
                    </div>
                    ${tarihGoster}
                </div>`;
            });
        }

        const container = document.getElementById('musteriListesi');
        if (container) container.innerHTML = html;

        // Kart içi olaylar
        document.querySelectorAll('.notInput').forEach(inp => {
            inp.addEventListener('change', function () {
                const id = this.dataset.id;
                const m = musteriler.find(x => String(x.id) === String(id));
                if (m) {
                    m.sonNot = this.value;
                    m.sonTarih = new Date().toLocaleString('tr-TR');
                    m.sonTarihISO = new Date().toISOString();
                    saveAll();
                }
            });
        });

        document.querySelectorAll('.musteri-butonlar button[data-durum]').forEach(btn => {
            btn.addEventListener('click', function () {
                const id = this.dataset.id;
                const yeniDurum = this.dataset.durum;
                const m = musteriler.find(x => String(x.id) === String(id));
                if (m) {
                    m.sonDurum = (m.sonDurum === yeniDurum) ? '' : yeniDurum;
                    m.sonTarih = new Date().toLocaleString('tr-TR');
                    m.sonTarihISO = new Date().toISOString();
                    saveAll();
                }
            });
        });

        document.querySelectorAll('.musteri-butonlar button[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', function () {
                const id = this.dataset.id;
                const m = musteriler.find(x => String(x.id) === String(id));
                if (m && confirm(`"${m.ad}" müşterisini silmek istediğinize emin misiniz?`)) {
                    musteriler = musteriler.filter(x => String(x.id) !== String(id));
                    saveAll();
                }
            });
        });
    }

    function renderFiltreSecenekleri() {
        // Faaliyetler
        const faaliyetler = [...new Set(musteriler.map(m => m.faaliyet).filter(Boolean))].sort();
        const fSelect = document.getElementById('filtreFaaliyet');
        if (fSelect) {
            fSelect.innerHTML = '<option value="">Tüm Faaliyetler</option>' + faaliyetler.map(f => `<option value="${esc(f)}">${esc(f)}</option>`).join('');
        }

        // İlçeler
        const ilceler = [...new Set(musteriler.map(m => m.ilce).filter(Boolean))].sort();
        const iSelect = document.getElementById('filtreIlce');
        if (iSelect) {
            iSelect.innerHTML = '<option value="">Tüm İlçeler</option>' + ilceler.map(i => `<option value="${esc(i)}">${esc(i)}</option>`).join('');
        }

        // Şirket Durumu
        const dDurumlar = [...new Set(musteriler.map(m => m.durum).filter(Boolean))].sort();
        const jdSelect = document.getElementById('filtreJsonDurum');
        if (jdSelect) {
            jdSelect.innerHTML = '<option value="">Tüm Durumlar</option>' + dDurumlar.map(d => `<option value="${esc(d)}">${esc(d)}</option>`).join('');
        }
    }

    // ---------- 2. SEKME : KANBAN SÜREÇLERİ ----------
    function renderKanban() {
        const isler = getTumIsler();
        const sutunlar = [
            { baslik: "📞 İletişim & Tanıtım", durum: 0 },
            { baslik: "📄 Teklif Aşaması", durum: 1 },
            { baslik: "✅ Alınan İş", durum: 2 },
            { baslik: "📦 Teslim Edilen (Ödeme Bekliyor)", durum: 3 },
            { baslik: "💰 Ödemesi Alınan", durum: 4 }
        ];

        let boardHtml = '';
        sutunlar.forEach(s => {
            const sutunIsler = isler.filter(i => Number(i.durum) === s.durum);
            let kartlarHtml = '';

            sutunIsler.forEach(i => {
                const musteri = musteriler.find(m => String(m.id) === String(i.musteriId)) || { ad: 'Bilinmeyen Müşteri' };
                kartlarHtml += `
                <div class="kanban-kart" draggable="true" data-id="${i.id}" data-mid="${i.musteriId}">
                    <button class="kart-sil" data-id="${i.id}" data-mid="${i.musteriId}" title="İşi Sil">&times;</button>
                    <div class="kart-baslik">${esc(i.isAdi)}</div>
                    <div class="kart-detay"><b>${esc(musteri.ad)}</b></div>
                    ${i.aciklama ? `<div class="kart-detay" style="margin-top:4px;">${esc(i.aciklama)}</div>` : ''}
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span class="kart-tutar">₺${Number(i.tutar || 0).toLocaleString('tr-TR')}</span>
                        <!-- Mobil dokunmatik kolon degistirme -->
                        <select class="kanban-mobil-select" data-id="${i.id}" data-mid="${i.musteriId}" style="font-size:11px; padding:2px 4px; border-radius:6px; border:1px solid #cbd5e1;">
                            <option value="0" ${s.durum === 0 ? 'selected' : ''}>Aşama 1</option>
                            <option value="1" ${s.durum === 1 ? 'selected' : ''}>Aşama 2</option>
                            <option value="2" ${s.durum === 2 ? 'selected' : ''}>Aşama 3</option>
                            <option value="3" ${s.durum === 3 ? 'selected' : ''}>Aşama 4</option>
                            <option value="4" ${s.durum === 4 ? 'selected' : ''}>Aşama 5</option>
                        </select>
                    </div>
                </div>`;
            });

            boardHtml += `
            <div class="kanban-sutun" data-durum="${s.durum}">
                <div class="sutun-baslik">
                    <span>${s.baslik}</span>
                    <span>${sutunIsler.length}</span>
                </div>
                <div class="sutun-icerik" data-durum="${s.durum}">
                    ${kartlarHtml || '<p style="color:#94a3b8; text-align:center; padding:30px 10px; font-size:13px;">Bu aşamada aktif iş yok</p>'}
                </div>
            </div>`;
        });

        const kanbanBoard = document.getElementById('kanbanBoard');
        if (kanbanBoard) kanbanBoard.innerHTML = boardHtml;

        // Drag & Drop
        document.querySelectorAll('.kanban-kart').forEach(k => {
            k.addEventListener('dragstart', handleDragStart);
            k.addEventListener('dragend', handleDragEnd);
        });

        document.querySelectorAll('.sutun-icerik').forEach(s => {
            s.addEventListener('dragover', e => e.preventDefault());
            s.addEventListener('drop', handleDrop);
        });

        // Mobil dropdown ile kolon değiştirme
        document.querySelectorAll('.kanban-mobil-select').forEach(sel => {
            sel.addEventListener('change', function () {
                const id = parseInt(this.dataset.id);
                const mid = this.dataset.mid;
                const yeniDurum = parseInt(this.value);
                const m = musteriler.find(x => String(x.id) === String(mid));
                if (m) {
                    const is = (m.isler || []).find(y => y.id === id);
                    if (is) {
                        is.durum = yeniDurum;
                        saveAll();
                    }
                }
            });
        });

        // Kart silme
        document.querySelectorAll('.kart-sil').forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                const id = parseInt(this.dataset.id);
                const mid = this.dataset.mid;
                const m = musteriler.find(x => String(x.id) === String(mid));
                if (m && confirm('Bu işi silmek istediğinize emin misiniz?')) {
                    m.isler = (m.isler || []).filter(y => y.id !== id);
                    saveAll();
                }
            });
        });
    }

    let draggedItem = null;
    function handleDragStart(e) {
        draggedItem = this;
        e.dataTransfer.setData('text/plain', this.dataset.id);
        e.dataTransfer.setData('text/mid', this.dataset.mid);
        this.style.opacity = '0.4';
    }

    function handleDragEnd() {
        if (draggedItem) draggedItem.style.opacity = '1';
        draggedItem = null;
    }

    function handleDrop(e) {
        e.preventDefault();
        const sutun = this.closest('.kanban-sutun');
        if (!sutun || !draggedItem) return;

        const yeniDurum = parseInt(sutun.dataset.durum);
        const id = parseInt(draggedItem.dataset.id);
        const mid = draggedItem.dataset.mid;

        const m = musteriler.find(x => String(x.id) === String(mid));
        if (m) {
            const is = (m.isler || []).find(y => y.id === id);
            if (is && is.durum !== yeniDurum) {
                is.durum = yeniDurum;
                if (yeniDurum === 2 && !is.alinmaTarihi) is.alinmaTarihi = new Date().toISOString().split('T')[0];
                if (yeniDurum === 4 && !is.odemeTarihi) is.odemeTarihi = new Date().toISOString().split('T')[0];
                saveAll();
            }
        }
    }

    // ---------- 3. SEKME : MAİL & AI İLETİŞİM ----------
    function renderMailMusteriVePdf() {
        const pSel = document.getElementById('pdfSec');
        if (pSel) {
            pSel.innerHTML = '<option value="">PDF seçilmedi</option>' + pdfDosyalari.map(p => `<option value="${esc(p.ad)}">${esc(p.ad)}</option>`).join('');
        }

        const pCont = document.getElementById('pdfListesi');
        if (pCont) {
            pCont.innerHTML = pdfDosyalari.map(p => `
                <div class="pdf-item">
                    <span>📄 ${esc(p.ad)}</span>
                    <button class="btn btn-secondary" data-pdf="${esc(p.ad)}" style="padding:4px 8px; font-size:11px;" title="Sil">Sil</button>
                </div>
            `).join('') || '<p style="font-size:13px; color:#94a3b8;">Henüz PDF kataloğu eklenmemiş.</p>';

            pCont.querySelectorAll('button[data-pdf]').forEach(btn => {
                btn.addEventListener('click', function () {
                    const name = this.dataset.pdf;
                    pdfDosyalari = pdfDosyalari.filter(p => p.ad !== name);
                    saveAll();
                });
            });
        }
    }

    function generateStandardEmailDraft() {
        const mid = document.getElementById('mailMusteri')?.value;
        const amac = document.getElementById('mailAmac')?.value;
        const pdfAd = document.getElementById('pdfSec')?.value;

        const m = musteriler.find(x => String(x.id) === String(mid));
        if (!m) {
            alert('Lütfen önce bir müşteri seçin.');
            document.getElementById('mailMusteriAra')?.focus();
            return;
        }

        let metin = `Sayın ${m.ad} Yetkilisi,\n\n`;
        switch (amac) {
            case 'tanitim':
                metin += `Mekanik tasarım, 3D katı modelleme ve sonlu elemanlar analizi alanlarında sunduğumuz ileri mühendislik çözümleri ile ${m.ilce ? m.ilce + ' bölgesindeki ' : ''}üretim projelerinize değer katmak istiyoruz.\n\n` +
                    `Yetkinliklerimiz:\n` +
                    `• 3D CAD/CAM Tasarım ve Tersine Mühendislik\n` +
                    `• Yapısal ve Termal FEA/CFD Simülasyonları\n` +
                    `• Seri Üretime ve Talaşlı İmalata Uygun Mekanizma Tasarımı\n` +
                    `• Prototip Doğrulama ve Test Desteği\n\n` +
                    `Sizlerle uygun olduğunuz bir gün yüz yüze veya çevrimiçi kısa bir tanışma toplantısı gerçekleştirmekten memnuniyet duyarız.`;
                break;
            case 'yazilim':
                metin += `Şirketinizin tasarım ve imalat departmanlarının verimini artıracak endüstriyel CAD/CAM lisanslama ve eğitim paketlerimize dair özel fiyat teklifimizi bilgilerinize sunuyoruz.\n\n` +
                    `Avantajlı Çözümlerimiz:\n` +
                    `• Yıllık ve Sürekli Lisanslama Seçenekleri\n` +
                    `• Ekip İçi Uygulamalı Teknik Eğitim Desteği\n` +
                    `• Hızlı Teknik Destek ve Güncelleme Garantisi`;
                break;
            case 'hizmet':
                metin += `Devam eden veya planlanan projelerinizde dış kaynak mühendislik ve simülasyon danışmanlığı ihtiyacınız olması halinde yanınızdayız.\n\n` +
                    `Uzman kadromuzla esnek proje bazlı çalışma modelleri sunarak tasarım maliyetlerinizi optimize ediyoruz.`;
                break;
            case 'teklif':
                metin += `Görüşmüş olduğumuz mekanik tasarım ve analiz projesi için detaylı fiyat ve iş kapsamı teklifimiz hazırlanmıştır.\n\n` +
                    `Proje: Endüstriyel Mekanik Tasarım & Üretim Çizimleri\n` +
                    `Tahmini Teslimat: 4-6 Hafta\n` +
                    `Ödeme Koşulları: %30 Avans, %70 Nihai Teslimatta\n\n` +
                    `Teklifimizin detaylarını inceleyip geri dönüşünüzü rica ederiz.`;
                break;
            case 'durum':
                metin += `Yürütmekte olduğumuz projeniz kapsamında güncel durum raporu:\n\n` +
                    `• 3D Modelleme: %90 tamamlandı\n` +
                    `• Gerilme ve Dayanım Analizleri: Devam ediyor (Beklenen sonuç: 3 gün)\n` +
                    `• Üretim ve Montaj Paftaları: Hazırlık aşamasında\n\n` +
                    `Tüm süreç planlanan takvime uygun şekilde ilerlemektedir.`;
                break;
            case 'odeme':
                metin += `Tamamlanan iş teslimatına ait cari hesap bakiyesi ve fatura ödeme vadesi hususunu hatırlatmak isteriz.\n\n` +
                    `Ödeme Bilgilerimiz:\n` +
                    `Banka: Garanti BBVA\n` +
                    `IBAN: TR12 0006 2000 1234 5678 9012 34\n\n` +
                    `Ödemenin tamamlanmasını takiben dekont iletmenizi rica eder, iş birliğiniz için teşekkür ederiz.`;
                break;
            default:
                metin += `Mühendislik çalışmalarımız ve iş birliği fırsatlarımız hakkında görüşmek isteriz.`;
        }

        if (pdfAd) metin += `\n\nEk Belge: ${pdfAd}`;
        metin += `\n\nSaygılarımızla,\nAI Manager / Mekanik Mühendislik Grubu`;

        const taslakEl = document.getElementById('mailTaslak');
        if (taslakEl) taslakEl.value = metin;
    }

    // AI Kişiselleştirme & Zenginleştirme
    async function generateAiDraft() {
        const mid = document.getElementById('mailMusteri')?.value;
        const m = musteriler.find(x => String(x.id) === String(mid));
        if (!m) {
            alert('Lütfen önce bir müşteri seçin.');
            document.getElementById('mailMusteriAra')?.focus();
            return;
        }

        const amac = document.getElementById('mailAmac')?.value || 'tanitim';
        const tone = document.getElementById('aiTone')?.value || 'kurumsal';
        const extraNote = document.getElementById('aiEkstraNot')?.value || '';
        const apiKey = document.getElementById('aiApiKey')?.value || localStorage.getItem('ai_manager_api_key') || '';

        const taslakEl = document.getElementById('mailTaslak');
        if (taslakEl) taslakEl.value = '🤖 AI metni üretiyor, lütfen bekleyin...';

        // Modal kapat
        document.getElementById('aiModal').style.display = 'none';

        // Eğer OpenRouter / OpenAI API anahtarı varsa gerçek LLM çağrısı yap
        if (apiKey && apiKey.startsWith('sk-')) {
            try {
                localStorage.setItem('ai_manager_api_key', apiKey);
                const prompt = `Sen B2B mekanik tasarım ve mühendislik firması için satış direktörüsün. Müşteri: ${m.ad} (${m.ilce || ''} - ${m.faaliyet || 'Mekanik'}).
Amacımız: ${amac}.
Yazım tonu: ${tone}.
Ekstra not: ${extraNote}.
Müşterinin geçmiş son temas notu: ${m.sonNot || 'Yok'}.
Türkçe, son derece etkili, profesyonel, gereksiz laf kalabalığından uzak, harekete geçirici (Call to Action içeren) bir kurumsal e-posta metni yaz. Konu başlığı ile başla.`;

                const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${apiKey}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        model: 'google/gemini-2.0-flash-001',
                        messages: [{ role: 'user', content: prompt }]
                    })
                });

                if (res.ok) {
                    const data = await res.json();
                    const aiText = data.choices?.[0]?.message?.content;
                    if (aiText) {
                        taslakEl.value = aiText;
                        return;
                    }
                }
            } catch (err) {
                console.warn('[AI Manager] Harici LLM API hatasi, yerel akilli sablon devreye giriyor:', err);
            }
        }

        // Akıllı Yerel AI Fallback Motoru (API Key olmasa bile üst düzey dinamik metin)
        let baslik = `Konu: ${m.ad} & Mühendislik Çözüm Ortaklığı`;
        let govde = `Sayın ${m.ad} Karar Vericileri ve İlgili Yöneticileri,\n\n`;

        if (tone === 'ikna') {
            govde += `Endüstriyel imalat ve mekanik sistemlerde zaman ve maliyet kayıplarının önüne geçmek adına ${m.ilce ? m.ilce + ' bölgesinde ' : ''}faaliyet gösteren saygın firmanız için özel bir mühendislik iş birliği paketi hazırladık.\n\n` +
                `Sunduğumuz Somut Avantajlar:\n` +
                `1. %100 Doğrulanmış 3D CAD ve Analiz Desteği ile Hatalı İmalat Riskine Sıfır Tolerans\n` +
                `2. Proje Süreçlerinizde %25'e Varan İmalat & Malzeme Maliyeti Tasarrufu\n` +
                `3. İlk Projenize Özel Tanışma İndirimi ve Ön Fizibilite Raporu Hediyesi\n\n`;
        } else if (tone === 'teknik') {
            govde += `Firmanızın teknik projelerinde ihtiyaç duyabileceği ileri düzey Sonlu Elemanlar Analizi (FEA), Termal/CFD Modelleme ve ISO standartlarına uygun imalat paftaları üretiminde partneriniz olmaya hazırız.\n\n` +
                `Tasarım sürecinde SolidWorks, Catia ve ANSYS platformlarında gerçekleştirdiğimiz simülasyonlarla prototipleme maliyetlerinizi minimize ediyoruz.\n\n`;
        } else {
            govde += `${m.ad} olarak sektördeki başarılarınızı takdirle takip ediyoruz. Mekanik tasarım, mekanizma geliştirme ve teknik danışmanlık alanlarında şirketinizin hedeflerine nasıl katkı sağlayabileceğimizi görüşmek arzusundayız.\n\n`;
        }

        if (extraNote) {
            govde += `📌 Özel Notumuz: ${extraNote}\n\n`;
        }

        govde += `Konuyu kısaca değerlendirebilmeniz adına sizler için uygun bir takvimde 15 dakikalık bir görüşme planlayabilir miyiz?\n\n` +
            `Saygılarımızla,\n` +
            `İş Geliştirme & Mühendislik Ekibi\nAI Manager`;

        taslakEl.value = `${baslik}\n\n${govde}`;
    }

    // ---------- 4. SEKME : CİRO & KAR HESAPLARI (0 ₺ Bug'ı Düzeltildi) ----------
    function renderCiroTablo() {
        const tbody = document.getElementById('ciroTbody');
        if (!tbody) return;

        const isler = getTumIsler().filter(i => Number(i.durum) >= 2);
        let html = '';

        isler.forEach(i => {
            const musteri = musteriler.find(m => String(m.id) === String(i.musteriId)) || { ad: 'Bilinmeyen Müşteri' };
            const tutar = Number(i.tutar || 0);
            const masraf = Number(i.masraf || 0);
            const vergiOran = Number(i.vergiOran || 20); // Varsayılan KDV %20
            const vTut = tutar * vergiOran / 100;
            const kar = tutar - masraf - vTut;

            html += `
            <tr>
                <td><b>${esc(i.isAdi)}</b></td>
                <td>${esc(musteri.ad)}</td>
                <td>${esc(i.alinmaTarihi || '-')}</td>
                <td><input type="number" value="${tutar}" step="100" data-id="${i.id}" data-mid="${i.musteriId}" class="tutarInput"></td>
                <td><input type="number" value="${masraf}" step="100" data-id="${i.id}" data-mid="${i.musteriId}" class="masrafInput"></td>
                <td><input type="number" value="${vergiOran}" step="1" data-id="${i.id}" data-mid="${i.musteriId}" class="vergiOranInput"> %</td>
                <td><b>₺${vTut.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</b></td>
                <td style="color:${kar >= 0 ? '#16a34a' : '#dc2626'}; font-weight:700;">₺${kar.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td><input type="date" value="${i.odemeTarihi || ''}" data-id="${i.id}" data-mid="${i.musteriId}" class="odemeTarihiInput"></td>
            </tr>`;
        });

        tbody.innerHTML = html || '<tr><td colspan="9" style="padding:32px; color:#64748b;">Alınan veya tamamlanan aktif iş kaydı bulunamadı. Kanban\'dan iş ekleyebilirsiniz.</td></tr>';

        // Dinamik ve Hatasız Ciro & Kar Hesaplaması
        let toplamCiro = 0;
        let haftalikCiro = 0;
        let yillikCiro = 0;
        let toplamMasraf = 0;
        let toplamVergi = 0;

        const bugun = new Date();
        const yediGunOnce = new Date(bugun.getTime() - 7 * 24 * 60 * 60 * 1000);
        const mevcutYil = bugun.getFullYear();

        isler.forEach(i => {
            const tutar = Number(i.tutar || 0);
            const masraf = Number(i.masraf || 0);
            const vergiOran = Number(i.vergiOran || 20);
            const vTut = tutar * vergiOran / 100;

            toplamCiro += tutar;
            toplamMasraf += masraf;
            toplamVergi += vTut;

            // Tarih kontrolü
            const isTarihStr = i.odemeTarihi || i.alinmaTarihi;
            if (isTarihStr) {
                const d = new Date(isTarihStr);
                if (!isNaN(d.getTime())) {
                    if (d >= yediGunOnce) haftalikCiro += tutar;
                    if (d.getFullYear() === mevcutYil) yillikCiro += tutar;
                } else {
                    haftalikCiro += tutar;
                    yillikCiro += tutar;
                }
            } else {
                // Tarih girilmemişse aktif haftaya/yıla dahil et
                haftalikCiro += tutar;
                yillikCiro += tutar;
            }
        });

        const netKar = toplamCiro - toplamMasraf - toplamVergi;

        // Kartları güncelle
        const elAylik = document.getElementById('aylikCiro');
        const elHaftalik = document.getElementById('haftalikCiro');
        const elYillik = document.getElementById('yillikCiro');
        const elVergi = document.getElementById('toplamVergi');
        const elKar = document.getElementById('toplamKar');

        if (elAylik) elAylik.textContent = `📆 Toplam Ciro: ₺${toplamCiro.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}`;
        if (elHaftalik) elHaftalik.textContent = `📅 Bu Haftaki Ciro: ₺${haftalikCiro.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}`;
        if (elYillik) elYillik.textContent = `📈 Bu Yılki Ciro: ₺${yillikCiro.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}`;
        if (elVergi) elVergi.textContent = `🧾 Toplam Vergi: ₺${toplamVergi.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}`;
        if (elKar) elKar.textContent = `💰 Net Kar: ₺${netKar.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}`;

        // Tablo içi input değişiklikleri
        document.querySelectorAll('.tutarInput, .masrafInput, .vergiOranInput, .odemeTarihiInput').forEach(inp => {
            inp.addEventListener('change', function () {
                const id = parseInt(this.dataset.id);
                const mid = this.dataset.mid;
                const m = musteriler.find(x => String(x.id) === String(mid));
                if (m) {
                    const is = (m.isler || []).find(y => y.id === id);
                    if (is) {
                        if (this.classList.contains('tutarInput')) is.tutar = parseFloat(this.value) || 0;
                        if (this.classList.contains('masrafInput')) is.masraf = parseFloat(this.value) || 0;
                        if (this.classList.contains('vergiOranInput')) is.vergiOran = parseFloat(this.value) || 0;
                        if (this.classList.contains('odemeTarihiInput')) is.odemeTarihi = this.value;
                        saveAll();
                    }
                }
            });
        });
    }

    // ---------- 5. SEKME : MÜŞTERİ LİNKLERİ ----------
    function renderLinkler() {
        const tamDiv = document.getElementById('tamamlananIsler');
        const lDiv = document.getElementById('linkListesi');
        if (!tamDiv || !lDiv) return;

        const tamamlanan = getTumIsler().filter(i => Number(i.durum) === 4);
        tamDiv.innerHTML = tamamlanan.map(i => {
            const m = musteriler.find(x => String(x.id) === String(i.musteriId)) || { ad: 'Bilinmeyen' };
            return `
            <div class="link-item">
                <span><strong>${esc(i.isAdi)}</strong> (${esc(m.ad)})</span>
                <button class="btn btn-mavi btn-link" data-id="${i.id}" data-mid="${i.musteriId}">🔗 Link Ekle</button>
            </div>`;
        }).join('') || '<p style="font-size:13px; color:#64748b;">Ödemesi alınmış tamamlanan iş bulunmuyor.</p>';

        document.querySelectorAll('.btn-link').forEach(btn => {
            btn.addEventListener('click', function () {
                const id = parseInt(this.dataset.id);
                const mid = this.dataset.mid;
                const m = musteriler.find(x => String(x.id) === String(mid));
                const is = m?.isler?.find(y => y.id === id);
                if (!m || !is) return;

                const link = prompt('Müşteri için paylaşılacak URL linki girin:', 'https://');
                if (link && link.trim()) {
                    if (!m.linkler) m.linkler = [];
                    m.linkler.push({
                        isId: id,
                        link: link.trim(),
                        aciklama: is.isAdi,
                        tarih: new Date().toLocaleString('tr-TR')
                    });
                    saveAll();
                }
            });
        });

        lDiv.innerHTML = getTumLinkler().map(l => {
            const m = musteriler.find(x => String(x.id) === String(l.musteriId)) || { ad: 'Bilinmeyen' };
            return `
            <div class="link-item">
                <div>
                    <b>${esc(m.ad)}</b> — ${esc(l.aciklama)}:
                    <a href="${esc(l.link)}" target="_blank" style="color:#0284c7; text-decoration:none; word-break:break-all;">${esc(l.link)}</a>
                </div>
                <small style="color:#64748b;">${esc(l.tarih)}</small>
            </div>`;
        }).join('') || '<p style="font-size:13px; color:#64748b;">Henüz müşteri linki eklenmemiş.</p>';
    }

    // 7. ARAMA VE MODAL YARDIMCILARI
    function setupCustomerSearch(inputId, resultsId, targetHiddenId, onSelectCallback) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        const hidden = document.getElementById(targetHiddenId);
        if (!input || !results) return;

        input.addEventListener('input', function () {
            const val = this.value.trim().toLocaleLowerCase('tr-TR');
            if (val.length < 2) {
                results.style.display = 'none';
                return;
            }

            const matches = musteriler.filter(m =>
                m.ad.toLocaleLowerCase('tr-TR').includes(val) || String(m.id).toLocaleLowerCase('tr-TR').includes(val)
            ).slice(0, 8);

            if (matches.length > 0) {
                results.innerHTML = matches.map(m => `
                    <div class="search-item" data-id="${esc(m.id)}" data-ad="${esc(m.ad)}" data-email="${esc(m.email || '')}">
                        <b>${esc(m.ad)}</b> <small style="color:#64748b;">(Sicil: ${esc(m.id)} - ${esc(m.ilce)})</small>
                    </div>
                `).join('');
                results.style.display = 'block';

                results.querySelectorAll('.search-item').forEach(item => {
                    item.addEventListener('click', function () {
                        if (hidden) hidden.value = this.dataset.id;
                        input.value = this.dataset.ad;
                        results.style.display = 'none';
                        if (onSelectCallback) onSelectCallback(this.dataset.id, this.dataset.ad, this.dataset.email);
                    });
                });
            } else {
                results.innerHTML = '<div style="padding:10px; font-size:13px; color:#94a3b8;">Sonuç bulunamadı.</div>';
                results.style.display = 'block';
            }
        });

        document.addEventListener('click', e => {
            if (!input.contains(e.target) && !results.contains(e.target)) {
                results.style.display = 'none';
            }
        });
    }

    // 8. OLAY DİNLEYİCİLERİ VE BAŞLANGIÇ
    function initEventHandlers() {
        // Sekme Geçişleri
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                this.classList.add('active');
                state.activeTab = this.dataset.tab;
                const activeEl = document.getElementById(this.dataset.tab);
                if (activeEl) activeEl.classList.add('active');

                renderAll();
            });
        });

        // Arama (Debounce ile)
        let searchTimer = null;
        const aramaInput = document.getElementById('arama');
        if (aramaInput) {
            aramaInput.addEventListener('input', function () {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(() => {
                    state.search = this.value.trim();
                    state.page = 1;
                    renderMusteriListesi();
                }, 150);
            });
        }

        // Filtre Dropdownları
        ['filtreFaaliyet', 'filtreIlce', 'filtreDurum', 'filtreJsonDurum', 'filtreTarih'].forEach(fId => {
            const el = document.getElementById(fId);
            if (el) {
                el.addEventListener('change', function () {
                    const key = fId.replace('filtre', '').toLowerCase();
                    if (key === 'faaliyet') state.faaliyet = this.value;
                    else if (key === 'ilce') state.ilce = this.value;
                    else if (key === 'durum') state.durum = this.value;
                    else if (key === 'jsondurum') state.jsonDurum = this.value;
                    else if (key === 'tarih') state.tarih = this.value;

                    state.page = 1;
                    renderMusteriListesi();
                });
            }
        });

        // Filtreleri Temizle
        document.getElementById('filtreUygula')?.addEventListener('click', () => {
            state.search = '';
            state.faaliyet = '';
            state.ilce = '';
            state.durum = '';
            state.jsonDurum = '';
            state.tarih = '';

            const a = document.getElementById('arama'); if (a) a.value = '';
            const f = document.getElementById('filtreFaaliyet'); if (f) f.value = '';
            const i = document.getElementById('filtreIlce'); if (i) i.value = '';
            const d = document.getElementById('filtreDurum'); if (d) d.value = '';
            const j = document.getElementById('filtreJsonDurum'); if (j) j.value = '';
            const t = document.getElementById('filtreTarih'); if (t) t.value = '';

            state.page = 1;
            renderMusteriListesi();
        });

        // Sayfalama Butonları
        document.getElementById('prevPageBtn')?.addEventListener('click', () => {
            if (state.page > 1) {
                state.page--;
                renderMusteriListesi();
            }
        });

        document.getElementById('nextPageBtn')?.addEventListener('click', () => {
            state.page++;
            renderMusteriListesi();
        });

        // Geri / İleri Butonları
        document.getElementById('undoBtn')?.addEventListener('click', () => {
            if (historyIndex > 0) loadFromHistory(historyIndex - 1);
            else alert('Geri alınacak önceki işlem bulunamadı.');
        });

        document.getElementById('redoBtn')?.addEventListener('click', () => {
            if (historyIndex < historyStack.length - 1) loadFromHistory(historyIndex + 1);
            else alert('İleri alınacak işlem bulunamadı.');
        });

        // Dışa Aktar
        document.getElementById('exportData')?.addEventListener('click', () => {
            const blob = new Blob([JSON.stringify({ musteriler, pdfDosyalari }, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `ai_manager_crm_yedek_${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
        });

        // Yeni İş Modalı Aç/Kapat
        document.getElementById('yeniIsEkle')?.addEventListener('click', () => {
            const modal = document.getElementById('isModal');
            if (modal) {
                document.getElementById('modalMusteriAra').value = '';
                document.getElementById('modalSeciliMusteriId').value = '';
                document.getElementById('modalIsAdi').value = '';
                document.getElementById('modalIsTutar').value = '';
                document.getElementById('modalIsNot').value = '';
                modal.style.display = 'flex';
            }
        });

        document.getElementById('isModalClose')?.addEventListener('click', () => document.getElementById('isModal').style.display = 'none');
        document.getElementById('isModalIptal')?.addEventListener('click', () => document.getElementById('isModal').style.display = 'none');

        document.getElementById('isModalKaydet')?.addEventListener('click', () => {
            const mid = document.getElementById('modalSeciliMusteriId')?.value;
            const isAdi = document.getElementById('modalIsAdi')?.value.trim();
            const tutar = parseFloat(document.getElementById('modalIsTutar')?.value) || 0;
            const notlar = document.getElementById('modalIsNot')?.value.trim();

            if (!mid) { alert('Lütfen müşteri seçiniz.'); return; }
            if (!isAdi) { alert('Lütfen iş adını giriniz.'); return; }

            const m = musteriler.find(x => String(x.id) === String(mid));
            if (m) {
                if (!m.isler) m.isler = [];
                m.isler.push({
                    id: Date.now(),
                    isAdi,
                    tutar,
                    masraf: 0,
                    vergiOran: 20,
                    alinmaTarihi: new Date().toISOString().split('T')[0],
                    odemeTarihi: '',
                    durum: 0, // İlk aşama
                    aciklama: notlar
                });
                saveAll();
                document.getElementById('isModal').style.display = 'none';
            }
        });

        // Yeni Müşteri Modalı Aç/Kapat
        document.getElementById('yeniMusteriBtn')?.addEventListener('click', () => {
            const modal = document.getElementById('yeniMusteriModal');
            if (modal) {
                document.getElementById('ym_ad').value = '';
                document.getElementById('ym_sicil').value = '';
                document.getElementById('ym_ilce').value = '';
                document.getElementById('ym_faaliyet').value = 'Mekanik Tasarım';
                document.getElementById('ym_telefon').value = '';
                document.getElementById('ym_email').value = '';
                modal.style.display = 'flex';
            }
        });

        document.getElementById('yeniMusteriClose')?.addEventListener('click', () => document.getElementById('yeniMusteriModal').style.display = 'none');
        document.getElementById('yeniMusteriIptal')?.addEventListener('click', () => document.getElementById('yeniMusteriModal').style.display = 'none');

        document.getElementById('yeniMusteriKaydet')?.addEventListener('click', () => {
            const ad = document.getElementById('ym_ad')?.value.trim();
            if (!ad) { alert('Müşteri adı zorunludur.'); return; }

            const yeniMusteri = {
                id: document.getElementById('ym_sicil')?.value.trim() || `CUST-${Date.now()}`,
                ad,
                ilce: document.getElementById('ym_ilce')?.value.trim() || 'İstanbul',
                faaliyet: document.getElementById('ym_faaliyet')?.value.trim() || 'Mekanik',
                telefon: document.getElementById('ym_telefon')?.value.trim() || '-',
                email: document.getElementById('ym_email')?.value.trim() || '',
                durum: 'Faal',
                sonDurum: 'yesil',
                sonNot: 'Yeni eklendi',
                sonTarih: new Date().toLocaleString('tr-TR'),
                sonTarihISO: new Date().toISOString(),
                isler: [],
                linkler: []
            };

            musteriler.unshift(yeniMusteri);
            saveAll();
            document.getElementById('yeniMusteriModal').style.display = 'none';
            renderFiltreSecenekleri();
        });

        // Mail Olayları
        setupCustomerSearch('mailMusteriAra', 'mailMusteriSonuclari', 'mailMusteri');
        setupCustomerSearch('modalMusteriAra', 'modalMusteriSonuclari', 'modalSeciliMusteriId');

        document.getElementById('mailOlustur')?.addEventListener('click', generateStandardEmailDraft);

        document.getElementById('mailAiBtn')?.addEventListener('click', () => {
            const mid = document.getElementById('mailMusteri')?.value;
            if (!mid) {
                alert('Lütfen önce bir müşteri seçin.');
                document.getElementById('mailMusteriAra')?.focus();
                return;
            }
            document.getElementById('aiModal').style.display = 'flex';
        });

        document.getElementById('aiModalClose')?.addEventListener('click', () => document.getElementById('aiModal').style.display = 'none');
        document.getElementById('aiModalIptal')?.addEventListener('click', () => document.getElementById('aiModal').style.display = 'none');
        document.getElementById('aiModalUret')?.addEventListener('click', generateAiDraft);

        // Mail Gönder (Mailto)
        document.getElementById('mailGonderBtn')?.addEventListener('click', () => {
            const mid = document.getElementById('mailMusteri')?.value;
            const m = musteriler.find(x => String(x.id) === String(mid));
            const taslak = document.getElementById('mailTaslak')?.value || '';

            if (!taslak) { alert('Gönderilecek bir taslak metni bulunamadı.'); return; }

            const lines = taslak.split('\n');
            let subject = 'Mühendislik & Çözüm Ortaklığı Teklifi';
            let body = taslak;

            if (lines[0].toLowerCase().startsWith('konu:')) {
                subject = lines[0].replace(/konu:/i, '').trim();
                body = lines.slice(1).join('\n').trim();
            }

            const email = m?.email || '';
            const mailtoUrl = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
            window.open(mailtoUrl, '_blank');
        });

        // Panoya Kopyala
        document.getElementById('mailKopyalaBtn')?.addEventListener('click', function () {
            const taslak = document.getElementById('mailTaslak')?.value;
            if (!taslak) { alert('Kopyalanacak metin yok.'); return; }

            navigator.clipboard.writeText(taslak).then(() => {
                const oldText = this.textContent;
                this.textContent = '✓ Panoya Kopyalandı!';
                this.style.background = '#2d9c6b';
                setTimeout(() => {
                    this.textContent = oldText;
                    this.style.background = '';
                }, 1800);
            });
        });

        // Taslağı Sakla
        document.getElementById('mailKaydet')?.addEventListener('click', function () {
            const draft = document.getElementById('mailTaslak')?.value.trim();
            if (!draft) { alert('Kaydedilecek taslak yok.'); return; }
            localStorage.setItem('mekanikCRM_mail_taslagi', draft);
            const oldText = this.textContent;
            this.textContent = '✓ Taslak Saklandı';
            setTimeout(() => { this.textContent = oldText; }, 1800);
        });

        const savedDraft = localStorage.getItem('mekanikCRM_mail_taslagi');
        if (savedDraft) {
            const t = document.getElementById('mailTaslak');
            if (t) t.value = savedDraft;
        }

        // PDF Yükleme
        document.getElementById('pdfYukle')?.addEventListener('change', function (e) {
            Array.from(e.target.files).forEach(file => {
                if (!pdfDosyalari.some(p => p.ad === file.name)) {
                    pdfDosyalari.push({ ad: file.name });
                }
            });
            saveAll();
        });

        // Ciro Yeniden Hesapla
        document.getElementById('ciroHesapla')?.addEventListener('click', () => {
            saveAll();
            alert('Finansal hesaplamalar ve veriler güncellendi.');
        });
    }

    // Başlat
    initEventHandlers();
    await loadData();
})();
