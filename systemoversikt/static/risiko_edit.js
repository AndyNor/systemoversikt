// Change log:
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
    let draftActions = [];
    let searchTimer = null;

    const modal = $('#risiko-scenario-modal');
    const modalStatus = document.getElementById('risiko-modal-status');
    const scopeStatus = document.getElementById('risiko-scope-status');

    function setModalStatus(msg, isError) {
      if (!modalStatus) return;
      modalStatus.textContent = msg || '';
      modalStatus.className = isError ? 'small mb-2 text-danger' : 'small mb-2 text-muted';
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

    function renderActionRows() {
      const tbody = document.getElementById('risiko-actions-tbody');
      tbody.innerHTML = '';
      draftActions.forEach(function (action, index) {
        const tr = document.createElement('tr');
        tr.innerHTML =
          '<td><input type="number" class="form-control form-control-sm risiko-action-nr" min="1" value="' +
          escapeHtml(action.tiltak_nr || (index + 1)) + '"></td>' +
          '<td><textarea class="form-control form-control-sm risiko-action-beskrivelse" rows="3">' +
          escapeHtml(action.beskrivelse || '') + '</textarea></td>' +
          '<td><input type="text" class="form-control form-control-sm risiko-action-ansvarlig" value="' +
          escapeHtml(action.ansvarlig || '') + '"></td>' +
          '<td><input type="date" class="form-control form-control-sm risiko-action-frist" value="' +
          escapeHtml(action.frist || '') + '"></td>' +
          '<td><select class="form-control form-control-sm risiko-action-status">' +
          statusOptionsHtml(action.status || 'ikke_startet') + '</select></td>' +
          '<td><button type="button" class="btn btn-link btn-sm text-danger risiko-action-fjern">&times;</button></td>';
        if (action.id) {
          tr.setAttribute('data-action-id', action.id);
        }
        tbody.appendChild(tr);
      });
    }

    function collectActionsFromDom() {
      const rows = document.querySelectorAll('#risiko-actions-tbody tr');
      const actions = [];
      rows.forEach(function (row, index) {
        const id = row.getAttribute('data-action-id');
        actions.push({
          id: id ? parseInt(id, 10) : null,
          tiltak_nr: parseInt(row.querySelector('.risiko-action-nr').value, 10) || (index + 1),
          beskrivelse: row.querySelector('.risiko-action-beskrivelse').value.trim(),
          ansvarlig: row.querySelector('.risiko-action-ansvarlig').value.trim(),
          frist: row.querySelector('.risiko-action-frist').value || null,
          status: row.querySelector('.risiko-action-status').value,
        });
      });
      return actions;
    }

    function collectScenarioPayload() {
      function levelVal(id) {
        const v = document.getElementById(id).value;
        return v === '' ? null : parseInt(v, 10);
      }
      return {
        risk_id: document.getElementById('risiko-f-risk-id').value.trim(),
        uonsket_hendelse: document.getElementById('risiko-f-uonsket').value.trim(),
        kit_dimensjoner: document.getElementById('risiko-f-kit').value.trim(),
        arsaker_svakheter: document.getElementById('risiko-f-arsaker').value.trim(),
        eksisterende_tiltak: document.getElementById('risiko-f-eksisterende').value.trim(),
        konsekvens_nivaa: levelVal('risiko-f-konsekvens'),
        sannsynlighet_nivaa: levelVal('risiko-f-sannsynlighet'),
        konsekvens_etter: levelVal('risiko-f-konsekvens-etter'),
        sannsynlighet_etter: levelVal('risiko-f-sannsynlighet-etter'),
        konsekvens_begrunnelse: document.getElementById('risiko-f-konsekvens-begrunnelse').value.trim(),
        sannsynlighetsbegrunnelse: document.getElementById('risiko-f-sannsynlighet-begrunnelse').value.trim(),
        risikobehandling: document.getElementById('risiko-f-risikobehandling').value,
        system_ids: draftSystems.map(function (s) { return s.id; }),
        actions: collectActionsFromDom(),
      };
    }

    function fillScenarioForm(scenario) {
      document.getElementById('risiko-modal-scenario-id').value = scenario ? scenario.id : '';
      document.getElementById('risiko-f-risk-id').value = scenario ? scenario.risk_id : '';
      document.getElementById('risiko-f-kit').value = scenario ? (scenario.kit_dimensjoner || '') : '';
      document.getElementById('risiko-f-uonsket').value = scenario ? (scenario.uonsket_hendelse || '') : '';
      document.getElementById('risiko-f-arsaker').value = scenario ? (scenario.arsaker_svakheter || '') : '';
      document.getElementById('risiko-f-eksisterende').value = scenario ? (scenario.eksisterende_tiltak || '') : '';
      document.getElementById('risiko-f-konsekvens').value = scenario && scenario.konsekvens_nivaa ? scenario.konsekvens_nivaa : '';
      document.getElementById('risiko-f-sannsynlighet').value = scenario && scenario.sannsynlighet_nivaa ? scenario.sannsynlighet_nivaa : '';
      document.getElementById('risiko-f-konsekvens-etter').value = scenario && scenario.konsekvens_etter ? scenario.konsekvens_etter : '';
      document.getElementById('risiko-f-sannsynlighet-etter').value = scenario && scenario.sannsynlighet_etter ? scenario.sannsynlighet_etter : '';
      document.getElementById('risiko-f-konsekvens-begrunnelse').value = scenario ? (scenario.konsekvens_begrunnelse || '') : '';
      document.getElementById('risiko-f-sannsynlighet-begrunnelse').value = scenario ? (scenario.sannsynlighetsbegrunnelse || '') : '';
      document.getElementById('risiko-f-risikobehandling').value = scenario ? (scenario.risikobehandling || '') : '';
      draftSystems = scenario ? (scenario.systemer || []).slice() : [];
      draftActions = scenario ? (scenario.actions || []).map(function (a) {
        return {
          id: a.id,
          tiltak_nr: a.tiltak_nr,
          beskrivelse: a.beskrivelse,
          ansvarlig: a.ansvarlig,
          frist: a.frist,
          status: a.status,
        };
      }) : [];
      renderSystemChips();
      renderActionRows();
      updateRiskBadges();
      document.getElementById('risiko-delete-scenario').style.display = scenario ? '' : 'none';
      document.getElementById('risiko-scenario-modal-title').textContent = scenario
        ? 'Rediger ' + scenario.risk_id
        : 'Nytt scenario';
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

    function scenarioEditUrl(scenarioId) {
      return config.urls.scopePage + '?edit=' + encodeURIComponent(String(scenarioId));
    }

    function renderTiltakSection(scenarios) {
      const section = document.getElementById('risiko-tiltak-section');
      if (!section) return;

      const rows = [];
      scenarios.forEach(function (scenario) {
        (scenario.actions || []).forEach(function (action) {
          rows.push({ scenario: scenario, action: action });
        });
      });

      if (!rows.length) {
        section.innerHTML = '<h5>Tiltak</h5><p class="text-muted mb-0">Ingen tiltak registrert.</p>';
        return;
      }

      let html = '<h5>Tiltak</h5><table class="table table-sm table-bordered excel mb-0"><thead><tr>' +
        '<th style="width:4rem">RiskID</th><th style="width:3rem">#</th><th>Tiltak</th>' +
        '<th style="width:8rem">Ansvarlig</th><th style="width:7rem">Frist</th><th style="width:8rem">Status</th>' +
        '</tr></thead><tbody id="risiko-tiltak-tbody">';

      rows.forEach(function (row) {
        const editUrl = scenarioEditUrl(row.scenario.id);
        html += '<tr><td><a href="' + escapeHtml(editUrl) + '">' + escapeHtml(row.scenario.risk_id) + '</a></td>' +
          '<td>' + escapeHtml(row.action.tiltak_nr) + '</td><td>' +
          escapeHtml(row.action.beskrivelse).replace(/\n/g, '<br>') + '</td><td>' +
          escapeHtml(row.action.ansvarlig || '-') + '</td><td>' +
          escapeHtml(row.action.frist || '-') + '</td><td>' +
          escapeHtml(row.action.status_display || row.action.status) + '</td></tr>';
      });
      html += '</tbody></table>';
      section.innerHTML = html;
    }

    function levelTagHtml(label, cssClass) {
      if (!label || label === '-') return '-';
      const cls = cssClass || 'risk-cell-empty';
      return '<span class="risiko-level-tag ' + escapeHtml(cls) + '">' + escapeHtml(label) + '</span>';
    }

    function renderScenariosTable(scenarios) {
      const tbody = document.getElementById('risiko-scenarios-tbody');
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
          '<td>' + escapeHtml(scenario.risk_id) + '</td>' +
          '<td>' + escapeHtml((scenario.uonsket_hendelse || '').substring(0, 80)) + '</td>' +
          '<td class="risiko-systemer-cell">' + systemsHtml + '</td>' +
          '<td class="risiko-kit-cell">' + kitHtml + '</td>' +
          '<td class="risiko-level-cell">' + levelTagHtml(kVal, kCss) + '</td>' +
          '<td class="risiko-level-cell">' + levelTagHtml(sVal, sCss) + '</td>' +
          '<td class="' + escapeHtml(rCss) + '">' + escapeHtml(scenario.risiko_etikett || '-') + '</td>' +
          '<td>' + escapeHtml(scenario.action_count) + '</td>' +
          '<td class="' + escapeHtml(resCss) + '">' + escapeHtml(scenario.restrisiko_etikett || '-') + '</td></tr>'
        );
      });
      bindScenarioRows();
    }

    function refreshTable() {
      return fetchJson(config.urls.scenarios).then(function (data) {
        renderScenariosTable(data.scenarios);
        renderTiltakSection(data.scenarios);
      });
    }

    function bindScenarioRows() {
      document.querySelectorAll('.risiko-scenario-row').forEach(function (row) {
        row.addEventListener('click', function () {
          const id = row.getAttribute('data-scenario-id');
          if (id) openModalForEdit(parseInt(id, 10));
        });
      });
    }

    function saveScenario() {
      const scenarioId = document.getElementById('risiko-modal-scenario-id').value;
      const payload = collectScenarioPayload();
      const isCreate = !scenarioId;
      const url = isCreate
        ? config.urls.scenarioCreate
        : urlWithId(config.urls.scenarioUpdate, scenarioId);
      const method = isCreate ? 'POST' : 'PATCH';

      setModalStatus('Lagrer…');
      document.getElementById('risiko-save-scenario').disabled = true;

      fetchJson(url, { method: method, body: JSON.stringify(payload) })
        .then(function () {
          setModalStatus('');
          modal.modal('hide');
          return refreshTable();
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        })
        .finally(function () {
          document.getElementById('risiko-save-scenario').disabled = false;
        });
    }

    function deleteScenario() {
      const scenarioId = document.getElementById('risiko-modal-scenario-id').value;
      if (!scenarioId || !window.confirm('Slette dette scenarioet og alle tilhørende tiltak?')) {
        return;
      }
      setModalStatus('Sletter…');
      fetchJson(urlWithId(config.urls.scenarioDelete, scenarioId), {
        method: 'POST',
        body: JSON.stringify({ _method: 'DELETE' }),
      })
        .then(function () {
          modal.modal('hide');
          return refreshTable();
        })
        .catch(function (err) {
          setModalStatus(err.message, true);
        });
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
          setScopeStatus('Lagret.');
          document.getElementById('risiko-scope-revidert-view').textContent = data.scope.sist_revidert;
          const beskView = document.getElementById('risiko-scope-beskrivelse-view');
          if (beskView) {
            beskView.style.display = data.scope.beskrivelse ? '' : 'none';
            beskView.textContent = data.scope.beskrivelse;
          }
        })
        .catch(function (err) {
          setScopeStatus(err.message, true);
        });
    }

    document.querySelectorAll('.risiko-level-select').forEach(function (el) {
      el.addEventListener('change', updateRiskBadges);
    });

    document.getElementById('risiko-new-scenario').addEventListener('click', openModalForCreate);
    document.getElementById('risiko-save-scenario').addEventListener('click', saveScenario);
    document.getElementById('risiko-delete-scenario').addEventListener('click', deleteScenario);
    document.getElementById('risiko-add-action').addEventListener('click', function () {
      draftActions.push({
        tiltak_nr: draftActions.length + 1,
        beskrivelse: '',
        ansvarlig: '',
        frist: null,
        status: 'ikke_startet',
      });
      renderActionRows();
    });

    document.getElementById('risiko-actions-tbody').addEventListener('click', function (e) {
      if (e.target.classList.contains('risiko-action-fjern')) {
        const row = e.target.closest('tr');
        const idx = Array.prototype.indexOf.call(row.parentNode.children, row);
        draftActions.splice(idx, 1);
        renderActionRows();
      }
    });

    document.getElementById('risiko-system-chips').addEventListener('click', function (e) {
      if (e.target.classList.contains('risiko-system-fjern')) {
        const chip = e.target.closest('[data-id]');
        const id = parseInt(chip.getAttribute('data-id'), 10);
        draftSystems = draftSystems.filter(function (s) { return s.id !== id; });
        renderSystemChips();
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
              });
              treff.appendChild(btn);
            });
          });
      }, 250);
    });

    const scopeSaveBtn = document.getElementById('risiko-scope-save');
    if (scopeSaveBtn) {
      scopeSaveBtn.addEventListener('click', saveScopeMeta);
    }

    bindScenarioRows();

    fetchJson(config.urls.meta).then(function (data) {
      meta = data.meta;
      populateMetaChoices();
      if (config.editScenarioId) {
        openModalForEdit(config.editScenarioId);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRisikoEditor);
  } else {
    initRisikoEditor();
  }
})();
