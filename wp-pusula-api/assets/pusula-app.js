(() => {
  const state = {
    customers: [],
    customerBase: [],
    customerLoadSeq: 0,
    isLoadingCustomers: false,
    isSavingCustomer: false,
    isSavingSale: false,
    autoRefreshHandle: null,
    autoRefreshMs: 15000,
    selected: null,
    pendingCustomerId: null,
    currentSaleExplicit: false,
    sales: [],
    reportSales: [],
    expectedPayments: [],
    currentExpected: null,
  };

  const apiBase = (window.PusulaApp && PusulaApp.apiBase) || '';
  const wpNonce = (window.PusulaApp && PusulaApp.nonce) || '';

  const todayStr = () => {
    const d = new Date();
    const pad = (n) => (n < 10 ? `0${n}` : n);
    return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`;
  };
  const toISO = (value) => {
    const input = String(value || '').trim();
    if (!input) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(input)) return input;
    let m = input.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    m = input.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    return '';
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

  function parseISODate(iso) {
    const s = String(iso || '').trim();
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const d = Number(m[3]);
    if (!y || mo < 1 || mo > 12 || d < 1 || d > 31) return null;
    return new Date(y, mo - 1, d);
  }

  function formatISODate(date) {
    const d = date instanceof Date ? date : new Date(date);
    if (!d || Number.isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  const formatMoney = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '0,00₺';
    return `${num.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}₺`;
  };

  const defaultDueDay = () => Math.min(new Date().getDate(), 28);

  const isPaid = (val) => Number(val) === 1;
  const hasUnpaidInstallments = (sale) => {
    const insts = sale && sale.installments;
    if (!Array.isArray(insts) || !insts.length) return false;
    return insts.some((inst) => !isPaid(inst.paid));
  };

  function ensureLayoutFits() {
    const app = document.getElementById('pusula-lite-app');
    if (!app) return;
    const needsScroll = app.scrollHeight > app.clientHeight + 1;
    app.classList.toggle('allow-scroll', needsScroll);
  }

  function setCustomersLoading(isLoading) {
    const wrapper = document.querySelector('#pusula-tab-search .pusula-table-wrapper');
    if (!wrapper) return;
    wrapper.classList.toggle('loading', Boolean(isLoading));
  }

  function setInstallmentsLoading(isLoading) {
    const table = document.getElementById('pusula-inst-table');
    if (!table) return;
    const wrapper = table.closest('.pusula-table-wrapper');
    if (!wrapper) return;
    wrapper.classList.toggle('loading', Boolean(isLoading));
  }

  function setExpectedLoading(isLoading) {
    const table = document.getElementById('exp-table');
    if (!table) return;
    const wrapper = table.closest('.pusula-table-wrapper');
    if (!wrapper) return;
    wrapper.classList.toggle('loading', Boolean(isLoading));
  }

  function getCustomerSearchFields() {
    const root = document.getElementById('pusula-tab-search');
    if (!root) return {};
    const fields = {};
    root.querySelectorAll('input[data-field]').forEach((input) => {
      const val = input.value.trim();
      if (val) fields[input.getAttribute('data-field')] = val;
    });
    return fields;
  }

  function normalizeText(s) {
    return String(s || '').toLowerCase();
  }

  function truncateDescription(text, maxLen = 70) {
    const raw = String(text || '').replace(/\r\n/g, '\n');
    const firstLine = raw.split('\n')[0] || '';
    const cleaned = firstLine.trim();
    if (!cleaned) return '';
    if (cleaned.length <= maxLen) return cleaned;
    return `${cleaned.slice(0, Math.max(0, maxLen - 1))}…`;
  }

  function filterCustomers(rows, fields) {
    const id = String(fields.id || '').trim();
    const name = normalizeText(fields.name);
    const phone = normalizeText(fields.phone);
    const address = normalizeText(fields.address);
    if (!id && !name && !phone && !address) return rows;
    return (rows || []).filter((c) => {
      if (id && !String(c.id || '').includes(id)) return false;
      if (name && !normalizeText(c.name).includes(name)) return false;
      if (phone && !normalizeText(c.phone).includes(phone)) return false;
      if (address) {
        const addr = normalizeText(c.address);
        const work = normalizeText(c.work_address);
        if (!addr.includes(address) && !work.includes(address)) return false;
      }
      return true;
    });
  }

  function applyCustomerFilterLocal() {
    const fields = getCustomerSearchFields();
    const base = state.customerBase && state.customerBase.length ? state.customerBase : state.customers;
    renderTable(filterCustomers(base || [], fields));
  }

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

  function activateTab(tab) {
    const tabName = String(tab || '');
    document.querySelectorAll('.pusula-tabs button').forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-tab') === tabName);
    });
    document.querySelectorAll('.pusula-tab-content').forEach((c) => (c.style.display = 'none'));
    const target = document.getElementById(`pusula-tab-${tabName}`);
    if (target) target.style.display = '';

    if (tabName === 'add') {
      if (state.selected) {
        if (!isAddFormDirty()) fillCustomerForm(state.selected);
      } else if (!isAddFormDirty()) {
        fillCustomerForm();
      }
    }
    if (tabName === 'sale') {
      if (state.selected) fillSaleCustomer(state.selected);
      else syncSaleCustomerFromPending();
    }
    if (tabName === 'detail') {
      if (state.selected) {
        updateDetail(state.selected);
        loadSales(state.selected.id, state.currentSale ? state.currentSale.id : null);
      } else {
        syncDetailFromPending();
      }
    }
    if (tabName === 'report') {
      loadReport();
    }
    if (tabName === 'expected') {
      loadExpectedPayments();
    }
    setTimeout(ensureLayoutFits, 0);
  }

  function renderTabs() {
    document.querySelectorAll('.pusula-tabs button').forEach((btn) => {
      btn.addEventListener('click', () => activateTab(btn.getAttribute('data-tab')));
    });
  }

  function getActiveTabName() {
    const btn = document.querySelector('.pusula-tabs button.active');
    return btn ? btn.getAttribute('data-tab') : 'search';
  }

  function isUserInteracting() {
    const app = document.getElementById('pusula-lite-app');
    if (!app) return false;
    const active = document.activeElement;
    if (!active || !app.contains(active)) return false;
    return ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName);
  }

  function isAddFormDirty() {
    const ids = [
      'cust-name',
      'cust-phone',
      'cust-address',
      'cust-work',
      'cust-notes',
      'c1-name',
      'c1-phone',
      'c1-home',
      'c1-work',
      'c2-name',
      'c2-phone',
      'c2-home',
      'c2-work',
    ];
    return ids.some((id) => {
      const el = document.getElementById(id);
      if (!el) return false;
      return String(el.value || '').trim().length > 0;
    });
  }

  async function autoRefreshTick() {
    if (document.hidden) return;
    if (state.isSavingCustomer || state.isSavingSale || state.isLoadingCustomers) return;
    if (document.querySelector('.pusula-modal-backdrop')) return;
    if (isUserInteracting()) return;

    const tab = getActiveTabName();
    try {
      await loadCustomers({ silent: true, showLoading: false });
      if (tab === 'detail' && state.selected) {
        await loadSales(state.selected.id, state.currentSale ? state.currentSale.id : null);
      }
      if (tab === 'report') {
        await loadReport({ silent: true });
      }
      if (tab === 'expected') {
        await loadExpectedPayments({ silent: true, showLoading: false });
      }
      if (tab === 'add' && !state.selected && !isAddFormDirty()) {
        const localNext = nextCustomerId();
        refreshNewCustomerIdFromServer(localNext);
      }
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  function startAutoRefresh() {
    if (state.autoRefreshHandle) clearInterval(state.autoRefreshHandle);
    state.autoRefreshHandle = setInterval(autoRefreshTick, state.autoRefreshMs);
  }

  function openTextModal({
    title,
    hideTitle = false,
    infoRows = [],
    textareaLabel,
    value,
    saveLabel,
    onSave,
    deleteLabel,
    onDelete,
  }) {
    const existing = document.querySelector('.pusula-modal-backdrop');
    if (existing) existing.remove();

    const hasInfo = Array.isArray(infoRows) && infoRows.length > 0;
    const hasDelete = typeof onDelete === 'function';
	    const showTitle = !hideTitle && title;
	    const backdrop = document.createElement('div');
	    backdrop.className = 'pusula-modal-backdrop';
	    backdrop.innerHTML = `
	      <div class="pusula-modal" role="dialog" aria-modal="true">
	        <div class="pusula-modal-header ${showTitle ? '' : 'no-title'}">
	          ${showTitle ? `<div class="pusula-modal-title">${title}</div>` : ''}
	          <button class="pusula-modal-close" type="button" data-action="close" aria-label="Kapat">✕</button>
	        </div>
	        <div class="pusula-modal-body">
	          <div class="pusula-modal-main ${hasInfo ? 'two-col' : 'one-col'}">
	            ${hasInfo ? '<div class="pusula-modal-info"></div>' : ''}
	            <div class="pusula-modal-editor">
	              ${textareaLabel ? `<div class="pusula-modal-label">${textareaLabel}</div>` : ''}
	              <textarea class="pusula-modal-textarea" rows="10"></textarea>
	              <div class="pusula-modal-status" aria-live="polite"></div>
	            </div>
	          </div>
	        </div>
	        <div class="pusula-modal-actions">
	          ${hasDelete ? `<button type="button" class="pusula-modal-btn danger" data-action="delete">${deleteLabel || 'SİL'}</button>` : ''}
	          <button type="button" class="pusula-modal-btn" data-action="cancel">VAZGEÇ</button>
	          <button type="button" class="pusula-modal-btn primary" data-action="save">${saveLabel || 'KAYDET'}</button>
	        </div>
	      </div>
	    `;

    document.body.appendChild(backdrop);

    const modal = backdrop.querySelector('.pusula-modal');
    const infoEl = backdrop.querySelector('.pusula-modal-info');
    const textarea = backdrop.querySelector('.pusula-modal-textarea');
    const statusEl = backdrop.querySelector('.pusula-modal-status');
    const deleteBtn = backdrop.querySelector('[data-action="delete"]');
    const saveBtn = backdrop.querySelector('[data-action="save"]');
    const cancelBtn = backdrop.querySelector('[data-action="cancel"]');
    const closeBtn = backdrop.querySelector('[data-action="close"]');

    if (infoEl && hasInfo) {
      infoRows.forEach((row) => {
        const label = row && row.label ? String(row.label) : '';
        const val = row && row.value !== undefined && row.value !== null ? String(row.value) : '';
        if (!label && !val) return;
        const rowEl = document.createElement('div');
        rowEl.className = 'pusula-modal-info-row';
        const labelEl = document.createElement('div');
        labelEl.className = 'pusula-modal-info-label';
        labelEl.textContent = label;
        const valueEl = document.createElement('div');
        valueEl.className = 'pusula-modal-info-value';
        valueEl.textContent = val;
        rowEl.appendChild(labelEl);
        rowEl.appendChild(valueEl);
        infoEl.appendChild(rowEl);
      });
    }

    if (textarea) {
      textarea.value = value || '';
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }

    const close = () => {
      document.removeEventListener('keydown', onKeyDown);
      backdrop.remove();
      setTimeout(ensureLayoutFits, 0);
    };

    const setModalStatus = (msg, isError = false) => {
      if (!statusEl) return;
      statusEl.textContent = msg || '';
      statusEl.style.color = isError ? '#f0a7a7' : '#88b7c9';
    };

    const onKeyDown = (e) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKeyDown);

    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) close();
    });
    if (cancelBtn) cancelBtn.addEventListener('click', close);
    if (closeBtn) closeBtn.addEventListener('click', close);

    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        if (!onSave) return close();
        const nextVal = textarea ? textarea.value : '';
        if (deleteBtn) deleteBtn.disabled = true;
        saveBtn.disabled = true;
        if (cancelBtn) cancelBtn.disabled = true;
        if (closeBtn) closeBtn.disabled = true;
        setModalStatus('Kaydediliyor...');
        try {
          await onSave(nextVal);
          close();
        } catch (err) {
          setModalStatus(`Hata: ${trErrorMessage(err.message)}`, true);
          if (deleteBtn) deleteBtn.disabled = false;
          saveBtn.disabled = false;
          if (cancelBtn) cancelBtn.disabled = false;
          if (closeBtn) closeBtn.disabled = false;
        }
      });
    }

    if (deleteBtn) {
      deleteBtn.addEventListener('click', async () => {
        if (!onDelete) return close();
        deleteBtn.disabled = true;
        if (saveBtn) saveBtn.disabled = true;
        if (cancelBtn) cancelBtn.disabled = true;
        if (closeBtn) closeBtn.disabled = true;
        setModalStatus('Siliniyor...');
        try {
          const deleted = await onDelete();
          if (deleted === false) {
            setModalStatus('');
            deleteBtn.disabled = false;
            if (saveBtn) saveBtn.disabled = false;
            if (cancelBtn) cancelBtn.disabled = false;
            if (closeBtn) closeBtn.disabled = false;
            return;
          }
          close();
        } catch (err) {
          setModalStatus(`Hata: ${trErrorMessage(err.message)}`, true);
          deleteBtn.disabled = false;
          if (saveBtn) saveBtn.disabled = false;
          if (cancelBtn) cancelBtn.disabled = false;
          if (closeBtn) closeBtn.disabled = false;
        }
      });
    }

    if (modal) modal.addEventListener('click', (e) => e.stopPropagation());
  }

  function openSaleDescriptionEditor(sale, { customer, onUpdated } = {}) {
    if (!sale || !sale.id) return;
    const custId = customer && customer.id ? customer.id : sale.customer_id;
    const custName = customer && customer.name ? customer.name : sale.customer_name;
    const infoRows = [
      { label: 'Satış No', value: sale.id },
      { label: 'Tarih', value: fromISO(sale.date) },
      { label: 'Tutar', value: formatMoney(sale.total || 0) },
      { label: 'Müşteri No', value: custId || '' },
      { label: 'Adı Soyadı', value: custName || '' },
    ];
    openTextModal({
      hideTitle: true,
      infoRows,
      textareaLabel: 'Açıklama',
      value: sale.description || '',
      saveLabel: 'KAYDET',
      deleteLabel: 'SİL',
      onDelete: () => deleteSale(sale),
      onSave: async (nextText) => {
        const next = String(nextText ?? '');
        await api(`/sales/${sale.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            date: sale.date,
            total: Number(sale.total || 0),
            description: next,
          }),
        });
        sale.description = next;
        setStatus('Açıklama güncellendi.');
        if (onUpdated) onUpdated(next);
      },
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
          <thead><tr><th>No</th><th>Kayıt Tarihi</th><th>İsim</th><th>Telefon</th><th>Adres</th></tr></thead>
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
    const debouncedRemote = debounce(loadCustomers, 150);
    root.querySelectorAll('input[data-field]').forEach((inp) => {
      inp.addEventListener('input', () => {
        applyCustomerFilterLocal();
        setCustomersLoading(true);
        debouncedRemote();
      });
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
    const list = Array.isArray(rows) ? rows : [];
    list.forEach((r) => {
      const tr = document.createElement('tr');
      const reg = r.registration_date ? fromISO(r.registration_date) : '';
      tr.innerHTML = `<td>${r.id}</td><td>${reg}</td><td>${r.name || ''}</td><td>${r.phone || ''}</td><td>${r.address || ''}</td>`;
      if (Number(r.late_unpaid) === 1) tr.classList.add('late');
      const isSelected = state.selected && String(state.selected.id) === String(r.id);
      tr.addEventListener('click', () => {
        state.selected = r;
        state.pendingCustomerId = null;
        fillSaleCustomer(r);
        tbody.querySelectorAll('tr').forEach((row) => row.classList.remove('selected'));
        tr.classList.add('selected');
        enableNav(true);
      });
      tr.addEventListener('dblclick', () => {
        state.selected = r;
        state.pendingCustomerId = null;
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
        state.pendingCustomerId = null;
        hasSelection = true;
      }
      tbody.appendChild(tr);
    });
    if (!list.length) {
      const fields = getCustomerSearchFields();
      const hasFilters = Boolean(fields.id || fields.name || fields.phone || fields.address);
      const msg = hasFilters ? 'Arama kriterlerine uygun müşteri bulunamadı.' : 'Henüz müşteri kaydı yok.';
      const tr = document.createElement('tr');
      tr.className = 'pusula-empty-row';
      tr.innerHTML = `<td colspan="5" class="pusula-empty-cell">${msg}</td>`;
      tbody.appendChild(tr);
    }

    if (!list.length || !hasSelection) {
      enableNav(false);
    }
  }

  async function loadCustomers({ silent = false, showLoading = true } = {}) {
    const fields = getCustomerSearchFields();
    const seq = ++state.customerLoadSeq;
    state.isLoadingCustomers = true;
    if (showLoading) setCustomersLoading(true);
    try {
      const query = new URLSearchParams({ limit: 500, with: 'late_unpaid' });
      ['id','name','phone','address'].forEach((f) => {
        if (fields[f]) query.append(f, fields[f]);
      });
      const rows = await api(`/customers?${query.toString()}`);
      if (seq !== state.customerLoadSeq) return;
      state.customers = rows || [];
      if (!fields.id && !fields.name && !fields.phone && !fields.address) {
        state.customerBase = state.customers;
      }
      renderTable(state.customers);
      if (!silent) setStatus(`${state.customers.length} kayıt yüklendi.`);
      if (getActiveTabName() === 'add' && !state.selected && !isAddFormDirty()) {
        refreshNewCustomerIdFromServer(nextCustomerId());
      }
    } catch (err) {
      if (seq !== state.customerLoadSeq) return;
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
      enableNav(false);
    } finally {
      if (seq === state.customerLoadSeq) {
        state.isLoadingCustomers = false;
        if (showLoading) setCustomersLoading(false);
      }
    }
    setTimeout(ensureLayoutFits, 0);
  }

  async function fetchCustomerById(customerId) {
    const id = String(customerId || '').trim();
    if (!/^\d+$/.test(id)) return null;
    const local = state.customers.find((c) => String(c.id) === id);
    if (local) return local;
    const rows = await api(`/customers?id=${encodeURIComponent(id)}&limit=1`);
    if (rows && rows[0]) return rows[0];
    return null;
  }

  async function fetchSalesForCustomer(customerId) {
    const id = Number(customerId);
    if (!Number.isFinite(id) || id < 1) return [];
    const rows = await api(`/sales?customer_id=${encodeURIComponent(id)}&with=installments`);
    return rows || [];
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
    if (!window.confirm('Dikkat: Bu işlem geri alınamaz. Müşteriye ait tüm satış ve taksit kayıtları silinecek. Devam etmek istiyor musunuz?')) return;
    try {
      await api(`/customers/${state.selected.id}`, { method: 'DELETE' });
      setStatus('Müşteri silindi.');
      state.selected = null;
      state.pendingCustomerId = null;
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
        <button id="cust-save">KAYDET</button>
        <button id="cust-clear">TEMİZLE</button>
      </div>
    `;
    root.querySelector('#cust-save').addEventListener('click', saveCustomer);
    root.querySelector('#cust-clear').addEventListener('click', () => {
      state.selected = null;
      state.pendingCustomerId = null;
      fillCustomerForm();
    });
    const custIdInput = root.querySelector('#cust-id');
    if (custIdInput) {
      const syncPending = () => {
        if (state.selected) return;
        setPendingCustomerId(custIdInput.value.trim());
      };
      custIdInput.addEventListener('input', syncPending);
      custIdInput.addEventListener('blur', syncPending);
    }
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
      if (!el) return;
      if ('value' in el) el.value = val || '';
      else el.textContent = val || '';
    };
    if (!cust) {
      state.selected = null;
      ['cust-id','cust-name','cust-phone','cust-address','cust-work','cust-notes','c1-name','c1-phone','c1-home','c1-work','c2-name','c2-phone','c2-home','c2-work'].forEach((id) => set(id, ''));
      const localNext = nextCustomerId();
      set('cust-id', String(localNext));
      setPendingCustomerId(localNext);
      set('cust-date-label', todayStr());
      set('cust-date-hidden', todayStr());
      refreshNewCustomerIdFromServer(localNext);
      return;
    }
    state.selected = cust;
    state.pendingCustomerId = null;
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
    const base = state.customerBase && state.customerBase.length ? state.customerBase : state.customers;
    if (!base || !base.length) return 1;
    const ids = new Set(
      base
        .map((c) => parseInt(c.id, 10))
        .filter((n) => Number.isFinite(n) && n > 0)
    );
    let nextId = 1;
    while (ids.has(nextId)) nextId += 1;
    return nextId;
  }

  function setPendingCustomerId(nextId) {
    if (state.selected) return;
    const val = String(nextId || '').trim();
    state.pendingCustomerId = val || null;
    syncSaleCustomerFromPending();
    syncDetailFromPending();
  }

  function syncSaleCustomerFromPending() {
    if (state.selected) return;
    const pending = state.pendingCustomerId;
    if (!pending) return;
    const idEl = document.getElementById('sale-cust-id');
    if (idEl) idEl.value = pending;
    const nameEl = document.getElementById('sale-cust-name');
    if (nameEl) nameEl.value = '';
  }

  function syncDetailFromPending() {
    if (state.selected) return;
    const pending = state.pendingCustomerId;
    if (!pending) return;
    updateDetail({ id: pending });
    if (getActiveTabName() === 'detail') {
      renderSalesTable([], { selectedSaleId: null });
    }
  }

  async function refreshNewCustomerIdFromServer(expectedId) {
    const idEl = document.getElementById('cust-id');
    if (!idEl) return;
    const before = idEl.value.trim();
    if (before && expectedId && before !== String(expectedId)) return;
    try {
      const res = await api('/customers/next-id');
      const nextId = Number(res && res.next_id);
      if (!Number.isFinite(nextId) || nextId < 1) return;
      const nowEl = document.getElementById('cust-id');
      if (!nowEl) return;
      if (nowEl.value.trim() !== before) return;
      nowEl.value = String(nextId);
      setPendingCustomerId(nextId);
    } catch (e) {
      // ignore (fallback already set)
    }
  }

  async function saveCustomer() {
    const addRoot = document.getElementById('pusula-tab-add');
    const saveBtn = document.getElementById('cust-save');
    const clearBtn = document.getElementById('cust-clear');
    const tabButtons = Array.from(document.querySelectorAll('.pusula-tabs button'));
    const prevSaveHtml = saveBtn ? saveBtn.innerHTML : '';

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
    try {
      state.isSavingCustomer = true;
      setStatus('Kaydediliyor...');
      if (addRoot) {
        addRoot.querySelectorAll('input, textarea, button').forEach((el) => {
          if (el.type === 'hidden') return;
          el.disabled = true;
        });
      }
      tabButtons.forEach((b) => { b.disabled = true; });
      if (saveBtn) saveBtn.innerHTML = `<span class="pusula-spinner" aria-hidden="true"></span>KAYDEDİLİYOR...`;
      if (clearBtn) clearBtn.disabled = true;

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
      if (state.customerBase && state.customerBase.length) {
        const baseIdx = state.customerBase.findIndex((c) => String(c.id) === String(newCust.id));
        if (baseIdx >= 0) state.customerBase[baseIdx] = newCust;
        else state.customerBase.unshift(newCust);
      }
      state.selected = newCust;
      state.pendingCustomerId = null;
      renderTable(state.customers);
      enableNav(true);
      updateDetail(newCust);
      fillCustomerForm(newCust);
      resetSaleForm();
      fillSaleCustomer(newCust);
      activateTab('sale');
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    } finally {
      state.isSavingCustomer = false;
      if (saveBtn) saveBtn.innerHTML = prevSaveHtml || 'KAYDET';
      if (addRoot) {
        addRoot.querySelectorAll('input, textarea, button').forEach((el) => {
          if (el.type === 'hidden') return;
          el.disabled = false;
        });
      }
      tabButtons.forEach((b) => { b.disabled = false; });
      setTimeout(ensureLayoutFits, 0);
    }
  }

  // ------------------- Sale -------------------
  function resetSaleForm() {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val;
    };
    setVal('sale-date', todayStr());
    setVal('sale-total', '');
    setVal('sale-down', '0');
    setVal('sale-n', '1');
    setVal('sale-due', String(defaultDueDay()));
    setVal('sale-desc', '');
    updateSalePreview();
  }

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
        <button id="sale-save">KAYDET</button>
        <button id="sale-clear">TEMİZLE</button>
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
    const custIdEl = document.getElementById('sale-cust-id');
    if (custIdEl) {
      const debouncedLookup = debounce(async () => {
        const id = custIdEl.value.trim();
        const nameEl = document.getElementById('sale-cust-name');
        if (!id) {
          if (nameEl) nameEl.value = '';
          return;
        }
        const cust = await fetchCustomerById(id);
        if (cust) {
          state.selected = cust;
          state.pendingCustomerId = null;
          fillSaleCustomer(cust);
        } else if (nameEl) {
          nameEl.value = '';
        }
      }, 200);
      custIdEl.addEventListener('input', debouncedLookup);
      custIdEl.addEventListener('blur', debouncedLookup);
    }
    updateSalePreview();
    syncSaleCustomerFromPending();
    setTimeout(ensureLayoutFits, 0);
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
    if (!state.selected || String(state.selected.id) !== String(custId)) {
      const cust = await fetchCustomerById(custId);
      if (!cust) {
        setStatus('Hata: Müşteri bulunamadı.', true);
        return;
      }
      state.selected = cust;
      state.pendingCustomerId = null;
      fillSaleCustomer(cust);
    }
	    const total = parseFloat(document.getElementById('sale-total').value);
	    const downRaw = parseFloat(document.getElementById('sale-down').value || '0');
	    const down = Number.isFinite(downRaw) ? Math.max(0, downRaw) : 0;
	    const nInstRaw = parseInt(document.getElementById('sale-n').value || '1', 10);
	    const dueDay = parseInt(document.getElementById('sale-due').value || '1', 10);
	    const totalCents = Math.round(Math.max(0, total) * 100);
	    const downCents = Math.round(Math.max(0, down) * 100);
	    const isFullyPaid = totalCents > 0 && downCents >= totalCents;
	    const nInst = isFullyPaid ? 0 : nInstRaw;
	    const effectiveDown = isFullyPaid ? total : down;
	    if (!total || total <= 0 || (!isFullyPaid && (nInst < 1 || dueDay < 1 || dueDay > 28))) {
	      setStatus('Satış alanlarını kontrol edin.', true);
	      return;
	    }
	    const saleDateISO = toISO(document.getElementById('sale-date').value || todayStr());
	    const saleBase = parseISODate(saleDateISO);
    if (!saleBase) {
      setStatus('Satış tarihi geçersiz. (GG-AA-YYYY)', true);
      return;
    }
    const desc = document.getElementById('sale-desc').value.trim();
    try {
      state.isSavingSale = true;
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
	      const instCalls = [];
	      const instList = [];
	      const remaining = Math.max(0, total - effectiveDown);
	      if (nInst > 0 && remaining > 0) {
	        const instAmt = Math.round((remaining / nInst) * 100) / 100;
	        for (let i = 1; i <= nInst; i++) {
	          const d = new Date(saleBase.getFullYear(), saleBase.getMonth() + i, 1);
	          d.setDate(Math.min(dueDay, 28));
	          const dueIso = formatISODate(d);
	          const inst = {
	            sale_id: saleId,
	            due_date: dueIso,
	            amount: instAmt,
	            paid: 0,
	          };
	          instList.push(inst);
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
	              if (instRes && instRes.id) inst.id = instRes.id;
	              return instRes;
	            })
	          );
	        }
	        await Promise.all(instCalls);
	      }
	      setStatus(nInst > 0 ? 'Satış ve taksitler kaydedildi.' : 'Satış kaydedildi.');
      const newSale = {
        id: saleId,
        customer_id: Number(custId),
        customer_name: (state.selected && state.selected.name) || '',
        date: saleDateISO,
        total,
        description: desc,
        installments: instList,
      };
      const withoutDup = (state.sales || []).filter((s) => String(s.id) !== String(saleId));
      state.sales = [newSale, ...withoutDup].sort((a, b) => {
        const da = String(a.date || '');
        const db = String(b.date || '');
        if (da !== db) return db.localeCompare(da);
        return Number(b.id || 0) - Number(a.id || 0);
      });
      updateDetail(state.selected);
      renderSalesTable(state.sales, { selectedSaleId: saleId });
      activateTab('detail');
      if (state.selected) loadSales(state.selected.id, saleId);
      fillSaleCustomer(state.selected);
      updateSalePreview();
	      const saleData = {
	        id: saleId,
	        date: saleDateISO,
	        total,
	        description: desc,
	        down: effectiveDown,
	        installments: instList,
	      };
      if (window.confirm('Satış makbuzu yazdırılsın mı?')) {
        printReceiptDetailed(saleData, state.selected || { id: custId });
      }
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    } finally {
      state.isSavingSale = false;
    }
    setTimeout(ensureLayoutFits, 0);
  }

  function updateSalePreview() {
    const totalEl = document.getElementById('sale-total');
    const downEl = document.getElementById('sale-down');
    const nEl = document.getElementById('sale-n');
    const dueEl = document.getElementById('sale-due');

    const total = parseFloat(totalEl?.value || '0');
    const down = parseFloat(downEl?.value || '0');
    const totalCents = Math.round(Math.max(0, total) * 100);
    const downCents = Math.round(Math.max(0, down) * 100);
    const isFullyPaid = totalCents > 0 && downCents >= totalCents;

    if (nEl) {
      if (isFullyPaid) {
        if (!nEl.disabled) nEl.dataset.prevValue = nEl.value;
        nEl.value = '0';
        nEl.disabled = true;
      } else if (nEl.disabled) {
        nEl.disabled = false;
        if (String(nEl.value) === '0') {
          const prev = nEl.dataset.prevValue;
          nEl.value = prev && prev !== '0' ? prev : '1';
        }
      }
    }

    if (dueEl) dueEl.disabled = isFullyPaid;

    const nInst = parseInt(nEl?.value || '1', 10);
    const dueDay = parseInt(dueEl?.value || '1', 10);
    const saleDate = toISO(document.getElementById('sale-date')?.value || todayStr());
    const base = parseISODate(saleDate);
    const remainingCents = isFullyPaid ? 0 : Math.max(0, totalCents - downCents);
    const remain = remainingCents / 100;
    const hasInstallments = !isFullyPaid && nInst > 0 && remainingCents > 0;
    const per = hasInstallments ? (remain / nInst) : 0;
    const amtEl = document.getElementById('sale-preview-amt');
    const dateEl = document.getElementById('sale-preview-date');
    if (amtEl) amtEl.textContent = hasInstallments && isFinite(per) ? formatMoney(per) : '—';
    if (dateEl) {
      if (!hasInstallments || !base || !isFinite(dueDay)) {
        dateEl.textContent = '—';
      } else {
        const d = new Date(base.getFullYear(), base.getMonth() + nInst, 1);
        d.setDate(Math.min(dueDay, 28));
        dateEl.textContent = fromISO(formatISODate(d));
      }
    }
  }

  // ------------------- Detail -------------------
  function renderDetailTab() {
    const root = document.getElementById('pusula-tab-detail');
    if (!root) return;
    root.innerHTML = `
      <div id="pusula-detail-summary" class="detail-summary">
        <div class="detail-item">
          <span class="detail-label">No:</span>
          <span class="detail-value" data-field="id">-</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">İsim:</span>
          <span class="detail-value" data-field="name">-</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Telefon:</span>
          <span class="detail-value" data-field="phone">-</span>
        </div>
        <div class="detail-item detail-item-wide">
          <span class="detail-label">Adres:</span>
          <span class="detail-value" data-field="address">-</span>
        </div>
      </div>
      <div class="detail-stack">
        <div class="detail-section">
          <div class="detail-section-header">
            <div class="detail-section-title">Satışlar</div>
            <div class="pusula-actions detail-actions">
              <button id="btn-print-sale" disabled>MAKBUZ YAZDIR</button>
              <button id="btn-edit-sale" disabled>DÜZELT</button>
              <button id="btn-delete-sale" disabled>SİL</button>
            </div>
          </div>
          <div class="pusula-table-wrapper">
            <table class="pusula-table" id="pusula-sales-table">
              <thead><tr><th>No</th><th>Tarih</th><th>Tutar</th><th>Açıklama</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-section-header">
            <div class="detail-section-title">Taksitler</div>
            <div class="pusula-actions detail-actions">
              <button id="btn-mark-paid" disabled>ÖDENDİ İŞARETLE</button>
              <button id="btn-mark-unpaid" disabled>ÖDENMEDİ İŞARETLE</button>
              <button id="btn-print-inst" disabled>Makbuz Yazdır</button>
            </div>
          </div>
          <div class="pusula-table-wrapper">
            <table class="pusula-table" id="pusula-inst-table">
              <thead><tr><th>Vade</th><th>Tutar</th><th>Durum</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
      </div>
    `;
    const editBtn = document.getElementById('btn-edit-sale');
    if (editBtn) {
      editBtn.addEventListener('click', () => {
        if (!state.currentSale) return;
        openSaleDescriptionEditor(state.currentSale, {
          customer: state.selected,
          onUpdated: () => renderSalesTable(state.sales || [], { selectedSaleId: state.currentSale.id }),
        });
      });
    }
    const salePrintBtn = document.getElementById('btn-print-sale');
    if (salePrintBtn) salePrintBtn.addEventListener('click', printReceipt);
    const deleteBtn = document.getElementById('btn-delete-sale');
    if (deleteBtn) deleteBtn.addEventListener('click', () => deleteSale(state.currentSale));
    const paidBtn = document.getElementById('btn-mark-paid');
    const unpaidBtn = document.getElementById('btn-mark-unpaid');
    if (paidBtn) paidBtn.addEventListener('click', () => toggleInstallmentPaid(true));
    if (unpaidBtn) unpaidBtn.addEventListener('click', () => toggleInstallmentPaid(false));
    const instPrintBtn = document.getElementById('btn-print-inst');
    if (instPrintBtn) instPrintBtn.addEventListener('click', printSelectedInstallmentReceipt);
    setTimeout(ensureLayoutFits, 0);
  }

  function updateDetail(cust) {
    const root = document.getElementById('pusula-detail-summary');
    if (!root) return;
    ['id','name','phone','address'].forEach((field) => {
      const el = root.querySelector(`[data-field="${field}"]`);
      if (el) el.textContent = cust ? (cust[field] || '—') : '—';
    });
  }

  async function loadSales(customerId, selectedSaleId = null) {
    try {
      state.sales = await api(`/sales?customer_id=${customerId}&with=installments`);
      renderSalesTable(state.sales, { selectedSaleId });
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
      state.sales = [];
      renderSalesTable([], { selectedSaleId });
    }
  }

  function renderSalesTable(rows, { selectedSaleId = null } = {}) {
    const tbody = document.querySelector('#pusula-sales-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    const prevSaleId = state.currentSale ? String(state.currentSale.id) : null;
    const prevExplicit = state.currentSaleExplicit;
    state.currentSale = null;
    state.currentSaleExplicit = false;
    const editBtn = document.getElementById('btn-edit-sale');
    const deleteBtn = document.getElementById('btn-delete-sale');
    const printBtn = document.getElementById('btn-print-sale');
    if (editBtn) editBtn.disabled = true;
    if (deleteBtn) deleteBtn.disabled = true;
    if (printBtn) printBtn.disabled = true;
    const list = Array.isArray(rows) ? rows : [];
    const hasSingleSale = list.length === 1;
    let preferredSale = null;
    if (selectedSaleId) {
      preferredSale = list.find((s) => String(s.id) === String(selectedSaleId));
    }
    if (!preferredSale) {
      preferredSale = list.find((s) => hasUnpaidInstallments(s));
    }
    if (!preferredSale && list.length) {
      preferredSale = list[0];
    }
    const preferredId = preferredSale ? String(preferredSale.id) : null;
    let preferredRow = null;
    list.forEach((s) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${s.id}</td><td>${fromISO(s.date)}</td><td>${formatMoney(s.total || 0)}</td><td>${truncateDescription(s.description || '')}</td>`;
      tr.addEventListener('click', () => {
        state.currentSale = s;
        state.currentSaleExplicit = true;
        renderInstallments(s.installments || []);
        const editBtn = document.getElementById('btn-edit-sale');
        const deleteBtn = document.getElementById('btn-delete-sale');
        const printBtn = document.getElementById('btn-print-sale');
        if (editBtn) editBtn.disabled = false;
        if (deleteBtn) deleteBtn.disabled = false;
        if (printBtn) printBtn.disabled = false;
        tbody.querySelectorAll('tr').forEach((row) => row.classList.remove('selected'));
        tr.classList.add('selected');
      });
      tr.addEventListener('dblclick', (e) => {
        e.preventDefault();
        const descCell = tr.querySelector('td:last-child');
        openSaleDescriptionEditor(s, {
          customer: state.selected,
          onUpdated: (next) => {
            if (descCell) descCell.textContent = truncateDescription(next || '');
            if (state.currentSale && String(state.currentSale.id) === String(s.id)) {
              state.currentSale.description = next;
            }
          },
        });
      });
      if (preferredId && String(s.id) === preferredId) {
        preferredRow = tr;
        preferredSale = s;
        tr.classList.add('selected');
      }
      tbody.appendChild(tr);
    });
    if (preferredSale) {
      if (prevExplicit && prevSaleId && preferredId && prevSaleId === preferredId) {
        state.currentSaleExplicit = true;
      }
      state.currentSale = preferredSale;
      renderInstallments(preferredSale.installments || []);
      const allowSaleActions = hasSingleSale || state.currentSaleExplicit;
      if (editBtn) editBtn.disabled = !allowSaleActions;
      if (deleteBtn) deleteBtn.disabled = !allowSaleActions;
      if (printBtn) printBtn.disabled = !allowSaleActions;
      if (preferredRow && selectedSaleId) {
        try {
          preferredRow.scrollIntoView({ block: 'nearest' });
        } catch (e) { /* ignore */ }
      }
    } else if (!rows.length) {
      renderInstallments([]);
    }
  }

  function renderInstallments(insts) {
    const tbody = document.querySelector('#pusula-inst-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    state.currentInstallment = null;
    const instPrintBtn = document.getElementById('btn-print-inst');
    if (instPrintBtn) instPrintBtn.disabled = true;
    const todayISO = formatISODate(new Date());
    insts.forEach((i) => {
      const tr = document.createElement('tr');
      const paid = isPaid(i.paid);
      tr.innerHTML = `<td>${fromISO(i.due_date)}</td><td>${formatMoney(i.amount || 0)}</td><td>${paid ? 'Ödendi' : 'Ödenmedi'}</td>`;
      if (paid) tr.classList.add('paid');
      if (!paid && i.due_date && i.due_date < todayISO) tr.classList.add('late');
      tr.addEventListener('click', () => {
        tbody.querySelectorAll('tr').forEach((row) => row.classList.remove('selected'));
        tr.classList.add('selected');
        tr.dataset.instId = i.id;
        tr.dataset.saleId = i.sale_id || (state.currentSale && state.currentSale.id);
        state.currentInstallment = i;
        const btnPaid = document.getElementById('btn-mark-paid');
        const btnUnpaid = document.getElementById('btn-mark-unpaid');
        if (btnPaid && btnUnpaid) {
          btnPaid.disabled = false;
          btnUnpaid.disabled = false;
        }
        const instPrintBtn = document.getElementById('btn-print-inst');
        if (instPrintBtn) instPrintBtn.disabled = !paid;
      });
      tbody.appendChild(tr);
    });
    const btnPaid = document.getElementById('btn-mark-paid');
    const btnUnpaid = document.getElementById('btn-mark-unpaid');
    if (btnPaid) btnPaid.disabled = true;
    if (btnUnpaid) btnUnpaid.disabled = true;
    if (!insts.length && instPrintBtn) instPrintBtn.disabled = true;
  }

  async function toggleInstallmentPaid(paid) {
    const tbody = document.querySelector('#pusula-inst-table tbody');
    if (!tbody) return;
    const selectedRow = Array.from(tbody.querySelectorAll('tr')).find((r) => r.classList.contains('selected'));
    if (!selectedRow) return;
    const instId = selectedRow.dataset.instId;
    if (!instId) return;
    try {
      setInstallmentsLoading(true);
      await api(`/installments/${instId}`, {
        method: 'PUT',
        body: JSON.stringify({ paid: paid ? 1 : 0 }),
      });
      setStatus('Taksit güncellendi.');
      if (state.currentInstallment) state.currentInstallment.paid = paid ? 1 : 0;

      if (paid && state.currentInstallment && state.selected) {
        const due = state.currentInstallment.due_date;
        const dt = parseISODate(due);
        if (dt && window.confirm('Makbuz yazdırılsın mı?')) {
          printPaymentReceiptForMonth(state.selected, dt.getFullYear(), dt.getMonth() + 1);
        }
      }

      if (state.selected) await loadSales(state.selected.id, state.currentSale ? state.currentSale.id : null);
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    } finally {
      setInstallmentsLoading(false);
    }
  }

  function printSelectedInstallmentReceipt() {
    if (!state.selected || !state.currentInstallment) return;
    if (!isPaid(state.currentInstallment.paid)) return;
    const dt = parseISODate(state.currentInstallment.due_date);
    if (!dt) {
      setStatus('Hata: Taksit tarihi bulunamadı.', true);
      return;
    }
    printPaymentReceiptForMonth(state.selected, dt.getFullYear(), dt.getMonth() + 1);
  }

  function trMonthName(month1to12) {
    const months = [
      'Ocak',
      'Şubat',
      'Mart',
      'Nisan',
      'Mayıs',
      'Haziran',
      'Temmuz',
      'Ağustos',
      'Eylül',
      'Ekim',
      'Kasım',
      'Aralık',
    ];
    const idx = Number(month1to12) - 1;
    return months[idx] || '';
  }

  function collectPaidInstallmentsForMonth(year, month1to12, salesList = null) {
    const items = [];
    const sales = Array.isArray(salesList) ? salesList : (state.sales || []);
    sales.forEach((sale) => {
      (sale.installments || []).forEach((inst) => {
        if (!isPaid(inst.paid)) return;
        const dt = parseISODate(inst.due_date);
        if (!dt) return;
        if (dt.getFullYear() !== Number(year) || dt.getMonth() + 1 !== Number(month1to12)) return;
        items.push({
          due_date: inst.due_date,
          amount: Number(inst.amount || 0),
          sale_id: sale.id,
        });
      });
    });
    const normalizeDueDate = (value) => {
      const raw = String(value || '').trim();
      if (!raw) return null;
      const compact = raw.length >= 10 ? raw.slice(0, 10) : raw;
      const iso = toISO(compact) || compact;
      const dt = parseISODate(iso);
      return dt ? dt.getTime() : null;
    };
    items.sort((a, b) => {
      const da = normalizeDueDate(a.due_date);
      const db = normalizeDueDate(b.due_date);
      if (da !== null && db !== null && da !== db) return da - db;
      if (da !== null && db === null) return -1;
      if (db !== null && da === null) return 1;
      return Number(a.sale_id || 0) - Number(b.sale_id || 0);
    });
    return items;
  }

  function printPaymentReceiptForMonth(customer, year, month1to12, salesList = null, fallbackInst = null) {
    if (!customer) return;
    const company = {
      name: 'ENES BEKO',
      address: 'KOZAN CD. PTT EVLERİ KAVŞAĞI NO: 689, ADANA',
      phone: 'Telefon: (0322) 329 92 32',
      web: 'Web: https://enesbeko.com',
      footerSub: 'ENES EFY KARDEŞLER',
    };

    const items = collectPaidInstallmentsForMonth(year, month1to12, salesList);
    if (!items.length && fallbackInst && isPaid(fallbackInst.paid)) {
      items.push({
        due_date: fallbackInst.due_date,
        amount: Number(fallbackInst.amount || 0),
        sale_id: fallbackInst.sale_id || (state.currentSale && state.currentSale.id),
      });
    }
    if (!items.length && state.currentInstallment && isPaid(state.currentInstallment.paid)) {
      items.push({
        due_date: state.currentInstallment.due_date,
        amount: Number(state.currentInstallment.amount || 0),
        sale_id: state.currentInstallment.sale_id || (state.currentSale && state.currentSale.id),
      });
    }
    if (!items.length) {
      setStatus('Bu ay için ödenmiş taksit bulunamadı.', true);
      return;
    }

    const todayISO = formatISODate(new Date());
    const totalPaid = items.reduce((sum, i) => sum + Number(i.amount || 0), 0);
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const timeStr = `${hh}:${mm}`;

    const monthName = trMonthName(month1to12);
    const customerId = customer.id || '';
    const customerName = customer.name || '';
    const customerAddress = customer.address || '';
    const anyLate = items.some((i) => i.due_date && i.due_date < todayISO);

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
        .no-print { font-size:12px; color:#000; margin:10px 0 14px; }
        .brand { text-align:center; }
        .brand .name { font-weight:700; font-size:18px; letter-spacing:1px; margin:0; }
        .brand .line { font-size:11px; margin:3px 0 0; }
        .rule { border-top:2px solid #000; margin:10px 0 12px; }
        .title { text-align:center; font-weight:700; font-size:14px; margin:0 0 10px; }
        .meta-row { display:flex; justify-content:space-between; font-size:12px; margin:6px 0 10px; }
        .info { font-size:12px; margin:6px 0 12px; }
        .info .row { display:flex; gap:10px; margin:4px 0; }
        .info .label { width:110px; }
        table { width:100%; border-collapse: collapse; margin-top: 8px; }
        th, td { border:1px solid #000; padding:6px 8px; font-size:12px; text-align:left; }
        th { font-weight:700; }
        .totals { margin-top: 12px; font-size:12px; }
        .totals .row { display:flex; justify-content:space-between; margin:6px 0; }
        .totals .grand { font-weight:700; border-top:2px solid #000; padding-top:8px; margin-top:8px; }
        .note { margin-top: 8px; font-size: 12px; font-weight: 700; }
        .footer-rule { border-top:2px solid #000; margin:18px 0 10px; }
        .footer { text-align:center; font-size:11px; }
        .footer .thanks { margin:0 0 10px; }
        .footer .name { font-weight:700; letter-spacing:1px; margin:0; }
        .footer .sub { margin:4px 0 0; color:#000; }
      </style></head><body>
      <div class="receipt">
        <div class="no-print">Not: Yazdırma ekranında “Üstbilgi ve altbilgiler” seçeneğini kapatın.</div>
        <div class="brand">
          <p class="name">${company.name}</p>
          <p class="line">${company.address}</p>
          <p class="line">${company.phone} | ${company.web}</p>
        </div>
        <div class="rule"></div>
        <p class="title">${monthName} ${year} Taksit Ödemesi</p>
        <div class="meta-row">
          <div><strong>Tarih:</strong> ${fromISOSlash(todayISO)}</div>
          <div><strong>Saat:</strong> ${timeStr}</div>
        </div>
        <div class="info">
          <div class="row"><div class="label"><strong>Hesap No:</strong></div><div>${customerId}</div></div>
          <div class="row"><div class="label"><strong>Müşteri:</strong></div><div>${customerName}</div></div>
          <div class="row"><div class="label"><strong>Adres:</strong></div><div>${customerAddress}</div></div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Taksit Tarihi</th>
              <th>Tutar</th>
              <th>Satış No</th>
              <th>Durum</th>
            </tr>
          </thead>
          <tbody>`;

    items.forEach((i) => {
      const due = i.due_date ? String(i.due_date) : '';
      const status = due && due < todayISO ? 'Geç Ödeme' : 'Vadesinde';
      html += `
            <tr>
              <td>${fromISOSlash(due)}</td>
              <td>${formatMoney(i.amount)}</td>
              <td>${i.sale_id || ''}</td>
              <td>${status}</td>
            </tr>`;
    });

    html += `
          </tbody>
        </table>
        <div class="totals">
          <div class="row grand"><div><strong>Toplam Ödenen:</strong></div><div><strong>${formatMoney(totalPaid)}</strong></div></div>
        </div>
        ${anyLate ? `<div class="note">Bu ödeme vadesinden sonra yapılmıştır.</div>` : ''}
        <div class="footer-rule"></div>
        <div class="footer">
          <p class="thanks">Mağazamızdan yapmış olduğunuz ödeme için teşekkür ederiz</p>
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

  async function deleteSale(sale) {
    const s = sale && sale.id ? sale : null;
    if (!s) return false;
    if (!window.confirm('Bu satışı silmek istediğinize emin misiniz?')) return false;
    if (!window.confirm('Dikkat: Bu işlem geri alınamaz. Bu satışa bağlı tüm taksitler de silinecek. Devam etmek istiyor musunuz?')) return false;
    try {
      setStatus('Siliniyor...');
      await api(`/sales/${s.id}`, { method: 'DELETE' });
      setStatus('Satış silindi.');
      const keepSelectedId = state.currentSale && String(state.currentSale.id) !== String(s.id) ? state.currentSale.id : null;
      state.sales = (state.sales || []).filter((row) => String(row.id) !== String(s.id));
      renderSalesTable(state.sales || [], { selectedSaleId: keepSelectedId });
      return true;
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
      return false;
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

    const normalizeDueDate = (value) => {
      const raw = String(value || '').trim();
      if (!raw) return null;
      const compact = raw.length >= 10 ? raw.slice(0, 10) : raw;
      const iso = toISO(compact) || compact;
      const dt = parseISODate(iso);
      return dt ? dt.getTime() : null;
    };
    const compareByDueDate = (a, b) => {
      const da = normalizeDueDate(a?.due_date);
      const db = normalizeDueDate(b?.due_date);
      if (da !== null && db !== null) {
        if (da !== db) return da - db;
      } else if (da !== null) {
        return -1;
      } else if (db !== null) {
        return 1;
      }
      return Number(a?.id || 0) - Number(b?.id || 0);
    };
    const insts = (sale.installments || [])
      .map((i) => ({ ...i, paid: isPaid(i.paid) ? 1 : 0 }))
      .sort(compareByDueDate);
    const todayISO = formatISODate(new Date());
    const todayStamp = normalizeDueDate(todayISO);
    const unpaid = insts.filter((i) => !isPaid(i.paid));
    const overdue = unpaid.filter((i) => {
      if (!i.due_date) return false;
      const stamp = normalizeDueDate(i.due_date);
      if (stamp !== null && todayStamp !== null) return stamp < todayStamp;
      return String(i.due_date) < todayISO;
    });
    const upcoming = unpaid.filter((i) => {
      if (!i.due_date) return false;
      const stamp = normalizeDueDate(i.due_date);
      if (stamp !== null && todayStamp !== null) return stamp >= todayStamp;
      return String(i.due_date) >= todayISO;
    });
    overdue.sort(compareByDueDate);
    upcoming.sort(compareByDueDate);

    const formatTL = (n) => formatMoney(n || 0);
    const fmtDate = (iso) => fromISOSlash(iso || '');
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const timeStr = `${hh}:${mm}`;
    const overdueTotal = overdue.reduce((s, i) => s + Number(i.amount || 0), 0);
    const totalInst = insts.reduce((s, i) => s + Number(i.amount || 0), 0);
    const saleTotal = Number(sale.total || 0);
    const downVal = Number(sale.down);
    const down = Number.isFinite(downVal) ? downVal : Math.max(0, saleTotal - totalInst);
    const isInstallmentSale = insts.length > 0;
    const receiptTitle = isInstallmentSale ? 'Taksitli Alışveriş - Satış Makbuzu' : 'Satış Makbuzu';

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
        .no-print { font-size:12px; color:#000; margin:10px 0 14px; }
        .brand { text-align:center; }
        .brand .name { font-weight:700; font-size:18px; letter-spacing:1px; margin:0; }
        .brand .line { font-size:11px; margin:3px 0 0; }
        .rule { border-top:2px solid #000; margin:10px 0 12px; }
        .title { text-align:center; font-weight:700; font-size:14px; margin:0 0 10px; }
        .meta-row { display:flex; justify-content:space-between; font-size:12px; margin:6px 0 12px; }
        .info { font-size:12px; margin:8px 0 12px; }
        .info .row { display:flex; gap:10px; margin:4px 0; }
        .info .label { width:90px; }
        .box { border:1px solid #000; border-radius:4px; padding:10px 12px; font-size:12px; margin:10px 0 14px; }
        .box .line { margin:3px 0; }
        .cols { display:flex; gap:30px; }
        .col { flex:1; }
        .col h3 { font-size:12px; margin:0; font-weight:700; }
        .col .under { border-bottom:1px solid #000; margin:6px 0 8px; }
        .item { font-size:12px; margin:6px 0; }
        .money { color:#000; font-weight:700; }
        .totals { margin-top:16px; font-size:12px; }
        .totals .row { display:flex; justify-content:space-between; margin:6px 0; }
        .totals .grand { font-weight:700; border-top:2px solid #000; padding-top:8px; margin-top:8px; }
        .footer-rule { border-top:2px solid #000; margin:18px 0 10px; }
        .footer { text-align:center; font-size:11px; }
        .footer .thanks { margin:0 0 10px; }
        .footer .name { font-weight:700; letter-spacing:1px; margin:0; }
        .footer .sub { margin:4px 0 0; color:#000; }
      </style></head><body>
      <div class="receipt">
        <div class="no-print">Not: Yazdırma ekranında “Üstbilgi ve altbilgiler” seçeneğini kapatın.</div>
        <div class="brand">
          <p class="name">${company.name}</p>
          <p class="line">${company.address}</p>
          <p class="line">${company.phone} | ${company.web}</p>
        </div>
        <div class="rule"></div>
        <p class="title">${receiptTitle}</p>
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
          <div class="line"><span class="money">${formatTL(isInstallmentSale ? down : saleTotal)}</span> ${isInstallmentSale ? 'Peşinat Alınmıştır' : 'Tahsil Edilmiştir'}</div>
        </div>`;

    if (isInstallmentSale) {
      html += `
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
          <div class="row grand"><div><strong>Genel Toplam:</strong></div><div class="money">${formatTL(saleTotal)}</div></div>
        </div>`;
    } else {
      html += `
        <div class="totals">
          <div class="row grand"><div><strong>Genel Toplam:</strong></div><div class="money">${formatTL(saleTotal)}</div></div>
        </div>`;
    }

    html += `
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
  function startOfWeekMonday(date) {
    const d = date instanceof Date ? new Date(date) : new Date(date);
    const day = d.getDay(); // 0=Sun, 1=Mon...
    const diff = day === 0 ? -6 : 1 - day;
    d.setDate(d.getDate() + diff);
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function setReportRange(startDate, endDate) {
    const startEl = document.getElementById('rep-start');
    const endEl = document.getElementById('rep-end');
    if (!startEl || !endEl) return;
    startEl.value = fromISO(formatISODate(startDate));
    endEl.value = fromISO(formatISODate(endDate));
    loadReport();
  }

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
      <div class="pusula-actions report-quick-actions" id="rep-quick">
        <button type="button" class="secondary" data-range="today">BUGÜN</button>
        <button type="button" class="secondary" data-range="yesterday">DÜN</button>
        <button type="button" class="secondary" data-range="this-week">BU HAFTA</button>
        <button type="button" class="secondary" data-range="last-week">GEÇEN HAFTA</button>
        <button type="button" class="secondary" data-range="this-month">BU AY</button>
        <button type="button" class="secondary" data-range="last-month">GEÇEN AY</button>
      </div>
      <div class="pusula-summary"><span id="rep-total">0,00₺</span> — <span id="rep-count">0</span> satış</div>
      <div class="pusula-table-wrapper">
        <table class="pusula-table" id="rep-table">
          <thead><tr><th>No</th><th>Müşteri</th><th>Tarih</th><th>Tutar</th><th>Açıklama</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    `;
    root.querySelector('#rep-run').addEventListener('click', () => loadReport());
    root.querySelectorAll('#rep-quick [data-range]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const range = btn.getAttribute('data-range');
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        if (range === 'today') {
          setReportRange(today, today);
          return;
        }
        if (range === 'yesterday') {
          const y = new Date(today);
          y.setDate(y.getDate() - 1);
          setReportRange(y, y);
          return;
        }
        if (range === 'this-week') {
          const start = startOfWeekMonday(today);
          setReportRange(start, today);
          return;
        }
        if (range === 'last-week') {
          const thisWeekStart = startOfWeekMonday(today);
          const start = new Date(thisWeekStart);
          start.setDate(start.getDate() - 7);
          const end = new Date(start);
          end.setDate(end.getDate() + 6);
          setReportRange(start, end);
          return;
        }
        if (range === 'this-month') {
          const start = new Date(today.getFullYear(), today.getMonth(), 1);
          setReportRange(start, today);
          return;
        }
        if (range === 'last-month') {
          const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
          const end = new Date(today.getFullYear(), today.getMonth(), 0);
          setReportRange(start, end);
        }
      });
    });
    setTimeout(ensureLayoutFits, 0);
  }

  async function loadReport({ silent = false } = {}) {
    const startEl = document.getElementById('rep-start');
    const endEl = document.getElementById('rep-end');
    if (!startEl || !endEl) return;
    const start = startEl.value || todayStr();
    const end = endEl.value || todayStr();
    try {
      const rows = await api(`/sales?start=${toISO(start)}&end=${toISO(end)}`);
      state.reportSales = rows || [];
      const total = rows.reduce((sum, s) => sum + Number(s.total || 0), 0);
      document.getElementById('rep-total').textContent = formatMoney(total);
      document.getElementById('rep-count').textContent = rows.length;
      const tbody = document.querySelector('#rep-table tbody');
      tbody.innerHTML = '';
      rows.forEach((s) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${s.id}</td><td>${s.customer_name || ''}</td><td>${fromISO(s.date)}</td><td>${formatMoney(s.total || 0)}</td><td>${truncateDescription(s.description || '')}</td>`;
        tr.addEventListener('dblclick', (e) => {
          e.preventDefault();
          const descCell = tr.querySelector('td:last-child');
          openSaleDescriptionEditor(s, {
            customer: { id: s.customer_id, name: s.customer_name },
            onUpdated: (next) => {
              if (descCell) descCell.textContent = truncateDescription(next || '');
            },
          });
        });
        tbody.appendChild(tr);
      });
      if (!silent) setStatus('Rapor yüklendi.');
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
    setTimeout(ensureLayoutFits, 0);
  }

  // ------------------- Expected Payments -------------------
  function renderExpectedTab() {
    const root = document.getElementById('pusula-tab-expected');
    if (!root) return;
    root.innerHTML = `
      <div class="pusula-grid">
        <label class="pusula-input"><span>Vade Başlangıç</span><input type="text" id="exp-start" placeholder="GG-AA-YYYY"></label>
        <label class="pusula-input"><span>Vade Bitiş</span><input type="text" id="exp-end" placeholder="GG-AA-YYYY"></label>
        <div class="pusula-actions"><button id="exp-run">LİSTELE</button></div>
      </div>
      <div class="pusula-actions report-quick-actions" id="exp-quick">
        <button type="button" class="secondary" data-range="all">TÜMÜ</button>
        <button type="button" class="secondary" data-range="this-month">BU AY</button>
        <button type="button" class="secondary" data-range="next-month">GELECEK AY</button>
        <label class="pusula-check"><input type="checkbox" id="exp-hide-late"><span>Gecikmiş ödemeleri gizle</span></label>
      </div>
      <div class="pusula-summary"><span id="exp-total">0,00₺</span> — <span id="exp-count">0</span> taksit</div>
      <div class="pusula-actions expected-actions">
        <button id="exp-mark-paid" disabled>ÖDENDİ İŞARETLE</button>
        <button id="exp-mark-unpaid" disabled>ÖDENMEDİ İŞARETLE</button>
        <button id="exp-print" disabled>Makbuz Yazdır</button>
      </div>
      <div class="pusula-table-wrapper">
        <table class="pusula-table" id="exp-table">
          <thead>
            <tr>
              <th>Vade</th>
              <th>Taksit</th>
              <th>Müşteri No</th>
              <th>Müşteri</th>
              <th>Telefon</th>
              <th>Adres</th>
              <th>Satış No</th>
              <th>Satış Tarihi</th>
              <th>Satış Tutarı</th>
              <th>Açıklama</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    `;
    root.querySelector('#exp-run').addEventListener('click', () => loadExpectedPayments());
    root.querySelector('#exp-hide-late').addEventListener('change', () => renderExpectedPaymentsTable());
    root.querySelector('#exp-start').addEventListener('input', () => {
      const changed = updateExpectedHideLateState();
      if (changed) renderExpectedPaymentsTable();
    });
    root.querySelector('#exp-mark-paid').addEventListener('click', markExpectedPaymentPaid);
    root.querySelector('#exp-mark-unpaid').addEventListener('click', markExpectedPaymentUnpaid);
    root.querySelector('#exp-print').addEventListener('click', () => printExpectedPaymentReceipt());
    root.querySelectorAll('#exp-quick [data-range]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const range = btn.getAttribute('data-range');
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        if (range === 'all') {
          const startEl = document.getElementById('exp-start');
          const endEl = document.getElementById('exp-end');
          if (startEl) startEl.value = '';
          if (endEl) endEl.value = '';
          const hideEl = document.getElementById('exp-hide-late');
          if (hideEl) hideEl.checked = false;
          updateExpectedHideLateState();
          loadExpectedPayments();
          return;
        }
        if (range === 'this-month') {
          const start = new Date(today.getFullYear(), today.getMonth(), 1);
          const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
          setExpectedRange(start, end);
          return;
        }
        if (range === 'next-month') {
          const start = new Date(today.getFullYear(), today.getMonth() + 1, 1);
          const end = new Date(today.getFullYear(), today.getMonth() + 2, 0);
          setExpectedRange(start, end);
        }
      });
    });
    updateExpectedHideLateState();
    setTimeout(ensureLayoutFits, 0);
  }

  function setExpectedRange(startDate, endDate) {
    const startEl = document.getElementById('exp-start');
    const endEl = document.getElementById('exp-end');
    if (!startEl || !endEl) return;
    startEl.value = fromISO(formatISODate(startDate));
    endEl.value = fromISO(formatISODate(endDate));
    updateExpectedHideLateState();
    loadExpectedPayments();
  }

  function updateExpectedHideLateState() {
    const hideEl = document.getElementById('exp-hide-late');
    const startEl = document.getElementById('exp-start');
    if (!hideEl || !startEl) return false;
    const todayISO = formatISODate(new Date());
    const startIso = toISO(startEl.value.trim());
    const shouldDisable = Boolean(startIso) && startIso >= todayISO;
    let changed = false;
    if (shouldDisable && !hideEl.disabled) {
      hideEl.disabled = true;
      changed = true;
    } else if (!shouldDisable && hideEl.disabled) {
      hideEl.disabled = false;
    }
    if (shouldDisable && hideEl.checked) {
      hideEl.checked = false;
      changed = true;
    }
    return changed;
  }

  function renderExpectedPaymentsTable() {
    const tbody = document.querySelector('#exp-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    state.currentExpected = null;
    const markPaidBtn = document.getElementById('exp-mark-paid');
    const markUnpaidBtn = document.getElementById('exp-mark-unpaid');
    const printBtn = document.getElementById('exp-print');
    if (markPaidBtn) markPaidBtn.disabled = true;
    if (markUnpaidBtn) markUnpaidBtn.disabled = true;
    if (printBtn) printBtn.disabled = true;
    const hideLate = Boolean(document.getElementById('exp-hide-late')?.checked);
    const todayISO = formatISODate(new Date());
    const lateCustomers = new Set();
    state.expectedPayments.forEach((row) => {
      const paidDate = row && row.paid_date ? String(row.paid_date) : '';
      const isPaidToday = isPaid(row && row.paid) && paidDate === todayISO;
      if (row && row.due_date && row.due_date < todayISO && !isPaidToday) {
        lateCustomers.add(String(row.customer_id || ''));
      }
    });
    const visibleRows = state.expectedPayments.filter((row) => {
      const isLatePayment = row && row.due_date && row.due_date < todayISO;
      const paidDate = row && row.paid_date ? String(row.paid_date) : '';
      const isPaidToday = isPaid(row && row.paid) && paidDate === todayISO;
      return !(hideLate && isLatePayment && !isPaidToday);
    });
    const total = visibleRows.reduce((sum, r) => sum + Number(r.amount || 0), 0);
    const totalEl = document.getElementById('exp-total');
    const countEl = document.getElementById('exp-count');
    if (totalEl) totalEl.textContent = formatMoney(total);
    if (countEl) countEl.textContent = visibleRows.length;
    visibleRows.forEach((row) => {
      const tr = document.createElement('tr');
      const due = row && row.due_date ? fromISO(row.due_date) : '';
      const saleDate = row && row.sale_date ? fromISO(row.sale_date) : '';
      const amount = formatMoney(row && row.amount ? row.amount : 0);
      const saleTotal = formatMoney(row && row.sale_total ? row.sale_total : 0);
      const desc = truncateDescription(row && row.sale_description ? row.sale_description : '');
      const address = [row && row.customer_address ? row.customer_address : '', row && row.customer_work_address ? row.customer_work_address : '']
        .filter(Boolean)
        .join(' / ');
      const paidDate = row && row.paid_date ? String(row.paid_date) : '';
      const isPaidRow = isPaid(row && row.paid);
      const isPaidToday = isPaidRow && paidDate === todayISO;
      tr.innerHTML = `
        <td>${due}</td>
        <td>${amount}</td>
        <td>${row && row.customer_id ? row.customer_id : ''}</td>
        <td>${row && row.customer_name ? row.customer_name : ''}</td>
        <td>${row && row.customer_phone ? row.customer_phone : ''}</td>
        <td>${address}</td>
        <td>${row && row.sale_id ? row.sale_id : ''}</td>
        <td>${saleDate}</td>
        <td>${saleTotal}</td>
        <td>${desc}</td>
      `;
      const isLatePayment = row && row.due_date && row.due_date < todayISO;
      if (isPaidToday) {
        tr.classList.add('paid-today');
      } else if (isLatePayment || lateCustomers.has(String(row && row.customer_id ? row.customer_id : ''))) {
        tr.classList.add('late');
      }
      tr.addEventListener('click', () => {
        state.currentExpected = row;
        tbody.querySelectorAll('tr').forEach((r) => r.classList.remove('selected'));
        tr.classList.add('selected');
        if (markPaidBtn) markPaidBtn.disabled = isPaidRow;
        if (markUnpaidBtn) markUnpaidBtn.disabled = !isPaidToday;
        if (printBtn) printBtn.disabled = !isPaidRow;
      });
      tr.addEventListener('dblclick', (e) => {
        e.preventDefault();
        openExpectedCustomerDetail(row);
      });
      tbody.appendChild(tr);
    });
    if (!visibleRows.length) {
      const tr = document.createElement('tr');
      tr.className = 'pusula-empty-row';
      tr.innerHTML = '<td colspan="10" class="pusula-empty-cell">Beklenen ödeme bulunamadı.</td>';
      tbody.appendChild(tr);
    }
  }

  function openExpectedCustomerDetail(row) {
    if (!row || !row.customer_id) return;
    const cust = {
      id: row.customer_id,
      name: row.customer_name || '',
      phone: row.customer_phone || '',
      address: row.customer_address || '',
      work_address: row.customer_work_address || '',
    };
    state.selected = cust;
    state.pendingCustomerId = null;
    updateDetail(cust);
    fillSaleCustomer(cust);
    activateTab('detail');
    loadSales(row.customer_id, row.sale_id || null);
  }

  async function printExpectedPaymentReceipt(row) {
    const target = row || state.currentExpected;
    if (!target || !isPaid(target.paid)) return;
    const dt = parseISODate(target.due_date);
    if (!dt) {
      setStatus('Hata: Taksit tarihi bulunamadı.', true);
      return;
    }
    const cust = {
      id: target.customer_id,
      name: target.customer_name || '',
      address: target.customer_address || '',
    };
    try {
      const sales = await fetchSalesForCustomer(target.customer_id);
      printPaymentReceiptForMonth(
        cust,
        dt.getFullYear(),
        dt.getMonth() + 1,
        sales,
        target
      );
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    }
  }

  async function markExpectedPaymentPaid() {
    if (!state.currentExpected || !state.currentExpected.installment_id) return;
    const instId = state.currentExpected.installment_id;
    try {
      setExpectedLoading(true);
      await api(`/installments/${instId}`, {
        method: 'PUT',
        body: JSON.stringify({ paid: 1 }),
      });
      setStatus('Ödeme güncellendi.');
      const todayISO = formatISODate(new Date());
      const updatedRow = { ...state.currentExpected, paid: 1, paid_date: todayISO };
      state.expectedPayments = (state.expectedPayments || []).map((row) => {
        if (String(row.installment_id) !== String(instId)) return row;
        return { ...row, paid: 1, paid_date: todayISO };
      });
      state.currentExpected = null;
      renderExpectedPaymentsTable();
      if (window.confirm('Makbuz yazdırılsın mı?')) {
        await printExpectedPaymentReceipt(updatedRow);
      }
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    } finally {
      setExpectedLoading(false);
    }
  }

  async function markExpectedPaymentUnpaid() {
    if (!state.currentExpected || !state.currentExpected.installment_id) return;
    const instId = state.currentExpected.installment_id;
    const todayISO = formatISODate(new Date());
    const paidDate = state.currentExpected.paid_date ? String(state.currentExpected.paid_date) : '';
    if (!isPaid(state.currentExpected.paid) || paidDate !== todayISO) return;
    try {
      setExpectedLoading(true);
      await api(`/installments/${instId}`, {
        method: 'PUT',
        body: JSON.stringify({ paid: 0 }),
      });
      setStatus('Ödeme güncellendi.');
      state.expectedPayments = (state.expectedPayments || []).map((row) => {
        if (String(row.installment_id) !== String(instId)) return row;
        return { ...row, paid: 0, paid_date: null };
      });
      state.currentExpected = null;
      renderExpectedPaymentsTable();
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    } finally {
      setExpectedLoading(false);
    }
  }

  async function loadExpectedPayments({ silent = false, showLoading = true } = {}) {
    const startEl = document.getElementById('exp-start');
    const endEl = document.getElementById('exp-end');
    const query = new URLSearchParams();
    const startRaw = startEl ? startEl.value.trim() : '';
    const endRaw = endEl ? endEl.value.trim() : '';
    const startIso = toISO(startRaw);
    const endIso = toISO(endRaw);
    if (startIso) query.append('start', startIso);
    if (endIso) query.append('end', endIso);
    try {
      if (showLoading) setExpectedLoading(true);
      const rows = await api(`/expected-payments${query.toString() ? `?${query.toString()}` : ''}`);
      state.expectedPayments = rows || [];
      renderExpectedPaymentsTable();
      if (!silent) setStatus('Beklenen ödemeler yüklendi.');
    } catch (err) {
      setStatus(`Hata: ${trErrorMessage(err.message)}`, true);
    } finally {
      if (showLoading) setExpectedLoading(false);
    }
    setTimeout(ensureLayoutFits, 0);
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
    renderExpectedTab();
    loadCustomers();
    startAutoRefresh();
    window.addEventListener('resize', () => setTimeout(ensureLayoutFits, 0));
    window.addEventListener('focus', () => autoRefreshTick());
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) autoRefreshTick();
    });
    setTimeout(ensureLayoutFits, 0);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
