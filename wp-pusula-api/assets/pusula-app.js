(() => {
  const state = {
    customers: [],
    selected: null,
    sales: [],
  };

  const apiBase = (window.PusulaApp && PusulaApp.apiBase) || '';
  const wpNonce = (window.PusulaApp && PusulaApp.nonce) || '';

  const todayStr = () => {
    const d = new Date();
    const pad = (n) => (n < 10 ? `0${n}` : n);
    return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`;
  };
  const toISO = (ddmmyyyy) => {
    if (!ddmmyyyy) return '';
    const [d, m, y] = ddmmyyyy.split('-');
    return `${y}-${m}-${d}`;
  };
  const fromISO = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}-${m}-${y}`;
  };

  const fromISOSlash = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
  };

  const defaultDueDay = () => Math.min(new Date().getDate(), 28);

  const isPaid = (val) => Number(val) === 1;

  const trErrorMessage = (msg) => {
    if (!msg) return 'Bilinmeyen hata.';
    if (msg.toLowerCase().includes('customer not found')) return 'Müşteri bulunamadı.';
    if (msg.toLowerCase().includes('not found')) return 'Kayıt bulunamadı.';
    if (msg.toLowerCase().includes('forbidden') || msg.toLowerCase().includes('unauthorized')) return 'Yetki hatası. Lütfen oturum açın.';
    return msg;
  };

  function setStatus(msg, isError = false) {
    const el = document.getElementById('pusula-status');
    if (el) {
      el.textContent = msg || '';
      el.style.color = isError ? '#f0a7a7' : '#88b7c9';
    }
  }

  async function api(path, opts = {}) {
    if (!apiBase) throw new Error('API ayarları eksik.');
    const res = await fetch(`${apiBase}${path}`, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        'X-WP-Nonce': wpNonce,
        ...(opts.headers || {}),
      },
      credentials: 'same-origin',
    });
    if (!res.ok) {
      const text = await res.text();
      let msg = text;
      try {
        msg = JSON.parse(text).message || msg;
      } catch (e) { /* ignore */ }
      throw new Error(msg || 'İstek başarısız.');
    }
    if (res.status === 204) return null;
    return res.json();
  }

  const debounce = (fn, wait = 200) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  };

  function renderTabs() {
    document.querySelectorAll('.pusula-tabs button').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.pusula-tabs button').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.getAttribute('data-tab');
        document.querySelectorAll('.pusula-tab-content').forEach((c) => (c.style.display = 'none'));
        const target = document.getElementById(`pusula-tab-${tab}`);
        if (target) target.style.display = 'block';
        if (tab === 'add' && !state.selected) {
          fillCustomerForm();
        }
      });
    });
  }

  // ------------------- Search -------------------
  function renderSearchTab() {
    const root = document.getElementById('pusula-tab-search');
    if (!root) return;
    root.innerHTML = `
      <div class="pusula-grid">
        ${['Müşteri No', 'İsim', 'Telefon', 'Adres'].map((label, idx) => `
          <label class="pusula-input">
            <span>${label}</span>
            <input type="text" data-field="${['id','name','phone','address'][idx]}">
          </label>
        `).join('')}
      </div>
      <div class="pusula-table-wrapper">
        <table class="pusula-table" id="pusula-search-table">
          <thead><tr><th>No</th><th>İsim</th><th>Telefon</th><th>Adres</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <div class="pusula-actions" id="pusula-nav-actions">
        <button id="nav-edit" disabled>MÜŞTERİ BİLGİLERİNİ DÜZELT</button>
        <button id="nav-sale" disabled>SATIŞ KAYDET</button>
        <button id="nav-detail" disabled>TAKSİTLİ SATIŞ KAYIT BİLGİSİ</button>
        <button id="nav-delete" disabled>MÜŞTERİ SİL</button>
      </div>
    `;
    const debouncedSearch = debounce(loadCustomers, 75);
    root.querySelectorAll('input[data-field]').forEach((inp) => {
      inp.addEventListener('input', debouncedSearch);
    });
    document.getElementById('nav-edit').addEventListener('click', () => {
      if (state.selected) {
        fillCustomerForm(state.selected);
        document.querySelector('button[data-tab="add"]').click();
      }
    });
    document.getElementById('nav-sale').addEventListener('click', () => {
      if (state.selected) {
        fillSaleCustomer(state.selected);
        document.querySelector('button[data-tab="sale"]').click();
      }
    });
    document.getElementById('nav-detail').addEventListener('click', () => {
      if (state.selected) {
        updateDetail(state.selected);
        document.querySelector('button[data-tab="detail"]').click();
        loadSales(state.selected.id);
      }
    });
    document.getElementById('nav-delete').addEventListener('click', deleteCustomer);
  }

  function renderTable(rows) {
    const tbody = document.querySelector('#pusula-search-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    let hasSelection = false;
    rows.forEach((r) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${r.id}</td><td>${r.name || ''}</td><td>${r.phone || ''}</td><td>${r.address || ''}</td>`;
      const isSelected = state.selected && String(state.selected.id) === String(r.id);
      tr.addEventListener('click', () => {
        state.selected = r;
        fillSaleCustomer(r);
        tbody.querySelectorAll('tr').forEach((row) => row.classList.remove('selected'));
        tr.classList.add('selected');
        enableNav(true);
      });
      tr.addEventListener('dblclick', () => {
        state.selected = r;
        fillSaleCustomer(r);
        updateDetail(r);
        document.querySelector('button[data-tab="detail"]').click();
        loadSales(r.id);
        tbody.querySelectorAll('tr').forEach((row) => row.classList.remove('selected'));
        tr.classList.add('selected');
        enableNav(true);
      });
      if (isSelected) {
        tr.classList.add('selected');
        state.selected = r;
        hasSelection = true;
      }
      tbody.appendChild(tr);
    });
    if (!rows.length || !hasSelection) {
      enableNav(false);
    }
  }

  async function loadCustomers() {
    const root = document.getElementById('pusula-tab-search');
    if (!root) return;
    const fields = {};
    root.querySelectorAll('input[data-field]').forEach((input) => {
      const val = input.value.trim();
      if (val) fields[input.getAttribute('data-field')] = val;
    });
    try {
      const query = new URLSearchParams({ limit: 100 });
      ['id','name','phone','address'].forEach((f) => {
        if (fields[f]) query.append(f, fields[f]);
      });
      const rows = await api(`/customers?${query.toString()}`);
      state.customers = rows || [];
      renderTable(state.customers);
      setStatus(`${state.customers.length} kayıt yüklendi.`);
      const addTab = document.querySelector('#pusula-tab-add');
      if (!state.selected && addTab && addTab.style.display !== 'none') {
        fillCustomerForm();
      }
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
      enableNav(false);
    }
  }

  function enableNav(enabled) {
    ['nav-edit', 'nav-sale', 'nav-detail', 'nav-delete'].forEach((id) => {
      const btn = document.getElementById(id);
      if (btn) btn.disabled = !enabled;
    });
  }

  async function deleteCustomer() {
    if (!state.selected) return;
    if (!window.confirm('Bu müşteriyi silmek istediğinize emin misiniz?')) return;
    try {
      await api(`/customers/${state.selected.id}`, { method: 'DELETE' });
      setStatus('Müşteri silindi.');
      state.selected = null;
      updateDetail(null);
      fillCustomerForm();
      enableNav(false);
      await loadCustomers();
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  // ------------------- Add/Edit Customer -------------------
  function renderAddTab() {
    const root = document.getElementById('pusula-tab-add');
    if (!root) return;
    root.innerHTML = `
      <div class="add-top-bar">
        <div class="form-row">
          <label>Müşteri No</label>
          <input type="text" id="cust-id">
        </div>
        <div class="form-row readonly">
          <label>Kayıt Tarihi</label>
          <div class="form-static" id="cust-date-label">${todayStr()}</div>
          <input type="hidden" id="cust-date-hidden" value="${todayStr()}">
        </div>
      </div>
      <div class="add-columns">
        <div class="add-left">
          <div class="form-row">
            <label>Adı Soyadı *</label>
            <input type="text" id="cust-name">
          </div>
          <div class="form-row">
            <label>Telefon</label>
            <input type="text" id="cust-phone">
          </div>
          <div class="form-row">
            <label>Ev Adresi</label>
            <input type="text" id="cust-address">
          </div>
          <div class="form-row">
            <label>İş Adresi</label>
            <input type="text" id="cust-work">
          </div>
          <div class="form-row textarea-row">
            <label>Notlar</label>
            <textarea id="cust-notes" rows="6"></textarea>
          </div>
        </div>
        <div class="add-right">
          <h4>Ek Kişi 1</h4>
          <div class="form-row">
            <label>Adı Soyadı</label>
            <input type="text" id="c1-name">
          </div>
          <div class="form-row">
            <label>Telefon</label>
            <input type="text" id="c1-phone">
          </div>
          <div class="form-row">
            <label>Ev Adresi</label>
            <input type="text" id="c1-home">
          </div>
          <div class="form-row">
            <label>İş Adresi</label>
            <input type="text" id="c1-work">
          </div>
          <h4>Ek Kişi 2</h4>
          <div class="form-row">
            <label>Adı Soyadı</label>
            <input type="text" id="c2-name">
          </div>
          <div class="form-row">
            <label>Telefon</label>
            <input type="text" id="c2-phone">
          </div>
          <div class="form-row">
            <label>Ev Adresi</label>
            <input type="text" id="c2-home">
          </div>
          <div class="form-row">
            <label>İş Adresi</label>
            <input type="text" id="c2-work">
          </div>
        </div>
      </div>
      <div class="pusula-actions add-actions">
        <button id="cust-save">Kaydet</button>
        <button id="cust-clear">Temizle</button>
      </div>
    `;
    root.querySelector('#cust-save').addEventListener('click', saveCustomer);
    root.querySelector('#cust-clear').addEventListener('click', () => fillCustomerForm());
    fillCustomerForm();
  }

  function collectContacts() {
    const contacts = [];
    const c1 = {
      name: document.getElementById('c1-name').value.trim(),
      phone: document.getElementById('c1-phone').value.trim(),
      home_address: document.getElementById('c1-home').value.trim(),
      work_address: document.getElementById('c1-work').value.trim(),
    };
    const c2 = {
      name: document.getElementById('c2-name').value.trim(),
      phone: document.getElementById('c2-phone').value.trim(),
      home_address: document.getElementById('c2-home').value.trim(),
      work_address: document.getElementById('c2-work').value.trim(),
    };
    [c1, c2].forEach((c) => {
      if (c.name || c.phone || c.home_address || c.work_address) contacts.push(c);
    });
    return contacts;
  }

  function fillCustomerForm(cust = null) {
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || '';
    };
    if (!cust) {
      ['cust-id','cust-name','cust-phone','cust-address','cust-work','cust-notes','c1-name','c1-phone','c1-home','c1-work','c2-name','c2-phone','c2-home','c2-work'].forEach((id) => set(id, ''));
      set('cust-id', String(nextCustomerId()));
      set('cust-date-label', todayStr());
      set('cust-date-hidden', todayStr());
      return;
    }
    set('cust-id', cust.id || '');
    set('cust-date-label', cust.registration_date ? fromISO(cust.registration_date) : todayStr());
    set('cust-date-hidden', cust.registration_date ? fromISO(cust.registration_date) : todayStr());
    set('cust-name', cust.name || '');
    set('cust-phone', cust.phone || '');
    set('cust-address', cust.address || '');
    set('cust-work', cust.work_address || '');
    set('cust-notes', cust.notes || '');
    const contacts = cust.contacts || [];
    const c1 = contacts[0] || {};
    const c2 = contacts[1] || {};
    set('c1-name', c1.name || '');
    set('c1-phone', c1.phone || '');
    set('c1-home', c1.home_address || '');
    set('c1-work', c1.work_address || '');
    set('c2-name', c2.name || '');
    set('c2-phone', c2.phone || '');
    set('c2-home', c2.home_address || '');
    set('c2-work', c2.work_address || '');
  }

  function nextCustomerId() {
    if (!state.customers || !state.customers.length) return 1;
    const maxId = state.customers.reduce((m, c) => Math.max(m, parseInt(c.id, 10) || 0), 0);
    return maxId + 1;
  }

  async function saveCustomer() {
    const name = document.getElementById('cust-name').value.trim();
    if (!name) {
      setStatus('Adı Soyadı zorunlu.', true);
      return;
    }
    const payload = {
      id: document.getElementById('cust-id').value.trim() || undefined,
      name,
      phone: document.getElementById('cust-phone').value.trim(),
      address: document.getElementById('cust-address').value.trim(),
      work_address: document.getElementById('cust-work').value.trim(),
      notes: document.getElementById('cust-notes').value.trim(),
      registration_date: toISO(document.getElementById('cust-date-hidden').value.trim() || todayStr()),
      contacts: collectContacts(),
    };
    const targetId = payload.id;
    const exists = targetId && state.customers.some((c) => String(c.id) === String(targetId));
    const method = exists ? 'PUT' : 'POST';
    const url = exists ? `/customers/${targetId}` : '/customers';
    if (!exists) {
      delete payload.id; // let backend assign id
    }
    try {
      const res = await api(url, {
        method,
        body: JSON.stringify(payload),
      });
      if (res && res.id) payload.id = res.id;
      setStatus('Müşteri kaydedildi.');
      const newCust = {
        id: payload.id,
        name: payload.name,
        phone: payload.phone,
        address: payload.address,
        work_address: payload.work_address,
        notes: payload.notes,
        registration_date: payload.registration_date,
        contacts: payload.contacts || [],
      };
      const existingIdx = state.customers.findIndex((c) => String(c.id) === String(newCust.id));
      if (existingIdx >= 0) {
        state.customers[existingIdx] = newCust;
      } else {
        state.customers.unshift(newCust);
      }
      state.selected = newCust;
      renderTable(state.customers);
      enableNav(true);
      updateDetail(newCust);
      fillCustomerForm(newCust);
      fillSaleCustomer(newCust);
      document.querySelector('button[data-tab="sale"]').click();
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  // ------------------- Sale -------------------
  function renderSaleTab() {
    const root = document.getElementById('pusula-tab-sale');
    if (!root) return;
    root.innerHTML = `
      <div class="sale-container">
        <div class="sale-left">
          <div class="form-row">
            <label>Müşteri No *</label>
            <input type="text" id="sale-cust-id">
          </div>
          <div class="form-row">
            <label>Adı Soyadı</label>
            <input type="text" id="sale-cust-name" disabled>
          </div>
          <div class="form-row">
            <label>Tarih (GG-AA-YYYY)</label>
            <input type="text" id="sale-date" value="${todayStr()}">
          </div>
          <div class="form-row">
            <label>Toplam Tutar *</label>
            <input type="number" step="0.01" id="sale-total">
          </div>
          <div class="form-row">
            <label>Peşinat</label>
            <input type="number" step="0.01" id="sale-down" value="0">
          </div>
          <div class="form-row">
            <label>Taksit Sayısı *</label>
            <input type="number" id="sale-n" value="1">
          </div>
          <div class="form-row">
            <label>Ödeme Günü (1-28)</label>
            <input type="number" id="sale-due" value="${defaultDueDay()}">
          </div>
          <div class="sale-preview">
            <strong>Önizleme</strong>
            <div><span>Her Taksit Tutarı:</span> <span id="sale-preview-amt">—</span></div>
            <div><span>Son Taksit Tarihi:</span> <span id="sale-preview-date">—</span></div>
          </div>
        </div>
        <div class="sale-right">
          <label>Açıklama</label>
          <textarea id="sale-desc" rows="8"></textarea>
        </div>
      </div>
      <div class="pusula-actions sale-actions">
        <button id="sale-save">Kaydet</button>
        <button id="sale-clear">Temizle</button>
      </div>
    `;
    root.querySelector('#sale-save').addEventListener('click', saveSale);
    root.querySelector('#sale-clear').addEventListener('click', () => {
      ['sale-total','sale-down','sale-n','sale-due','sale-desc'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = id === 'sale-down' ? '0' : id === 'sale-n' ? '1' : id === 'sale-due' ? String(defaultDueDay()) : '';
      });
      document.getElementById('sale-date').value = todayStr();
      updateSalePreview();
    });
    ['sale-total','sale-down','sale-n','sale-due'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', updateSalePreview);
    });
    updateSalePreview();
  }

  function fillSaleCustomer(cust) {
    if (!cust) return;
    const idEl = document.getElementById('sale-cust-id');
    const nameEl = document.getElementById('sale-cust-name');
    if (idEl) idEl.value = cust.id || '';
    if (nameEl) nameEl.value = cust.name || '';
  }

  async function saveSale() {
    const custId = document.getElementById('sale-cust-id').value.trim();
    if (!custId) {
      setStatus('Müşteri seçiniz.', true);
      return;
    }
    const total = parseFloat(document.getElementById('sale-total').value);
    const down = parseFloat(document.getElementById('sale-down').value || '0');
    const nInst = parseInt(document.getElementById('sale-n').value || '1', 10);
    const dueDay = parseInt(document.getElementById('sale-due').value || '1', 10);
    if (!total || total <= 0 || nInst < 1 || dueDay < 1 || dueDay > 28) {
      setStatus('Satış alanlarını kontrol edin.', true);
      return;
    }
    const saleDateISO = toISO(document.getElementById('sale-date').value || todayStr());
    const desc = document.getElementById('sale-desc').value.trim();
    try {
      setStatus('Kaydediliyor...');
      const sale = await api('/sales', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: parseInt(custId, 10),
          date: saleDateISO,
          total,
          description: desc,
        }),
      });
      const saleId = sale.id;
      const remaining = total - down;
      const instAmt = Math.round((remaining / nInst) * 100) / 100;
      const instCalls = [];
      const instList = [];
      for (let i = 1; i <= nInst; i++) {
        const d = new Date(saleDateISO);
        d.setMonth(d.getMonth() + i);
        d.setDate(Math.min(dueDay, 28));
        const dueIso = d.toISOString().slice(0, 10);
        instCalls.push(
          api('/installments', {
            method: 'POST',
            body: JSON.stringify({
              sale_id: saleId,
              due_date: dueIso,
              amount: instAmt,
              paid: 0,
            }),
          }).then((instRes) => {
            instList.push({
              id: instRes?.id,
              sale_id: saleId,
              due_date: dueIso,
              amount: instAmt,
              paid: 0,
            });
            return instRes;
          })
        );
      }
      await Promise.all(instCalls);
      setStatus('Satış ve taksitler kaydedildi.');
      if (state.selected) loadSales(state.selected.id);
      fillSaleCustomer(state.selected);
      updateSalePreview();
      const saleData = {
        id: saleId,
        date: saleDateISO,
        total,
        description: desc,
        down,
        installments: instList,
      };
      if (window.confirm('Satış makbuzu yazdırılsın mı?')) {
        printReceiptDetailed(saleData, state.selected || { id: custId });
      }
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  function updateSalePreview() {
    const total = parseFloat(document.getElementById('sale-total')?.value || '0');
    const down = parseFloat(document.getElementById('sale-down')?.value || '0');
    const nInst = parseInt(document.getElementById('sale-n')?.value || '1', 10);
    const dueDay = parseInt(document.getElementById('sale-due')?.value || '1', 10);
    const saleDate = toISO(document.getElementById('sale-date')?.value || todayStr());
    const remain = Math.max(0, total - down);
    const per = nInst > 0 ? (remain / nInst) : 0;
    const amtEl = document.getElementById('sale-preview-amt');
    const dateEl = document.getElementById('sale-preview-date');
    if (amtEl) amtEl.textContent = isFinite(per) ? per.toFixed(2) + ' ₺' : '—';
    if (dateEl) {
      if (!saleDate || !isFinite(dueDay)) {
        dateEl.textContent = '—';
      } else {
        const d = new Date(saleDate);
        d.setMonth(d.getMonth() + nInst);
        d.setDate(Math.min(dueDay, 28));
        dateEl.textContent = fromISO(d.toISOString().slice(0, 10));
      }
    }
  }

  // ------------------- Detail -------------------
  function renderDetailTab() {
    const root = document.getElementById('pusula-tab-detail');
    if (!root) return;
    root.innerHTML = `
      <div id="pusula-detail-header" class="pusula-card">
        <p><strong>No:</strong> <span data-field="id">-</span></p>
        <p><strong>İsim:</strong> <span data-field="name">-</span></p>
        <p><strong>Telefon:</strong> <span data-field="phone">-</span></p>
        <p><strong>Adres:</strong> <span data-field="address">-</span></p>
      </div>
      <div class="pusula-flex">
        <div class="pusula-half">
          <h4 class="pusula-subtitle">Satışlar</h4>
          <div class="pusula-table-wrapper">
            <table class="pusula-table" id="pusula-sales-table">
              <thead><tr><th>No</th><th>Tarih</th><th>Tutar</th><th>Açıklama</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <div class="pusula-actions">
            <button id="btn-print-sale" disabled>Makbuz Yazdır</button>
          </div>
        </div>
        <div class="pusula-half">
          <h4 class="pusula-subtitle">Taksitler</h4>
          <div class="pusula-table-wrapper">
            <table class="pusula-table" id="pusula-inst-table">
              <thead><tr><th>Vade</th><th>Tutar</th><th>Durum</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <div class="pusula-actions">
            <button id="btn-mark-paid" disabled>Ödendi İşaretle</button>
            <button id="btn-mark-unpaid" disabled>Ödenmedi İşaretle</button>
          </div>
        </div>
      </div>
    `;
    const printBtn = document.getElementById('btn-print-sale');
    if (printBtn) printBtn.addEventListener('click', printReceipt);
    const paidBtn = document.getElementById('btn-mark-paid');
    const unpaidBtn = document.getElementById('btn-mark-unpaid');
    if (paidBtn) paidBtn.addEventListener('click', () => toggleInstallmentPaid(true));
    if (unpaidBtn) unpaidBtn.addEventListener('click', () => toggleInstallmentPaid(false));
  }

  function updateDetail(cust) {
    const root = document.getElementById('pusula-detail-header');
    if (!root) return;
    ['id','name','phone','address'].forEach((field) => {
      const el = root.querySelector(`[data-field="${field}"]`);
      if (el) el.textContent = cust ? (cust[field] || '—') : '—';
    });
  }

  async function loadSales(customerId) {
    try {
      state.sales = await api(`/sales?customer_id=${customerId}&with=installments`);
      renderSalesTable(state.sales);
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
      state.sales = [];
      renderSalesTable([]);
    }
  }

  function renderSalesTable(rows) {
    const tbody = document.querySelector('#pusula-sales-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    state.currentSale = null;
    const printBtn = document.getElementById('btn-print-sale');
    if (printBtn) printBtn.disabled = true;
    rows.forEach((s, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${s.id}</td><td>${fromISO(s.date)}</td><td>${Number(s.total || 0).toFixed(2)}</td><td>${s.description || ''}</td>`;
      tr.addEventListener('click', () => {
        state.currentSale = s;
        renderInstallments(s.installments || []);
        const printBtn = document.getElementById('btn-print-sale');
        if (printBtn) printBtn.disabled = false;
      });
      tbody.appendChild(tr);
      if (idx === 0) {
        state.currentSale = s;
        renderInstallments(s.installments || []);
        const printBtn = document.getElementById('btn-print-sale');
        if (printBtn) printBtn.disabled = false;
      }
    });
    if (!rows.length) {
      renderInstallments([]);
    }
  }

  function renderInstallments(insts) {
    const tbody = document.querySelector('#pusula-inst-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    insts.forEach((i) => {
      const tr = document.createElement('tr');
      const paid = isPaid(i.paid);
      tr.innerHTML = `<td>${fromISO(i.due_date)}</td><td>${Number(i.amount || 0).toFixed(2)}</td><td>${paid ? 'Ödendi' : 'Ödenmedi'}</td>`;
      if (paid) tr.classList.add('paid');
      tr.addEventListener('click', () => {
        tbody.querySelectorAll('tr').forEach((row) => row.classList.remove('selected'));
        tr.classList.add('selected');
        tr.dataset.instId = i.id;
        tr.dataset.saleId = i.sale_id || (state.currentSale && state.currentSale.id);
        const btnPaid = document.getElementById('btn-mark-paid');
        const btnUnpaid = document.getElementById('btn-mark-unpaid');
        if (btnPaid && btnUnpaid) {
          btnPaid.disabled = false;
          btnUnpaid.disabled = false;
        }
      });
      tbody.appendChild(tr);
    });
    const btnPaid = document.getElementById('btn-mark-paid');
    const btnUnpaid = document.getElementById('btn-mark-unpaid');
    if (btnPaid && btnUnpaid) {
      const hasRows = insts.length > 0;
      btnPaid.disabled = !hasRows;
      btnUnpaid.disabled = !hasRows;
    }
  }

  async function toggleInstallmentPaid(paid) {
    const tbody = document.querySelector('#pusula-inst-table tbody');
    if (!tbody) return;
    const selectedRow = Array.from(tbody.querySelectorAll('tr')).find((r) => r.classList.contains('selected'));
    if (!selectedRow) return;
    const instId = selectedRow.dataset.instId;
    if (!instId) return;
    try {
      await api(`/installments/${instId}`, {
        method: 'PUT',
        body: JSON.stringify({ paid: paid ? 1 : 0 }),
      });
      setStatus('Taksit güncellendi.');
      if (state.selected) loadSales(state.selected.id);
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  function printReceipt() {
    if (!state.currentSale || !state.selected) return;
    const sale = state.currentSale;
    const cust = state.selected;
    const insts = sale.installments || [];
    const totalInst = insts.reduce((s, i) => s + Number(i.amount || 0), 0);
    const down = Math.max(0, Number(sale.total || 0) - totalInst);
    printReceiptDetailed(
      {
        id: sale.id,
        date: sale.date,
        total: Number(sale.total || 0),
        down,
        installments: insts,
      },
      cust
    );
  }

  function printReceiptDetailed(sale, cust) {
    if (!sale || !cust) return;
    const company = {
      name: 'ENES BEKO',
      address: 'KOZAN CD. PTT EVLERİ KAVŞAĞI NO: 689, ADANA',
      phone: 'Telefon: (0322) 329 92 32',
      web: 'Web: https://enesbeko.com',
      footerSub: 'ENES EFY KARDEŞLER',
    };

    const insts = (sale.installments || []).map((i) => ({ ...i, paid: isPaid(i.paid) ? 1 : 0 }));
    const todayISO = new Date().toISOString().slice(0, 10);
    const unpaid = insts.filter((i) => !isPaid(i.paid));
    const overdue = unpaid.filter((i) => i.due_date && i.due_date < todayISO);
    const upcoming = unpaid.filter((i) => i.due_date && i.due_date >= todayISO);

    const formatTL = (n) => `${Number(n || 0).toLocaleString('tr-TR', { minimumFractionDigits: 2 })} TL`;
    const fmtDate = (iso) => fromISOSlash(iso || '');
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const timeStr = `${hh}:${mm}`;
    const overdueTotal = overdue.reduce((s, i) => s + Number(i.amount || 0), 0);
    const totalInst = insts.reduce((s, i) => s + Number(i.amount || 0), 0);
    const down = Number(sale.down || 0);

    let html = `
      <html><head><title> </title>
      <style>
        @page { size: A4; margin: 0; }
        @media print {
          .no-print { display:none; }
          html, body { margin:0; padding:0; }
        }
        body { font-family: Arial, sans-serif; color:#000; margin:0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .receipt { padding: 14mm; }
        .no-print { font-size:12px; color:#444; margin:10px 0 14px; }
        .brand { text-align:center; }
        .brand .name { font-weight:700; font-size:18px; letter-spacing:1px; margin:0; }
        .brand .line { font-size:11px; margin:3px 0 0; }
        .rule { border-top:2px solid #000; margin:10px 0 12px; }
        .title { text-align:center; font-weight:700; font-size:14px; margin:0 0 10px; }
        .meta-row { display:flex; justify-content:space-between; font-size:12px; margin:6px 0 12px; }
        .info { font-size:12px; margin:8px 0 12px; }
        .info .row { display:flex; gap:10px; margin:4px 0; }
        .info .label { width:90px; }
        .box { border:1px solid #ddd; border-radius:4px; padding:10px 12px; font-size:12px; margin:10px 0 14px; }
        .box .line { margin:3px 0; }
        .cols { display:flex; gap:30px; }
        .col { flex:1; }
        .col h3 { font-size:12px; margin:0; font-weight:700; }
        .col .under { border-bottom:1px solid #ccc; margin:6px 0 8px; }
        .item { font-size:12px; margin:6px 0; }
        .money { color:#1a58d3; font-weight:700; }
        .totals { margin-top:16px; font-size:12px; }
        .totals .row { display:flex; justify-content:space-between; margin:6px 0; }
        .totals .grand { font-weight:700; border-top:2px solid #000; padding-top:8px; margin-top:8px; }
        .footer-rule { border-top:2px solid #000; margin:18px 0 10px; }
        .footer { text-align:center; font-size:11px; }
        .footer .thanks { margin:0 0 10px; }
        .footer .name { font-weight:700; letter-spacing:1px; margin:0; }
        .footer .sub { margin:4px 0 0; color:#444; }
      </style></head><body>
      <div class="receipt">
        <div class="no-print">Not: Yazdırma ekranında “Üstbilgi ve altbilgiler” seçeneğini kapatın.</div>
        <div class="brand">
          <p class="name">${company.name}</p>
          <p class="line">${company.address}</p>
          <p class="line">${company.phone} | ${company.web}</p>
        </div>
        <div class="rule"></div>
        <p class="title">Taksitli Alışveriş - Satış Makbuzu</p>
        <div class="meta-row">
          <div><strong>Tarih:</strong> ${fmtDate(sale.date)}</div>
          <div><strong>Saat:</strong> ${timeStr}</div>
        </div>
        <div class="info">
          <div class="row"><div class="label"><strong>Hesap No:</strong></div><div>${cust.id || ''}</div></div>
          <div class="row"><div class="label"><strong>Sayın:</strong></div><div>${cust.name || ''}</div></div>
          <div class="row"><div class="label"><strong>Adres:</strong></div><div>${cust.address || ''}</div></div>
        </div>
        <div class="box">
          <div class="line"><strong>${fmtDate(sale.date)}</strong> Tarihinde <span class="money">${formatTL(sale.total)}</span> Alışveriş Yapılıp</div>
          <div class="line"><span class="money">${formatTL(down)}</span> Peşinat Alınmıştır</div>
        </div>
        <div class="cols">
          <div class="col">
            <h3>Geciken Taksitler</h3>
            <div class="under"></div>`;
    if (!overdue.length) {
      html += `<div class="item">Yok</div>`;
    } else {
      overdue.forEach((i) => {
        html += `<div class="item">${fmtDate(i.due_date)} - <span class="money">${formatTL(i.amount)}</span></div>`;
      });
    }
    html += `
          </div>
          <div class="col">
            <h3>Yaklaşan Taksitler</h3>
            <div class="under"></div>`;
    upcoming.forEach((i) => {
      html += `<div class="item">${fmtDate(i.due_date)} - <span class="money">${formatTL(i.amount)}</span></div>`;
    });
    html += `
          </div>
        </div>
        <div class="totals">
          <div class="row"><div><strong>Geciken Toplam:</strong></div><div class="money">${formatTL(overdueTotal)}</div></div>
          <div class="row"><div><strong>Taksitler Toplamı:</strong></div><div class="money">${formatTL(totalInst)}</div></div>
          <div class="row grand"><div><strong>Genel Toplam:</strong></div><div class="money">${formatTL(sale.total)}</div></div>
        </div>
        <div class="footer-rule"></div>
        <div class="footer">
          <p class="thanks">Mağazamızdan yapmış olduğunuz alış verişten dolayı teşekkür ederiz</p>
          <p class="name">${company.name}</p>
          <p class="sub">${company.footerSub}</p>
        </div>
      </div>
      </body></html>`;
    const w = window.open('', '_blank');
    if (w) {
      try { w.document.title = ''; } catch (e) { /* ignore */ }
      w.document.write(html);
      w.document.close();
      w.focus();
      w.print();
    }
  }

  // ------------------- Report -------------------
  function renderReportTab() {
    const root = document.getElementById('pusula-tab-report');
    if (!root) return;
    const today = todayStr();
    root.innerHTML = `
      <div class="pusula-grid">
        <label class="pusula-input"><span>Başlangıç</span><input type="text" id="rep-start" value="${today}"></label>
        <label class="pusula-input"><span>Bitiş</span><input type="text" id="rep-end" value="${today}"></label>
        <div class="pusula-actions"><button id="rep-run">Raporla</button></div>
      </div>
      <div class="pusula-summary"><span id="rep-total">0,00</span> ₺ — <span id="rep-count">0</span> satış</div>
      <table class="pusula-table" id="rep-table">
        <thead><tr><th>No</th><th>Müşteri</th><th>Tarih</th><th>Tutar</th><th>Açıklama</th></tr></thead>
        <tbody></tbody>
      </table>
    `;
    root.querySelector('#rep-run').addEventListener('click', loadReport);
  }

  async function loadReport() {
    const start = document.getElementById('rep-start').value || todayStr();
    const end = document.getElementById('rep-end').value || todayStr();
    try {
      const rows = await api(`/sales?start=${toISO(start)}&end=${toISO(end)}`);
      const total = rows.reduce((sum, s) => sum + Number(s.total || 0), 0);
      document.getElementById('rep-total').textContent = total.toFixed(2);
      document.getElementById('rep-count').textContent = rows.length;
      const tbody = document.querySelector('#rep-table tbody');
      tbody.innerHTML = '';
      rows.forEach((s) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${s.id}</td><td>${s.customer_name || ''}</td><td>${fromISO(s.date)}</td><td>${Number(s.total || 0).toFixed(2)}</td><td>${s.description || ''}</td>`;
        tbody.appendChild(tr);
      });
      setStatus('Rapor yüklendi.');
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  // ------------------- Settings -------------------
  function renderSettingsTab() {
    const root = document.getElementById('pusula-tab-settings');
    if (!root) return;
    root.innerHTML = `
      <p>Bu sayfa, eklentide kayıtlı API anahtarını kullanır.</p>
      <p><strong>API Uç Noktası:</strong> ${apiBase}</p>
      <p>Pusula Kullanıcısı rolüne sahip kullanıcılar bu arayüze erişebilir.</p>
    `;
  }

  // ------------------- Init -------------------
  function init() {
    renderTabs();
    renderSearchTab();
    renderAddTab();
    renderSaleTab();
    renderDetailTab();
    renderReportTab();
    loadCustomers();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
