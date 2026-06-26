// Change log:
// 2026-06-26: Debounced auto-save for scenario fields and tiltak cards in modal.
// 2026-06-26: Browser back / mouse back closes scenario modal via history.pushState.
// 2026-06-26: Compact modal tiltak cards; unlink vs delete when shared across scenarios.
// 2026-06-26: Link existing scope tiltak; RiskID multi-select on modal action cards.
// 2026-06-26: Tiltak edited in scenario modal; scope tiltak table is read-only overview.
// 2026-06-26: Pause floatThead before scenario tbody rebuild; keep server rows on first load.
// 2026-06-26: Refresh tablesorter/floatThead after AJAX table rebuild – fixes empty scenario list.
// 2026-06-26: Tiltak edited in scope list; scenario modal no longer manages tiltak.
// 2026-06-26: Display-time R/T IDs; scope-level tiltak reuse; «Tilknyttede systemer».
// 2026-06-26: Scope meta edit toggled via Rediger button; exit edit mode after save/cancel.
// 2026-06-25: Konsekvens/sannsynlighet as colored tags, not full cell backgrounds.
// 2026-06-25: KIT tags with icons; column reorder; explicit risk cell backgrounds in table.
// 2026-06-25: Konsekvens/sannsynlighet cells show lookup labels with 1–5 color scale.
// 2026-06-25: Drop scenario detail page links – edit via scope modal only.
// 2026-06-25: Taller tiltak textareas in three-column modal layout.
// 2026-06-25: Unified tiltak table; colored scenario cells; drop level-count refresh.
// 2026-06-24: Refresh tiltak section after AJAX scenario save.
// 2026-06-24: AJAX modal editor for risk scenarios and tiltak on scope detail page.

