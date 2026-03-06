// review_shared.js — Shared utilities and framework for stage review pages

// ═══════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════

function escHtml(s) {
  if (!s && s !== 0) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function formatVal(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function section(title, fields) {
  return `<div class="section"><div class="section-title">${escHtml(title)}</div>${fields.join('')}</div>`;
}

function field(label, value, compareValue) {
  const v = value || '';
  const display = v || '(empty)';
  const isEmpty = !v;
  const changed = compareValue !== undefined && String(v) !== String(compareValue || '');
  const cls = isEmpty ? 'field-value empty' : changed ? 'field-value changed' : 'field-value';
  return `<div class="field"><span class="field-label">${escHtml(label)}</span><span class="${cls}">${escHtml(display)}</span></div>`;
}

// Render parsed transaction data — reused by parse (pane 2/3), extract (pane 1), normalize (pane 1)
function renderParsedFields(data, cmpData) {
  const t = data.transaction || {};
  const addr = t.address || {};
  const xferor = data.transferor || {};
  const xferee = data.transferee || {};
  const site = data.site || {};
  const consid = data.consideration || {};
  const broker = data.broker || {};
  const extras = data.export_extras || {};
  const cmpExtras = cmpData?.export_extras || {};

  let html = '';

  html += section('Transaction', [
    field('Property Type', data.property_type, cmpData?.property_type),
    field('Transaction Type', t.transaction_type, cmpData?.transaction?.transaction_type),
    field('Address', addr.address, cmpData?.transaction?.address?.address),
    field('Suite', addr.address_suite, cmpData?.transaction?.address?.address_suite),
    field('Alt Addresses', (addr.alternate_addresses || []).join('; '), (cmpData?.transaction?.address?.alternate_addresses || []).join('; ')),
    field('City', addr.city, cmpData?.transaction?.address?.city),
    field('Municipality', addr.municipality, cmpData?.transaction?.address?.municipality),
    field('Province', addr.province, cmpData?.transaction?.address?.province),
    field('Postal Code', addr.postal_code, cmpData?.transaction?.address?.postal_code),
    field('Sale Date', t.sale_date, cmpData?.transaction?.sale_date),
    field('Sale Date ISO', t.sale_date_iso, cmpData?.transaction?.sale_date_iso),
    field('Sale Price', t.sale_price, cmpData?.transaction?.sale_price),
    field('Sale Price Raw', t.sale_price_raw, cmpData?.transaction?.sale_price_raw),
    field('Building SF', extras.building_sf, cmpExtras.building_sf),
    field('RT Number', t.rt_number, cmpData?.transaction?.rt_number),
    field('ARN', t.arn, cmpData?.transaction?.arn),
    field('PINs', (t.pins || []).join(', '), (cmpData?.transaction?.pins || []).join(', ')),
  ]);

  html += section('Seller (Transferor)', [
    field('Name', xferor.name, cmpData?.transferor?.name),
    field('Contact', xferor.contact, cmpData?.transferor?.contact),
    field('Attention', xferor.attention, cmpData?.transferor?.attention),
    field('Phone', formatVal(xferor.phone), formatVal(cmpData?.transferor?.phone)),
    field('Phones', (xferor.phones || []).join('; '), (cmpData?.transferor?.phones || []).join('; ')),
    field('Address', formatVal(xferor.address), formatVal(cmpData?.transferor?.address)),
    field('Alt Names', (xferor.alternate_names || []).join('; '), (cmpData?.transferor?.alternate_names || []).join('; ')),
    field('Aliases', (xferor.aliases || []).join('; '), (cmpData?.transferor?.aliases || []).join('; ')),
    field('Company Lines', (xferor.company_lines || []).join('; '), (cmpData?.transferor?.company_lines || []).join('; ')),
    field('Contact Lines', (xferor.contact_lines || []).join('; '), (cmpData?.transferor?.contact_lines || []).join('; ')),
    field('Address Lines', (xferor.address_lines || []).join('; '), (cmpData?.transferor?.address_lines || []).join('; ')),
    field('Officer Titles', (xferor.officer_titles || []).join('; '), (cmpData?.transferor?.officer_titles || []).join('; ')),
  ]);

  html += section('Buyer (Transferee)', [
    field('Name', xferee.name, cmpData?.transferee?.name),
    field('Contact', xferee.contact, cmpData?.transferee?.contact),
    field('Attention', xferee.attention, cmpData?.transferee?.attention),
    field('Phone', formatVal(xferee.phone), formatVal(cmpData?.transferee?.phone)),
    field('Phones', (xferee.phones || []).join('; '), (cmpData?.transferee?.phones || []).join('; ')),
    field('Address', formatVal(xferee.address), formatVal(cmpData?.transferee?.address)),
    field('Alt Names', (xferee.alternate_names || []).join('; '), (cmpData?.transferee?.alternate_names || []).join('; ')),
    field('Aliases', (xferee.aliases || []).join('; '), (cmpData?.transferee?.aliases || []).join('; ')),
    field('Company Lines', (xferee.company_lines || []).join('; '), (cmpData?.transferee?.company_lines || []).join('; ')),
    field('Contact Lines', (xferee.contact_lines || []).join('; '), (cmpData?.transferee?.contact_lines || []).join('; ')),
    field('Address Lines', (xferee.address_lines || []).join('; '), (cmpData?.transferee?.address_lines || []).join('; ')),
    field('Officer Titles', (xferee.officer_titles || []).join('; '), (cmpData?.transferee?.officer_titles || []).join('; ')),
  ]);

  html += section('Site', [
    field('Legal Desc', site.legal_description, cmpData?.site?.legal_description),
    field('Area', `${site.site_area || ''} ${site.site_area_units || ''}`.trim(),
      `${cmpData?.site?.site_area || ''} ${cmpData?.site?.site_area_units || ''}`.trim()),
    field('Frontage', `${site.site_frontage || ''} ${site.site_frontage_units || ''}`.trim(),
      `${cmpData?.site?.site_frontage || ''} ${cmpData?.site?.site_frontage_units || ''}`.trim()),
    field('Depth', `${site.site_depth || ''} ${site.site_depth_units || ''}`.trim(),
      `${cmpData?.site?.site_depth || ''} ${cmpData?.site?.site_depth_units || ''}`.trim()),
    field('Zoning', site.zoning, cmpData?.site?.zoning),
    field('Site PINs', site.pins, cmpData?.site?.pins),
    field('Site ARN', site.arn, cmpData?.site?.arn),
  ]);

  html += section('Consideration', [
    field('Cash', consid.cash, cmpData?.consideration?.cash),
    field('Assumed Debt', consid.assumed_debt, cmpData?.consideration?.assumed_debt),
    field('Chattels', consid.chattels, cmpData?.consideration?.chattels),
    field('Verbatim', consid.verbatim, cmpData?.consideration?.verbatim),
    field('Chargees', (consid.chargees || []).join('; '), (cmpData?.consideration?.chargees || []).join('; ')),
  ]);

  html += section('Description', [
    field('Description', data.description, cmpData?.description),
  ]);

  html += section('Broker', [
    field('Brokerage', broker.brokerage, cmpData?.broker?.brokerage),
    field('Phone', broker.phone, cmpData?.broker?.phone),
  ]);

  html += section('Photos', [
    field('Count', (data.photos || []).length || '', (cmpData?.photos || []).length || ''),
    field('URLs', (data.photos || []).join('\n'), (cmpData?.photos || []).join('\n')),
  ]);

  return html;
}

// ═══════════════════════════════════════════════════════════════════════════
// Stage Review Framework
// ═══════════════════════════════════════════════════════════════════════════

function initStageReview(config) {
  // State
  let allRecords = [];
  let filteredRecords = [];
  let currentIndex = -1;
  let currentId = null;
  let reviewDirty = false;
  let statusData = null;
  let regressionSet = new Set();
  let extraData = null;

  // DOM refs
  const elFilter = document.getElementById('filter-select');
  const elSearch = document.getElementById('search-input');
  const elRecordSelect = document.getElementById('record-select');
  const elPrevBtn = document.getElementById('prev-btn');
  const elNextBtn = document.getElementById('next-btn');
  const elCounter = document.getElementById('counter');
  const elStatus = document.getElementById('status-info');
  const elRegBar = document.getElementById('regression-bar');
  const elRegLabel = document.getElementById('reg-bar-label');
  const elRegStatus = document.getElementById('reg-bar-status');
  const elRegApprove = document.getElementById('reg-approve');
  const elRegReject = document.getElementById('reg-reject');
  const elReviewPanel = document.getElementById('review-panel');
  const elToggleArrow = document.getElementById('toggle-arrow');
  const elSaveIndicator = document.getElementById('save-indicator');
  const elDetermination = document.getElementById('review-determination');
  const elNotes = document.getElementById('review-notes');
  const elSaveBtn = document.getElementById('review-save');
  const elClearBtn = document.getElementById('review-clear');

  // ── Navigation ──

  function applyFilter() {
    const filterVal = elFilter ? elFilter.value : 'all';
    const search = elSearch ? elSearch.value.toUpperCase().trim() : '';

    const filters = config.buildFilters ? config.buildFilters(extraData) : [];
    const filterDef = filters.find(f => f.value === filterVal);
    const filterFn = filterDef?.fn || (() => true);

    filteredRecords = allRecords.filter(r => {
      if (search && !r.rt_id.toUpperCase().includes(search)) return false;
      return filterFn(r);
    });

    // Populate record dropdown
    if (elRecordSelect) {
      elRecordSelect.innerHTML = '';
      for (const r of filteredRecords) {
        const opt = document.createElement('option');
        opt.value = r.rt_id;
        let label = r.rt_id;
        if (r.reviewed) label = '\u2713 ' + label;
        if (r.determination) label += ` (${r.determination})`;
        opt.textContent = label;
        elRecordSelect.appendChild(opt);
      }
    }

    if (elCounter) elCounter.textContent = `${filteredRecords.length} records`;

    if (filteredRecords.length > 0) {
      currentIndex = 0;
      if (elRecordSelect) elRecordSelect.value = filteredRecords[0].rt_id;
      loadRecord(filteredRecords[0].rt_id);
    } else {
      currentIndex = -1;
      currentId = null;
      clearPanes();
    }
    updateNav();
  }

  function updateNav() {
    if (elPrevBtn) elPrevBtn.disabled = currentIndex <= 0;
    if (elNextBtn) elNextBtn.disabled = currentIndex >= filteredRecords.length - 1;
    if (elCounter && currentIndex >= 0) {
      elCounter.textContent = `${currentIndex + 1} / ${filteredRecords.length}`;
    }
  }

  function navPrev() {
    if (currentIndex > 0) {
      currentIndex--;
      const rtId = filteredRecords[currentIndex].rt_id;
      if (elRecordSelect) elRecordSelect.value = rtId;
      loadRecord(rtId);
      updateNav();
    }
  }

  function navNext() {
    if (currentIndex < filteredRecords.length - 1) {
      currentIndex++;
      const rtId = filteredRecords[currentIndex].rt_id;
      if (elRecordSelect) elRecordSelect.value = rtId;
      loadRecord(rtId);
      updateNav();
    }
  }

  function clearPanes() {
    for (const id of ['pane-left', 'pane-middle', 'pane-right']) {
      const el = document.getElementById(id);
      if (el) el.innerHTML = '<div class="empty-state">No records match filter</div>';
    }
  }

  // ── Record Loading ──

  async function loadRecord(rtId) {
    currentId = rtId;
    currentIndex = filteredRecords.findIndex(r => r.rt_id === rtId);

    // Load review data
    loadReview(rtId);

    // Call stage-specific loader
    if (config.loadRecord) {
      await config.loadRecord(rtId, {
        left: document.getElementById('pane-left'),
        middle: document.getElementById('pane-middle'),
        right: document.getElementById('pane-right'),
      });
    }

    // Update regression bar
    updateRegressionBar();
  }

  // ── Review Panel ──

  function togglePanel() {
    if (elReviewPanel.classList.contains('collapsed')) {
      elReviewPanel.classList.remove('collapsed');
      elReviewPanel.classList.add('expanded');
      if (elToggleArrow) elToggleArrow.innerHTML = '&#9660;';
    } else {
      elReviewPanel.classList.remove('expanded');
      elReviewPanel.classList.add('collapsed');
      if (elToggleArrow) elToggleArrow.innerHTML = '&#9650;';
    }
  }

  function updateSaveIndicator(state) {
    if (!elSaveIndicator) return;
    elSaveIndicator.className = 'save-indicator ' + state;
    if (state === 'saved') elSaveIndicator.textContent = 'Saved';
    else if (state === 'unsaved') elSaveIndicator.textContent = 'Unsaved';
    else elSaveIndicator.textContent = '';
  }

  function markDirty() {
    if (currentId) {
      reviewDirty = true;
      updateSaveIndicator('unsaved');
    }
  }

  async function loadReview(rtId) {
    if (elDetermination) elDetermination.value = '';
    if (elNotes) elNotes.value = '';
    if (config.clearOverrides) config.clearOverrides();
    reviewDirty = false;
    updateSaveIndicator('hidden');
    if (elSaveBtn) elSaveBtn.disabled = !rtId;
    if (!rtId) return;

    try {
      const url = typeof config.reviewUrl === 'function'
        ? config.reviewUrl(rtId) : `${config.reviewUrl}/${rtId}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data && (data.determination !== undefined || data.overrides)) {
          if (elDetermination) elDetermination.value = data.determination || '';
          if (elNotes) elNotes.value = data.notes || '';
          if (config.setOverrides) config.setOverrides(data.overrides || {});
          const hasContent = data.determination || data.notes ||
            (data.overrides && Object.keys(data.overrides).length > 0);
          updateSaveIndicator(hasContent ? 'saved' : 'hidden');
          // Track sandbox_accepted
          const rec = allRecords.find(r => r.rt_id === rtId);
          if (rec) rec.sandbox_accepted = !!data.sandbox_accepted;
        }
      }
    } catch { /* no review yet */ }
  }

  async function saveReview() {
    if (!currentId) return;
    const determination = elDetermination ? elDetermination.value : '';
    const notes = elNotes ? elNotes.value : '';
    const overrides = config.getOverrides ? config.getOverrides() : {};

    try {
      const url = typeof config.reviewUrl === 'function'
        ? config.reviewUrl(currentId) : `${config.reviewUrl}/${currentId}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ determination, notes, overrides }),
      });
      if (res.ok) {
        reviewDirty = false;
        const hasContent = determination || notes || Object.keys(overrides).length > 0;
        updateSaveIndicator(hasContent ? 'saved' : 'hidden');
        // Update local record
        const rec = allRecords.find(r => r.rt_id === currentId);
        if (rec) {
          rec.reviewed = hasContent;
          rec.determination = determination;
          // Update dropdown label
          const opt = elRecordSelect?.querySelector(`option[value="${currentId}"]`);
          if (opt) {
            let label = currentId;
            if (rec.reviewed) label = '\u2713 ' + label;
            if (rec.determination) label += ` (${rec.determination})`;
            opt.textContent = label;
          }
        }
      }
    } catch (err) {
      console.error('Save failed:', err);
    }
  }

  function clearReview() {
    if (elDetermination) elDetermination.value = '';
    if (elNotes) elNotes.value = '';
    if (config.clearOverrides) config.clearOverrides();
    reviewDirty = true;
    updateSaveIndicator('unsaved');
  }

  // ── Regression Bar ──

  function updateRegressionBar() {
    if (!elRegBar) return;
    const rec = allRecords.find(r => r.rt_id === currentId);
    const isReg = rec && config.isRegression ? config.isRegression(rec) : false;

    if (!isReg) {
      elRegBar.classList.remove('visible');
      return;
    }

    elRegBar.classList.add('visible');
    if (rec.sandbox_accepted) {
      if (elRegStatus) elRegStatus.textContent = 'Approved';
      if (elRegApprove) elRegApprove.style.display = 'none';
      if (elRegReject) elRegReject.style.display = 'none';
    } else {
      if (elRegStatus) elRegStatus.textContent = '';
      if (elRegApprove) elRegApprove.style.display = '';
      if (elRegReject) elRegReject.style.display = '';
    }
  }

  async function approveRegression() {
    if (!currentId) return;
    const rec = allRecords.find(r => r.rt_id === currentId);
    if (!rec) return;

    const notes = elNotes ? elNotes.value : '';
    const overrides = config.getOverrides ? config.getOverrides() : {};

    try {
      const url = typeof config.reviewUrl === 'function'
        ? config.reviewUrl(currentId) : `${config.reviewUrl}/${currentId}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ determination: 'clean', notes, overrides, sandbox_accepted: true }),
      });
      if (res.ok) {
        rec.sandbox_accepted = true;
        rec.reviewed = true;
        rec.determination = 'clean';
        updateRegressionBar();
        loadReview(currentId);
      }
    } catch (err) {
      console.error('Approve failed:', err);
    }
  }

  function rejectRegression() {
    if (!currentId) return;
    if (elReviewPanel.classList.contains('collapsed')) togglePanel();
    if (elDetermination) elDetermination.value = config.rejectDetermination || 'parser_issue';
    markDirty();
  }

  // ── Init ──

  async function init() {
    // Fetch records and status
    const [recordsRes, statusRes] = await Promise.all([
      fetch(config.recordsUrl).then(r => r.json()),
      config.statusUrl ? fetch(config.statusUrl).then(r => r.json()) : Promise.resolve({}),
    ]);

    allRecords = recordsRes;
    statusData = statusRes;

    // Fetch regressions
    if (config.regressionsUrl) {
      try {
        const regRes = await fetch(config.regressionsUrl).then(r => r.json());
        regressionSet = new Set(regRes);
      } catch { /* no regressions endpoint */ }
    }

    // Status text
    if (elStatus && config.getStatusText) {
      elStatus.textContent = config.getStatusText(statusRes);
    }

    // Let page do extra initialization (fetch flags, etc.)
    if (config.onInit) {
      extraData = await config.onInit(allRecords, statusData, regressionSet);
    }

    // Build filter options
    if (elFilter && config.buildFilters) {
      const filters = config.buildFilters(extraData);
      elFilter.innerHTML = '';
      for (const f of filters) {
        const opt = document.createElement('option');
        opt.value = f.value;
        opt.textContent = f.count !== undefined ? `${f.label} (${f.count})` : f.label;
        elFilter.appendChild(opt);
      }
    }

    // Build determination options
    if (elDetermination && config.determinations) {
      elDetermination.innerHTML = '<option value="">(none)</option>';
      for (const d of config.determinations) {
        const opt = document.createElement('option');
        opt.value = d.value;
        opt.textContent = d.label;
        elDetermination.appendChild(opt);
      }
    }

    // Wire up events
    if (elFilter) elFilter.addEventListener('change', applyFilter);
    if (elSearch) elSearch.addEventListener('input', applyFilter);
    if (elRecordSelect) elRecordSelect.addEventListener('change', e => {
      const rtId = e.target.value;
      if (!rtId) return;
      currentIndex = filteredRecords.findIndex(r => r.rt_id === rtId);
      loadRecord(rtId);
      updateNav();
    });
    if (elPrevBtn) elPrevBtn.addEventListener('click', navPrev);
    if (elNextBtn) elNextBtn.addEventListener('click', navNext);

    // Review panel events
    const toggleEl = document.getElementById('review-toggle');
    if (toggleEl) toggleEl.addEventListener('click', togglePanel);
    if (elSaveBtn) elSaveBtn.addEventListener('click', saveReview);
    if (elClearBtn) elClearBtn.addEventListener('click', clearReview);
    if (elDetermination) elDetermination.addEventListener('change', markDirty);
    if (elNotes) elNotes.addEventListener('input', markDirty);

    // Regression bar events
    if (elRegApprove) elRegApprove.addEventListener('click', approveRegression);
    if (elRegReject) elRegReject.addEventListener('click', rejectRegression);

    // Keyboard navigation
    document.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      if (e.key === 'ArrowLeft') navPrev();
      if (e.key === 'ArrowRight') navNext();
    });

    // Initial load
    applyFilter();
  }

  init();

  // Return public API for page-specific code
  return {
    getAllRecords: () => allRecords,
    getFilteredRecords: () => filteredRecords,
    getCurrentId: () => currentId,
    getRegressionSet: () => regressionSet,
    getStatusData: () => statusData,
    markDirty,
    updateRegressionBar,
  };
}