(function () {
  'use strict';

  function getConfig() {
    const el = document.getElementById('risiko-editor-config');
    const urlsEl = document.getElementById('risiko-editor-urls');
    if (!el || !urlsEl) {
      return null;
    }
    const config = JSON.parse(el.textContent);
    config.urls = JSON.parse(urlsEl.textContent);
    return config;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function urlWithId(template, id) {
    return template.replace('{id}', String(id));
  }

  function initRisikoEditor() {
    const root = document.getElementById('risiko-scope-editor');
    if (!root || root.getAttribute('data-can-edit') !== 'true') {
      return;
    }

    const config = getConfig();
    if (!config) {
      return;
    }

    let meta = null;
    let draftSystems = [];
    let scopeTiltak = [];
    let scopeScenarios = [];
    let searchTimer = null;
    let scenarioAutosaveTimer = null;
    let scenarioSaveInFlight = null;
    let scenarioSnapshot = '';
    let modalAutosavePaused = false;
    let modalCloseAllowed = false;
    let modalSavedStatusTimer = null;
    const actionAutosaveTimers = new WeakMap();
    const actionSaveInFlight = new WeakMap();
    const actionSnapshots = new WeakMap();

    const AUTOSAVE_DELAY_MS = 800;

    const modal = $('#risiko-scenario-modal');
    const modalStatus = document.getElementById('risiko-modal-status');
    const scopeStatus = document.getElementById('risiko-scope-status');

    let modalHistoryActive = false;
    let suppressModalHistoryPop = false;

    modal.on('show.bs.modal', function () {
      history.pushState({ risikoScenarioModal: true }, '', window.location.href);
      modalHistoryActive = true;
    });

    modal.on('hidden.bs.modal', function () {
      if (modalHistoryActive) {
        modalHistoryActive = false;
        suppressModalHistoryPop = true;
        history.back();
      }
      clearTimeout(scenarioAutosaveTimer);
      scenarioAutosaveTimer = null;
    });

    modal.on('hide.bs.modal', function (e) {
      if (modalCloseAllowed) {
        modalCloseAllowed = false;
        return;
      }
      e.preventDefault();
      Promise.all([flushScenarioAutosave(), flushAllActionAutosaves()])
        .then(function () {
          modalCloseAllowed = true;
          modal.modal('hide');
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        });
    });

    window.addEventListener('popstate', function () {
      if (suppressModalHistoryPop) {
        suppressModalHistoryPop = false;
        return;
      }
      if (modal.hasClass('show')) {
        modalHistoryActive = false;
        modal.modal('hide');
      }
    });

    function setModalStatus(msg, isError) {
      if (!modalStatus) return;
      modalStatus.textContent = msg || '';
      modalStatus.className = isError ? 'small mb-2 text-danger' : 'small mb-2 text-muted';
    }

    function showModalSavedStatus() {
      setModalStatus('Lagret');
      clearTimeout(modalSavedStatusTimer);
      modalSavedStatusTimer = setTimeout(function () {
        if (modalStatus && modalStatus.textContent === 'Lagret') {
          setModalStatus('');
        }
      }, 2000);
    }

    function scenarioPayloadJson() {
      return JSON.stringify(collectScenarioPayload());
    }

    function captureScenarioSnapshot() {
      scenarioSnapshot = scenarioPayloadJson();
    }

    function captureActionSnapshot(card) {
      actionSnapshots.set(card, JSON.stringify(collectModalActionPayload(card)));
    }

    function actionPayloadJson(card) {
      return JSON.stringify(collectModalActionPayload(card));
    }

    function scheduleScenarioAutosave() {
      if (modalAutosavePaused) return;
      clearTimeout(scenarioAutosaveTimer);
      scenarioAutosaveTimer = setTimeout(function () {
        flushScenarioAutosave().catch(function (err) {
          setModalStatus(err.message, true);
        });
      }, AUTOSAVE_DELAY_MS);
    }

    function scheduleActionAutosave(card) {
      if (modalAutosavePaused || !card) return;
      const existing = actionAutosaveTimers.get(card);
      if (existing) clearTimeout(existing);
      actionAutosaveTimers.set(card, setTimeout(function () {
        actionAutosaveTimers.delete(card);
        persistActionCard(card).catch(function (err) {
          setModalStatus(err.message, true);
        });
      }, AUTOSAVE_DELAY_MS));
    }

    function flushScenarioAutosave() {
      clearTimeout(scenarioAutosaveTimer);
      scenarioAutosaveTimer = null;
      if (scenarioSaveInFlight) return scenarioSaveInFlight;
      if (scenarioPayloadJson() === scenarioSnapshot) return Promise.resolve();
      scenarioSaveInFlight = persistScenario()
        .finally(function () {
          scenarioSaveInFlight = null;
        });
      return scenarioSaveInFlight;
    }

    function flushAllActionAutosaves() {
      const cards = document.querySelectorAll('#risiko-actions-list .risiko-action-card');
      const jobs = [];
      cards.forEach(function (card) {
        const timer = actionAutosaveTimers.get(card);
        if (timer) {
          clearTimeout(timer);
          actionAutosaveTimers.delete(card);
        }
        const inFlight = actionSaveInFlight.get(card);
        if (inFlight) {
          jobs.push(inFlight);
          return;
        }
        if (actionPayloadJson(card) !== (actionSnapshots.get(card) || '')) {
          jobs.push(persistActionCard(card));
        }
      });
      return Promise.all(jobs);
    }

    function applyScenarioCreateResult(scenario) {
      if (!scenario || !scenario.id) return;
      document.getElementById('risiko-modal-scenario-id').value = scenario.id;
      document.getElementById('risiko-delete-scenario').style.display = '';
      const riskLabel = scenario.display_risk_id || '';
      document.getElementById('risiko-scenario-modal-title').textContent =
        riskLabel ? 'Rediger ' + riskLabel : 'Rediger scenario';
      updateModalTiltakToolbar(true);
    }

    function refreshScopeTablesOnly() {
      return fetchJson(config.urls.scenarios).then(function (data) {
        scopeTiltak = data.tiltak || [];
        scopeScenarios = data.scenarios || [];
        const hasServerRows = document.querySelector('#risiko-scenarios-tbody tr[data-scenario-id]');
        if (hasServerRows) {
          updateScenarioTiltakColumn(scopeScenarios);
        } else {
          renderScenariosTable(scopeScenarios);
        }
        renderTiltakSection(scopeTiltak);
      });
    }

    function persistScenario() {
      const scenarioId = document.getElementById('risiko-modal-scenario-id').value;
      const payload = collectScenarioPayload();
      const isCreate = !scenarioId;
      if (isCreate && !payload.uonsket_hendelse) {
        return Promise.resolve();
      }

      const url = isCreate
        ? config.urls.scenarioCreate
        : urlWithId(config.urls.scenarioUpdate, scenarioId);
      const method = isCreate ? 'POST' : 'PATCH';

      setModalStatus('Lagrer…');
      return fetchJson(url, { method: method, body: JSON.stringify(payload) })
        .then(function (data) {
          if (isCreate && data.scenario) {
            applyScenarioCreateResult(data.scenario);
          }
          captureScenarioSnapshot();
          showModalSavedStatus();
          return refreshScopeTablesOnly();
        });
    }

    function setScopeStatus(msg, isError) {
      if (!scopeStatus) return;
      scopeStatus.textContent = msg || '';
      scopeStatus.className = isError ? 'text-danger small ml-2' : 'text-muted small ml-2';
    }

    function fetchJson(url, options) {
      const opts = options || {};
      opts.credentials = 'same-origin';
      opts.headers = opts.headers || {};
      if (opts.body && !opts.headers['Content-Type']) {
        opts.headers['Content-Type'] = 'application/json';
      }
      if (opts.method && opts.method !== 'GET') {
        opts.headers['X-CSRFToken'] = config.csrf;
      }
      return fetch(url, opts).then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            const err = new Error((data && data.error) || 'Forespørsel feilet');
            err.data = data;
            throw err;
          }
          return data;
        });
      });
    }

    function riskLabel(sannsynlighet, konsekvens) {
      if (!meta || !sannsynlighet || !konsekvens) return '';
      const row = meta.risk_matrix[sannsynlighet];
      return row ? (row[konsekvens] || '') : '';
    }

    function badgeClass(label) {
      if (label === 'Lav') return 'badge-success';
      if (label === 'Middels') return 'badge-warning';
      if (label === 'Høy') return 'badge-danger';
      return 'badge-secondary';
    }

    function levelCellClass(level) {
      if (level === null || level === undefined || level === '') return 'risk-cell-empty';
      return 'risk-level-' + level;
    }

    function riskCellClass(label) {
      if (label === 'Lav') return 'risk-cell-lav';
      if (label === 'Middels') return 'risk-cell-middels';
      if (label === 'Høy') return 'risk-cell-hoy';
      return 'risk-cell-empty';
    }

    function updateRiskBadges() {
      const k = parseInt(document.getElementById('risiko-f-konsekvens').value, 10);
      const s = parseInt(document.getElementById('risiko-f-sannsynlighet').value, 10);
      const ke = parseInt(document.getElementById('risiko-f-konsekvens-etter').value, 10);
      const se = parseInt(document.getElementById('risiko-f-sannsynlighet-etter').value, 10);
      const curLabel = riskLabel(s, k);
      const resLabel = riskLabel(se, ke);
      const curBadge = document.getElementById('risiko-badge-current');
      const resBadge = document.getElementById('risiko-badge-residual');
      curBadge.textContent = curLabel || '–';
      curBadge.className = 'badge ' + badgeClass(curLabel);
      resBadge.textContent = resLabel || '–';
      resBadge.className = 'badge ' + badgeClass(resLabel);
    }

    function fillLevelSelect(selectEl, labels) {
      selectEl.innerHTML = '<option value="">–</option>';
      Object.keys(labels).sort(function (a, b) { return parseInt(a, 10) - parseInt(b, 10); }).forEach(function (level) {
        const opt = document.createElement('option');
        opt.value = level;
        opt.textContent = level + ' – ' + labels[level];
        selectEl.appendChild(opt);
      });
    }

    function populateMetaChoices() {
      if (!meta) return;
      fillLevelSelect(document.getElementById('risiko-f-konsekvens'), meta.konsekvens_labels);
      fillLevelSelect(document.getElementById('risiko-f-konsekvens-etter'), meta.konsekvens_labels);
      fillLevelSelect(document.getElementById('risiko-f-sannsynlighet'), meta.sannsynlighet_labels);
      fillLevelSelect(document.getElementById('risiko-f-sannsynlighet-etter'), meta.sannsynlighet_labels);
      const behSelect = document.getElementById('risiko-f-risikobehandling');
      behSelect.innerHTML = '<option value="">–</option>';
      meta.risikobehandling.forEach(function (item) {
        const opt = document.createElement('option');
        opt.value = item.value;
        opt.textContent = item.label;
        behSelect.appendChild(opt);
      });
    }

    function renderSystemChips() {
      const container = document.getElementById('risiko-system-chips');
      container.innerHTML = '';
      draftSystems.forEach(function (sys) {
        container.insertAdjacentHTML('beforeend',
          '<span class="badge badge-light mr-1 mb-1" data-id="' + sys.id + '">' +
          '<a href="' + escapeHtml(sys.url) + '">' + escapeHtml(sys.label) + '</a> ' +
          '<button type="button" class="btn btn-link btn-sm p-0 ml-1 risiko-system-fjern">&times;</button></span>'
        );
      });
    }

    function statusOptionsHtml(selected) {
      let html = '';
      (meta.tiltak_status || []).forEach(function (item) {
        html += '<option value="' + escapeHtml(item.value) + '"' +
          (item.value === selected ? ' selected' : '') + '>' + escapeHtml(item.label) + '</option>';
      });
      return html;
    }

    function collectScenarioPayload() {
      function levelVal(id) {
        const v = document.getElementById(id).value;
        return v === '' ? null : parseInt(v, 10);
      }
      return {
        uonsket_hendelse: document.getElementById('risiko-f-uonsket').value.trim(),
        kit_dimensjoner: document.getElementById('risiko-f-kit').value.trim(),
        arsaker_svakheter: document.getElementById('risiko-f-arsaker').value.trim(),
        konsekvens_nivaa: levelVal('risiko-f-konsekvens'),
        sannsynlighet_nivaa: levelVal('risiko-f-sannsynlighet'),
        konsekvens_etter: levelVal('risiko-f-konsekvens-etter'),
        sannsynlighet_etter: levelVal('risiko-f-sannsynlighet-etter'),
        konsekvens_begrunnelse: document.getElementById('risiko-f-konsekvens-begrunnelse').value.trim(),
        sannsynlighetsbegrunnelse: document.getElementById('risiko-f-sannsynlighet-begrunnelse').value.trim(),
        risikobehandling: document.getElementById('risiko-f-risikobehandling').value,
        system_ids: draftSystems.map(function (s) { return s.id; }),
      };
    }

    function fillScenarioForm(scenario) {
      modalAutosavePaused = true;
      document.getElementById('risiko-modal-scenario-id').value = scenario ? scenario.id : '';
      document.getElementById('risiko-f-kit').value = scenario ? (scenario.kit_dimensjoner || '') : '';
      document.getElementById('risiko-f-uonsket').value = scenario ? (scenario.uonsket_hendelse || '') : '';
      document.getElementById('risiko-f-arsaker').value = scenario ? (scenario.arsaker_svakheter || '') : '';
      document.getElementById('risiko-f-konsekvens').value = scenario && scenario.konsekvens_nivaa ? scenario.konsekvens_nivaa : '';
      document.getElementById('risiko-f-sannsynlighet').value = scenario && scenario.sannsynlighet_nivaa ? scenario.sannsynlighet_nivaa : '';
      document.getElementById('risiko-f-konsekvens-etter').value = scenario && scenario.konsekvens_etter ? scenario.konsekvens_etter : '';
      document.getElementById('risiko-f-sannsynlighet-etter').value = scenario && scenario.sannsynlighet_etter ? scenario.sannsynlighet_etter : '';
      document.getElementById('risiko-f-konsekvens-begrunnelse').value = scenario ? (scenario.konsekvens_begrunnelse || '') : '';
      document.getElementById('risiko-f-sannsynlighet-begrunnelse').value = scenario ? (scenario.sannsynlighetsbegrunnelse || '') : '';
      document.getElementById('risiko-f-risikobehandling').value = scenario ? (scenario.risikobehandling || '') : '';
      draftSystems = scenario ? (scenario.systemer || []).slice() : [];
      renderSystemChips();
      setModalStatus('');
      renderModalActionCards(scenario ? (scenario.actions || []) : []);
      updateModalTiltakToolbar(!!scenario);
      updateRiskBadges();
      document.getElementById('risiko-delete-scenario').style.display = scenario ? '' : 'none';
      const riskLabel = scenario ? (scenario.display_risk_id || '') : '';
      document.getElementById('risiko-scenario-modal-title').textContent = scenario
        ? (riskLabel ? 'Rediger ' + riskLabel : 'Rediger scenario')
        : 'Nytt scenario';
      captureScenarioSnapshot();
      modalAutosavePaused = false;
    }

    function openModalForCreate() {
      setModalStatus('');
      fillScenarioForm(null);
      modal.modal('show');
    }

    function openModalForEdit(scenarioId) {
      setModalStatus('Laster…');
      fetchJson(urlWithId(config.urls.scenarioDetail, scenarioId))
        .then(function (data) {
          setModalStatus('');
          fillScenarioForm(data.scenario);
          modal.modal('show');
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        });
    }

    function levelLabel(level, labels) {
      if (level === null || level === undefined || level === '') return '-';
      if (!labels) return String(level);
      return labels[level] || labels[String(level)] || '-';
    }

    const RISIKO_KIT_META = {
      K: { label: 'Konfidensialitet', css: 'risiko-kit-k' },
      I: { label: 'Integritet', css: 'risiko-kit-i' },
      T: { label: 'Tilgjengelighet', css: 'risiko-kit-t' },
    };

    const RISIKO_KIT_ICON_PATHS = {
      K: '<path d="M8 1a2 2 0 0 0-2 2v2H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2V3a2 2 0 0 0-2-2zM7 3a1 1 0 0 1 2 0v2H7V3z"/>',
      I: '<path d="M8 1 2 3.5v5A6 6 0 0 0 8 15a6 6 0 0 0 6-6.5v-5L8 1zm0 1.5 4 1.7v3.3a4 4 0 0 1-8 0V4.2l4-1.7z"/><path d="M6.2 8.2 7.5 9.5 10 7" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
      T: '<path d="M8 3.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zM2 8a6 6 0 1 1 12 0A6 6 0 0 1 2 8z"/><path d="M8 5.5V8l1.8 1.2" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    };

    function kitIconSvg(code) {
      const paths = RISIKO_KIT_ICON_PATHS[code];
      if (!paths) return '';
      return '<svg class="risiko-kit-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" ' +
        'fill="currentColor" aria-hidden="true" focusable="false">' + paths + '</svg>';
    }

    function renderKitTags(kitTags) {
      if (!kitTags || !kitTags.length) return '-';
      return kitTags.map(function (code) {
        const meta = RISIKO_KIT_META[code];
        if (!meta) return '';
        return '<span class="risiko-kit-tag ' + escapeHtml(meta.css) + '" title="' + escapeHtml(meta.label) + '">' +
          kitIconSvg(code) + escapeHtml(meta.label) + '</span>';
      }).join(' ');
    }

    function updateModalTiltakToolbar(hasScenario) {
      const addBtn = document.getElementById('risiko-add-action');
      const linkBtn = document.getElementById('risiko-link-action');
      const needSave = document.getElementById('risiko-modal-tiltak-need-save');
      if (addBtn) addBtn.disabled = !hasScenario;
      if (linkBtn) linkBtn.disabled = !hasScenario;
      if (needSave) needSave.classList.toggle('d-none', !!hasScenario);
      if (!hasScenario) hideLinkActionPicker();
    }

    function hideLinkActionPicker() {
      const picker = document.getElementById('risiko-link-action-picker');
      if (picker) picker.style.display = 'none';
    }

    function actionScenarioIds(action) {
      if (action.scenario_ids && action.scenario_ids.length) {
        return action.scenario_ids.slice();
      }
      const fromScope = scopeTiltak.find(function (a) { return a.id === action.id; });
      if (fromScope) {
        if (fromScope.scenario_ids && fromScope.scenario_ids.length) {
          return fromScope.scenario_ids.slice();
        }
        return (fromScope.risk_links || []).map(function (link) { return link.scenario_pk; });
      }
      return (action.risk_links || []).map(function (link) { return link.scenario_pk; });
    }

    function actionSharesWithOtherScenarios(action, currentScenarioId) {
      const ids = actionScenarioIds(action);
      if (!currentScenarioId) return ids.length > 1;
      return ids.some(function (id) { return id !== currentScenarioId; });
    }

    function buildModalActionCardHtml(action, defaultScenarioId) {
      const displayId = escapeHtml(action.display_tiltak_id || '–');
      let scenarioIds = actionScenarioIds(action);
      if (!scenarioIds.length && defaultScenarioId) {
        scenarioIds = [defaultScenarioId];
      }
      const shared = action.id && actionSharesWithOtherScenarios(action, defaultScenarioId);
      const removeBtn = shared
        ? '<button type="button" class="btn btn-outline-secondary btn-sm risiko-action-unlink">Koble fra</button>'
        : '<button type="button" class="btn btn-outline-danger btn-sm risiko-action-delete">Slett</button>';

      return '<div class="risiko-action-desc-row">' +
          '<span class="risiko-action-card-id">' + displayId + '</span>' +
          '<textarea class="form-control form-control-sm risiko-action-beskrivelse" rows="2">' +
          escapeHtml(action.beskrivelse || '') + '</textarea>' +
        '</div>' +
        '<div class="form-row risiko-action-meta-row no-gutters align-items-end">' +
          '<div class="col risiko-action-meta-col">' +
            '<label class="risiko-action-label">Ansvarlig</label>' +
            '<input type="text" class="form-control form-control-sm risiko-action-ansvarlig" value="' +
            escapeHtml(action.ansvarlig || '') + '">' +
          '</div>' +
          '<div class="col risiko-action-meta-col">' +
            '<label class="risiko-action-label">Frist</label>' +
            '<input type="date" class="form-control form-control-sm risiko-action-frist" value="' +
            escapeHtml(action.frist || '') + '">' +
          '</div>' +
          '<div class="col risiko-action-meta-col">' +
            '<label class="risiko-action-label">Status</label>' +
            '<select class="form-control form-control-sm risiko-action-status">' +
            statusOptionsHtml(action.status || 'ikke_startet') + '</select>' +
          '</div>' +
          '<div class="col-auto risiko-action-btn-col">' +
            removeBtn +
          '</div>' +
        '</div>';
    }

    function setCardScenarioIds(card, scenarioIds) {
      card.setAttribute('data-scenario-ids', (scenarioIds || []).join(','));
    }

    function cardScenarioIds(card) {
      const raw = card.getAttribute('data-scenario-ids');
      if (!raw) return [];
      return raw.split(',').map(function (part) {
        return parseInt(part, 10);
      }).filter(function (id) { return !isNaN(id); });
    }

    function renderModalActionCards(actions) {
      const container = document.getElementById('risiko-actions-list');
      if (!container) return;

      modalAutosavePaused = true;
      const scenarioIdRaw = document.getElementById('risiko-modal-scenario-id').value;
      const defaultScenarioId = scenarioIdRaw ? parseInt(scenarioIdRaw, 10) : null;

      const list = (actions || []).slice().sort(function (a, b) {
        const aNum = parseInt((a.display_tiltak_id || 'T0').slice(1), 10);
        const bNum = parseInt((b.display_tiltak_id || 'T0').slice(1), 10);
        return aNum - bNum;
      });

      container.innerHTML = '';
      list.forEach(function (action) {
        const card = document.createElement('div');
        card.className = 'risiko-action-card';
        if (action.id) {
          card.setAttribute('data-action-id', action.id);
        }
        const scenarioIds = actionScenarioIds(action);
        if (!scenarioIds.length && defaultScenarioId) {
          scenarioIds.push(defaultScenarioId);
        }
        setCardScenarioIds(card, scenarioIds);
        card.innerHTML = buildModalActionCardHtml(action, defaultScenarioId);
        container.appendChild(card);
        captureActionSnapshot(card);
      });
      hideLinkActionPicker();
      modalAutosavePaused = false;
    }

    function showLinkActionPicker() {
      const scenarioIdRaw = document.getElementById('risiko-modal-scenario-id').value;
      if (!scenarioIdRaw) {
        flushScenarioAutosave().then(function () {
          if (document.getElementById('risiko-modal-scenario-id').value) {
            showLinkActionPicker();
          } else {
            setModalStatus('Skriv uønsket hendelse – scenarioet opprettes automatisk.', true);
          }
        });
        return;
      }
      const currentScenarioId = parseInt(scenarioIdRaw, 10);
      const select = document.getElementById('risiko-link-action-select');
      const picker = document.getElementById('risiko-link-action-picker');
      if (!select || !picker) return;

      select.innerHTML = '<option value="">Velg tiltak…</option>';
      scopeTiltak.forEach(function (action) {
        const linkedIds = actionScenarioIds(action);
        if (linkedIds.indexOf(currentScenarioId) !== -1) return;
        const label = (action.display_tiltak_id || 'T?') + ' – ' +
          (action.beskrivelse || '').substring(0, 80);
        select.insertAdjacentHTML('beforeend',
          '<option value="' + action.id + '">' + escapeHtml(label) + '</option>'
        );
      });

      if (select.options.length <= 1) {
        setModalStatus('Ingen flere tiltak å koble – opprett et nytt.', true);
        return;
      }
      picker.style.display = '';
      setModalStatus('');
    }

    function linkExistingAction() {
      const select = document.getElementById('risiko-link-action-select');
      const scenarioIdRaw = document.getElementById('risiko-modal-scenario-id').value;
      if (!select || !scenarioIdRaw) return;

      const actionId = parseInt(select.value, 10);
      const currentScenarioId = parseInt(scenarioIdRaw, 10);
      if (!actionId) {
        setModalStatus('Velg et tiltak.', true);
        return;
      }

      const action = scopeTiltak.find(function (a) { return a.id === actionId; });
      if (!action) return;

      const scenarioIds = actionScenarioIds(action);
      if (scenarioIds.indexOf(currentScenarioId) === -1) {
        scenarioIds.push(currentScenarioId);
      }

      setModalStatus('Kobler…');
      fetchJson(urlWithId(config.urls.actionUpdate, actionId), {
        method: 'PATCH',
        body: JSON.stringify({
          beskrivelse: action.beskrivelse,
          ansvarlig: action.ansvarlig,
          frist: action.frist,
          status: action.status,
          scenario_ids: scenarioIds,
        }),
      })
        .then(function () {
          setModalStatus('');
          hideLinkActionPicker();
          return refreshAfterModalTiltakChange();
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        });
    }

    function collectModalActionPayload(card) {
      const scenarioIdRaw = document.getElementById('risiko-modal-scenario-id').value;
      const currentScenarioId = scenarioIdRaw ? parseInt(scenarioIdRaw, 10) : null;
      let scenarioIds = cardScenarioIds(card);
      if (currentScenarioId && scenarioIds.indexOf(currentScenarioId) === -1) {
        scenarioIds.push(currentScenarioId);
      }
      if (!scenarioIds.length && currentScenarioId) {
        scenarioIds = [currentScenarioId];
      }
      return {
        beskrivelse: card.querySelector('.risiko-action-beskrivelse').value.trim(),
        ansvarlig: card.querySelector('.risiko-action-ansvarlig').value.trim(),
        frist: card.querySelector('.risiko-action-frist').value || null,
        status: card.querySelector('.risiko-action-status').value,
        scenario_ids: scenarioIds,
      };
    }

    function refreshAfterModalTiltakChange() {
      const scenarioId = document.getElementById('risiko-modal-scenario-id').value;
      return refreshTable().then(function () {
        if (!scenarioId) return;
        return fetchJson(urlWithId(config.urls.scenarioDetail, scenarioId))
          .then(function (data) {
            renderModalActionCards(data.scenario.actions || []);
          });
      });
    }

    function persistActionCard(card) {
      const scenarioId = document.getElementById('risiko-modal-scenario-id').value;
      if (!scenarioId) {
        return flushScenarioAutosave().then(function () {
          if (!document.getElementById('risiko-modal-scenario-id').value) {
            return Promise.resolve();
          }
          return persistActionCard(card);
        });
      }

      const actionId = card.getAttribute('data-action-id');
      const payload = collectModalActionPayload(card);
      if (!payload.beskrivelse) {
        if (!actionId) return Promise.resolve();
        return Promise.reject(new Error('Beskrivelse er påkrevd.'));
      }
      if (actionPayloadJson(card) === (actionSnapshots.get(card) || '')) {
        return Promise.resolve();
      }

      const inFlight = actionSaveInFlight.get(card);
      if (inFlight) return inFlight;

      const isCreate = !actionId;
      const url = isCreate
        ? config.urls.actionCreate
        : urlWithId(config.urls.actionUpdate, actionId);
      const method = isCreate ? 'POST' : 'PATCH';

      setModalStatus('Lagrer…');
      const job = fetchJson(url, { method: method, body: JSON.stringify(payload) })
        .then(function (data) {
          if (isCreate && data.action) {
            card.setAttribute('data-action-id', data.action.id);
            const idSpan = card.querySelector('.risiko-action-card-id');
            if (idSpan && data.action.display_tiltak_id) {
              idSpan.textContent = data.action.display_tiltak_id;
            }
            if (data.action.id) {
              const shared = actionSharesWithOtherScenarios(
                data.action,
                parseInt(document.getElementById('risiko-modal-scenario-id').value, 10)
              );
              const btnCol = card.querySelector('.risiko-action-btn-col');
              if (btnCol) {
                btnCol.innerHTML = shared
                  ? '<button type="button" class="btn btn-outline-secondary btn-sm risiko-action-unlink">Koble fra</button>'
                  : '<button type="button" class="btn btn-outline-danger btn-sm risiko-action-delete">Slett</button>';
              }
            }
          }
          captureActionSnapshot(card);
          showModalSavedStatus();
          return refreshScopeTablesOnly();
        })
        .finally(function () {
          actionSaveInFlight.delete(card);
        });
      actionSaveInFlight.set(card, job);
      return job;
    }

    function unlinkModalActionCard(card) {
      const actionId = card.getAttribute('data-action-id');
      const scenarioIdRaw = document.getElementById('risiko-modal-scenario-id').value;
      if (!actionId || !scenarioIdRaw) {
        return Promise.resolve();
      }
      const currentScenarioId = parseInt(scenarioIdRaw, 10);
      if (!window.confirm('Fjerne koblingen til dette scenarioet? Tiltaket beholdes på andre scenarioer.')) {
        return Promise.resolve();
      }

      const action = scopeTiltak.find(function (a) { return a.id === parseInt(actionId, 10); });
      const payload = collectModalActionPayload(card);
      const scenarioIds = actionScenarioIds(action || {}).filter(function (id) {
        return id !== currentScenarioId;
      });

      setModalStatus('Kobler fra…');
      card.querySelectorAll('button').forEach(function (btn) { btn.disabled = true; });

      return fetchJson(urlWithId(config.urls.actionUpdate, actionId), {
        method: 'PATCH',
        body: JSON.stringify({
          beskrivelse: payload.beskrivelse,
          ansvarlig: payload.ansvarlig,
          frist: payload.frist,
          status: payload.status,
          scenario_ids: scenarioIds,
        }),
      })
        .then(function () {
          setModalStatus('');
          return refreshAfterModalTiltakChange();
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
          card.querySelectorAll('button').forEach(function (btn) { btn.disabled = false; });
        });
    }

    function deleteModalActionCard(card) {
      const actionId = card.getAttribute('data-action-id');
      if (!actionId) {
        card.remove();
        return Promise.resolve();
      }
      if (!window.confirm('Slette dette tiltaket?')) {
        return Promise.resolve();
      }

      setModalStatus('Sletter…');
      return fetchJson(urlWithId(config.urls.actionDelete, actionId), {
        method: 'POST',
        body: JSON.stringify({ _method: 'DELETE' }),
      })
        .then(function () {
          setModalStatus('');
          return refreshAfterModalTiltakChange();
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        });
    }

    function addModalActionCard() {
      const scenarioIdRaw = document.getElementById('risiko-modal-scenario-id').value;
      if (!scenarioIdRaw) {
        flushScenarioAutosave().then(function () {
          if (document.getElementById('risiko-modal-scenario-id').value) {
            addModalActionCard();
          } else {
            setModalStatus('Skriv uønsket hendelse – scenarioet opprettes automatisk.', true);
          }
        });
        return;
      }
      const container = document.getElementById('risiko-actions-list');
      if (!container) return;
      const card = document.createElement('div');
      card.className = 'risiko-action-card';
      setCardScenarioIds(card, [parseInt(scenarioIdRaw, 10)]);
      card.innerHTML = buildModalActionCardHtml({
        beskrivelse: '',
        ansvarlig: '',
        frist: null,
        status: 'ikke_startet',
        scenario_ids: [parseInt(scenarioIdRaw, 10)],
      }, parseInt(scenarioIdRaw, 10));
      container.appendChild(card);
      captureActionSnapshot(card);
      card.querySelector('.risiko-action-beskrivelse').focus();
      hideLinkActionPicker();
      setModalStatus('');
    }

    function buildTiltakReadOnlyRowHtml(action) {
      const displayId = escapeHtml(action.display_tiltak_id || '–');
      let riskHtml = '-';
      const links = action.risk_links || [];
      if (links.length) {
        riskHtml = links.map(function (link) {
          return '<a href="' + escapeHtml(config.urls.scopePage) + '?edit=' + link.scenario_pk + '">' +
            escapeHtml(link.risk_id) + '</a>';
        }).join(', ');
      }
      return '<td>' + displayId + '</td>' +
        '<td>' + escapeHtml(action.beskrivelse || '').replace(/\n/g, '<br>') + '</td>' +
        '<td>' + riskHtml + '</td>' +
        '<td>' + escapeHtml(action.ansvarlig || '-') + '</td>' +
        '<td>' + escapeHtml(action.frist || '-') + '</td>' +
        '<td>' + escapeHtml(action.status_display || action.status || '-') + '</td>';
    }

    function renderTiltakSection(tiltak) {
      const tbody = document.getElementById('risiko-tiltak-tbody');
      const table = document.getElementById('risiko-tiltak-table');
      const section = document.getElementById('risiko-tiltak-section');
      if (!tbody) return;

      tbody.innerHTML = '';
      (tiltak || []).forEach(function (action) {
        const tr = document.createElement('tr');
        tr.innerHTML = buildTiltakReadOnlyRowHtml(action);
        tbody.appendChild(tr);
      });

      if (table) {
        table.style.display = (tiltak && tiltak.length) ? '' : 'none';
      }
      if (section) {
        let emptyMsg = section.querySelector('.risiko-tiltak-empty-msg');
        if (!tiltak || !tiltak.length) {
          if (!emptyMsg) {
            emptyMsg = document.createElement('p');
            emptyMsg.className = 'text-muted mb-0 risiko-tiltak-empty-msg';
            emptyMsg.textContent = 'Ingen tiltak registrert.';
            section.appendChild(emptyMsg);
          }
          emptyMsg.style.display = '';
        } else if (emptyMsg) {
          emptyMsg.style.display = 'none';
        }
      }
    }

    function pauseFloatThead(tableId) {
      const table = $('#' + tableId);
      if (!table.length || !$.fn.floatThead) {
        return function () {};
      }
      const attached = table.data('floatThead-attached');
      if (attached) {
        table.floatThead('destroy');
      }
      return function () {
        if (attached) {
          table.floatThead({ top: 135 });
        }
      };
    }

    function updateScenarioTiltakColumn(scenarios) {
      const byId = {};
      (scenarios || []).forEach(function (scenario) {
        byId[scenario.id] = scenario.display_tiltak_ids || '–';
      });
      document.querySelectorAll('#risiko-scenarios-tbody tr[data-scenario-id]').forEach(function (row) {
        const id = parseInt(row.getAttribute('data-scenario-id'), 10);
        if (!byId[id]) return;
        const cell = row.cells[7];
        if (cell) cell.textContent = byId[id];
      });
    }

    function applyRefreshData(data, opts) {
      opts = opts || {};
      scopeTiltak = data.tiltak || [];
      scopeScenarios = data.scenarios || [];
      const hasServerRows = document.querySelector('#risiko-scenarios-tbody tr[data-scenario-id]');
      if (opts.keepScenarioRows && hasServerRows) {
        bindScenarioRows();
        updateScenarioTiltakColumn(scopeScenarios);
      } else {
        renderScenariosTable(scopeScenarios);
      }
      renderTiltakSection(scopeTiltak);
    }

    function levelTagHtml(label, cssClass) {
      if (!label || label === '-') return '-';
      const cls = cssClass || 'risk-cell-empty';
      return '<span class="risiko-level-tag ' + escapeHtml(cls) + '">' + escapeHtml(label) + '</span>';
    }

    function renderScenariosTable(scenarios) {
      const resumeFloatThead = pauseFloatThead('risiko-scenarios-table');
      const tbody = document.getElementById('risiko-scenarios-tbody');
      if (!tbody) {
        resumeFloatThead();
        return;
      }
      tbody.innerHTML = '';
      scenarios.forEach(function (scenario) {
        let systemsHtml = '-';
        if (scenario.systemer && scenario.systemer.length) {
          systemsHtml = scenario.systemer.map(function (sys) {
            return '<a href="' + escapeHtml(sys.url) + '" onclick="event.stopPropagation();">' +
              escapeHtml(sys.label) + '</a>';
          }).join(', ');
        }
        const kCss = scenario.konsekvens_css || levelCellClass(scenario.konsekvens_nivaa);
        const sCss = scenario.sannsynlighet_css || levelCellClass(scenario.sannsynlighet_nivaa);
        const rCss = scenario.risiko_css || riskCellClass(scenario.risiko_etikett);
        const resCss = scenario.restrisiko_css || riskCellClass(scenario.restrisiko_etikett);
        const kVal = scenario.konsekvens_label
          || levelLabel(scenario.konsekvens_nivaa, meta && meta.konsekvens_labels);
        const sVal = scenario.sannsynlighet_label
          || levelLabel(scenario.sannsynlighet_nivaa, meta && meta.sannsynlighet_labels);

        const kitHtml = renderKitTags(scenario.kit_tags);

        tbody.insertAdjacentHTML('beforeend',
          '<tr class="risiko-scenario-row" data-scenario-id="' + scenario.id + '" style="cursor:pointer">' +
          '<td>' + escapeHtml(scenario.display_risk_id || '') + '</td>' +
          '<td>' + escapeHtml((scenario.uonsket_hendelse || '').substring(0, 80)) + '</td>' +
          '<td class="risiko-systemer-cell">' + systemsHtml + '</td>' +
          '<td class="risiko-kit-cell">' + kitHtml + '</td>' +
          '<td class="risiko-level-cell">' + levelTagHtml(kVal, kCss) + '</td>' +
          '<td class="risiko-level-cell">' + levelTagHtml(sVal, sCss) + '</td>' +
          '<td class="' + escapeHtml(rCss) + '">' + escapeHtml(scenario.risiko_etikett || '-') + '</td>' +
          '<td>' + escapeHtml(scenario.display_tiltak_ids || '–') + '</td>' +
          '<td class="' + escapeHtml(resCss) + '">' + escapeHtml(scenario.restrisiko_etikett || '-') + '</td></tr>'
        );
      });
      bindScenarioRows();
      resumeFloatThead();
    }

    function refreshTable() {
      return fetchJson(config.urls.scenarios).then(function (data) {
        applyRefreshData(data);
      });
    }

    function bindScenarioRows() {
      const tbody = document.getElementById('risiko-scenarios-tbody');
      if (!tbody || tbody.getAttribute('data-rows-bound') === 'true') {
        return;
      }
      tbody.setAttribute('data-rows-bound', 'true');
      tbody.addEventListener('click', function (e) {
        const row = e.target.closest('.risiko-scenario-row');
        if (!row) return;
        const id = row.getAttribute('data-scenario-id');
        if (id) openModalForEdit(parseInt(id, 10));
      });
    }

    function deleteScenario() {
      const scenarioId = document.getElementById('risiko-modal-scenario-id').value;
      if (!scenarioId) {
        return;
      }
      const displayId = document.getElementById('risiko-scenario-modal-title').textContent.replace(/^Rediger\s+/, '');
      const label = displayId || 'dette scenarioet';
      if (!window.confirm('Er du sikker på at du vil slette ' + label + '?\n\nTiltak som deles med andre scenarioer beholdes.')) {
        return;
      }
      setModalStatus('Sletter…');
      fetchJson(urlWithId(config.urls.scenarioDelete, scenarioId), {
        method: 'POST',
        body: JSON.stringify({ _method: 'DELETE' }),
      })
        .then(function () {
          modalCloseAllowed = true;
          modal.modal('hide');
          return refreshTable();
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        });
    }

    const scopeMetaView = document.getElementById('risiko-scope-meta-view');
    const scopeMetaEdit = document.getElementById('risiko-scope-meta-edit');
    let scopeMetaSnapshot = null;

    function captureScopeMetaSnapshot() {
      scopeMetaSnapshot = {
        title: document.getElementById('risiko-scope-title').value,
        beskrivelse: document.getElementById('risiko-scope-beskrivelse').value,
        sist_revidert: document.getElementById('risiko-scope-revidert').value,
      };
    }

    function restoreScopeMetaSnapshot() {
      if (!scopeMetaSnapshot) return;
      document.getElementById('risiko-scope-title').value = scopeMetaSnapshot.title;
      document.getElementById('risiko-scope-beskrivelse').value = scopeMetaSnapshot.beskrivelse;
      document.getElementById('risiko-scope-revidert').value = scopeMetaSnapshot.sist_revidert;
    }

    function showScopeMetaView() {
      if (scopeMetaView) scopeMetaView.style.display = '';
      if (scopeMetaEdit) scopeMetaEdit.style.display = 'none';
      setScopeStatus('');
    }

    function showScopeMetaEdit() {
      captureScopeMetaSnapshot();
      if (scopeMetaView) scopeMetaView.style.display = 'none';
      if (scopeMetaEdit) scopeMetaEdit.style.display = '';
      setScopeStatus('');
    }

    function updateScopeMetaView(scope) {
      const pageTitle = document.getElementById('risiko-page-title');
      if (pageTitle) pageTitle.textContent = scope.title;

      document.getElementById('risiko-scope-revidert-view').textContent = scope.sist_revidert;
      const beskBlock = document.getElementById('risiko-scope-beskrivelse-block');
      const beskView = document.getElementById('risiko-scope-beskrivelse-view');
      if (beskBlock && beskView) {
        beskBlock.style.display = scope.beskrivelse ? '' : 'none';
        beskView.innerHTML = escapeHtml(scope.beskrivelse || '').replace(/\n/g, '<br>');
      }
    }

    function saveScopeMeta() {
      const payload = {
        title: document.getElementById('risiko-scope-title').value.trim(),
        beskrivelse: document.getElementById('risiko-scope-beskrivelse').value.trim(),
        sist_revidert: document.getElementById('risiko-scope-revidert').value,
      };
      setScopeStatus('Lagrer…');
      fetchJson(config.urls.scopeUpdate, { method: 'PATCH', body: JSON.stringify(payload) })
        .then(function (data) {
          updateScopeMetaView(data.scope);
          captureScopeMetaSnapshot();
          showScopeMetaView();
        })
        .catch(function (err) {
          setScopeStatus(err.message, true);
        });
    }

    document.querySelectorAll('.risiko-level-select').forEach(function (el) {
      el.addEventListener('change', function () {
        updateRiskBadges();
        scheduleScenarioAutosave();
      });
    });

    const modalEl = document.getElementById('risiko-scenario-modal');
    if (modalEl) {
      modalEl.addEventListener('input', function (e) {
        if (e.target.closest('.risiko-action-card')) return;
        if (e.target.id === 'risiko-system-sok') return;
        scheduleScenarioAutosave();
      });
      modalEl.addEventListener('change', function (e) {
        if (e.target.closest('.risiko-action-card')) return;
        if (e.target.id === 'risiko-system-sok') return;
        scheduleScenarioAutosave();
      });
    }

    document.getElementById('risiko-new-scenario').addEventListener('click', openModalForCreate);
    document.getElementById('risiko-delete-scenario').addEventListener('click', deleteScenario);

    const addActionBtn = document.getElementById('risiko-add-action');
    if (addActionBtn) {
      addActionBtn.addEventListener('click', addModalActionCard);
    }

    const linkActionBtn = document.getElementById('risiko-link-action');
    if (linkActionBtn) {
      linkActionBtn.addEventListener('click', showLinkActionPicker);
    }

    const linkActionConfirm = document.getElementById('risiko-link-action-confirm');
    if (linkActionConfirm) {
      linkActionConfirm.addEventListener('click', linkExistingAction);
    }

    const linkActionCancel = document.getElementById('risiko-link-action-cancel');
    if (linkActionCancel) {
      linkActionCancel.addEventListener('click', hideLinkActionPicker);
    }

    const actionsList = document.getElementById('risiko-actions-list');
    if (actionsList) {
      actionsList.addEventListener('input', function (e) {
        const card = e.target.closest('.risiko-action-card');
        if (card) scheduleActionAutosave(card);
      });
      actionsList.addEventListener('change', function (e) {
        const card = e.target.closest('.risiko-action-card');
        if (card) scheduleActionAutosave(card);
      });
      actionsList.addEventListener('click', function (e) {
        const card = e.target.closest('.risiko-action-card');
        if (!card) return;
        if (e.target.classList.contains('risiko-action-unlink')) {
          unlinkModalActionCard(card);
        } else if (e.target.classList.contains('risiko-action-delete')) {
          deleteModalActionCard(card);
        }
      });
    }

    document.getElementById('risiko-system-chips').addEventListener('click', function (e) {
      if (e.target.classList.contains('risiko-system-fjern')) {
        const chip = e.target.closest('[data-id]');
        const id = parseInt(chip.getAttribute('data-id'), 10);
        draftSystems = draftSystems.filter(function (s) { return s.id !== id; });
        renderSystemChips();
        scheduleScenarioAutosave();
      }
    });

    document.getElementById('risiko-system-sok').addEventListener('input', function (e) {
      const q = e.target.value.trim();
      clearTimeout(searchTimer);
      const treff = document.getElementById('risiko-system-sok-treff');
      if (q.length < 2) {
        treff.innerHTML = '';
        return;
      }
      searchTimer = setTimeout(function () {
        fetchJson(config.urls.systemSearch + '?q=' + encodeURIComponent(q))
          .then(function (data) {
            treff.innerHTML = '';
            (data.results || []).forEach(function (sys) {
              if (draftSystems.some(function (s) { return s.id === sys.id; })) return;
              const btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'btn btn-link btn-sm d-block text-left p-0';
              btn.textContent = sys.label;
              btn.addEventListener('click', function () {
                draftSystems.push(sys);
                renderSystemChips();
                document.getElementById('risiko-system-sok').value = '';
                treff.innerHTML = '';
                scheduleScenarioAutosave();
              });
              treff.appendChild(btn);
            });
          });
      }, 250);
    });

    const scopeEditBtn = document.getElementById('risiko-scope-edit');
    if (scopeEditBtn) {
      scopeEditBtn.addEventListener('click', showScopeMetaEdit);
    }

    const scopeCancelBtn = document.getElementById('risiko-scope-cancel');
    if (scopeCancelBtn) {
      scopeCancelBtn.addEventListener('click', function () {
        restoreScopeMetaSnapshot();
        showScopeMetaView();
      });
    }

    const scopeSaveBtn = document.getElementById('risiko-scope-save');
    if (scopeSaveBtn) {
      scopeSaveBtn.addEventListener('click', saveScopeMeta);
    }

    captureScopeMetaSnapshot();

    bindScenarioRows();

    fetchJson(config.urls.meta).then(function (data) {
      meta = data.meta;
      populateMetaChoices();
      return fetchJson(config.urls.scenarios);
    }).then(function (data) {
      applyRefreshData(data, { keepScenarioRows: true });
      if (config.editScenarioId) {
        openModalForEdit(config.editScenarioId);
      }
    }).catch(function (err) {
      setScopeStatus('Kunne ikke laste tabellene: ' + err.message, true);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRisikoEditor);
  } else {
    initRisikoEditor();
  }
})();
