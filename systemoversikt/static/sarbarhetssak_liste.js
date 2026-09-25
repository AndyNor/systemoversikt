// Change log:
// 2026-09-25: A save already in flight must not mark a newer tiltakseier as saved before it is sent.
// 2026-09-25: The closed-cases checkbox shows only closed cases.
// 2026-09-25: Cases are cards on two lines. Owner is a select, not a button group.
// 2026-09-25: Free-text status field, and Qualys hit summary after a CVE is saved.
// 2026-09-25: Clear "Lagrer…" when the request finishes. A second save starts only if the user edited again.
// 2026-09-25: Keep relative "sist endret" and the exact timestamp tooltip after autosave.
// 2026-09-25: A new row is saved when the title is filled; owner and CVE may be empty.
// 2026-09-25: Toggle between open and closed cases when the checkbox changes, without reloading.
// 2026-09-25: Inline edit on the vulnerability-case list with debounced autosave.

(function () {
  'use strict';

  var STATUS_LUKKET = 'lukket';
  var AUTOSAVE_DELAY_MS = 800;
  var SAVED_STATUS_MS = 2000;
  var FIELDS = ['cve', 'tittel', 'tiltakseier', 'saksreferanse', 'saksstatus', 'oppgavestatus'];
  var TEXT_FIELDS = ['cve', 'tittel', 'saksreferanse', 'oppgavestatus'];
  var STATUS_CLASSES = ['sak-status-ny', 'sak-status-under_arbeid', 'sak-status-lukket'];
  var FIELD_LABELS = {
    cve: 'CVE',
    tittel: 'Tittel',
    tiltakseier: 'Tiltakseier',
    saksreferanse: 'Saksreferanse',
    saksstatus: 'Saksstatus',
    oppgavestatus: 'Status',
  };

  var saveState = new WeakMap();

  function state(tr) {
    var current = saveState.get(tr);
    if (!current) {
      current = { timer: null, inflight: null, snapshot: null, sending: null, savedTimer: null, queued: false };
      saveState.set(tr, current);
    }
    return current;
  }

  function fieldValue(el, name) {
    // 2026-09-25: Same read for every control. A select's value is the chosen option key.
    if (el && el.tagName === 'OPTION') {
      el = el.closest('select');
    }
    var value = el && el.value != null ? String(el.value) : '';
    if (TEXT_FIELDS.indexOf(name) !== -1) {
      value = value.trim();
    }
    if (name === 'cve') {
      value = value.toUpperCase();
    }
    return value;
  }

  function payloadOf(tr) {
    var data = {};
    FIELDS.forEach(function (name) {
      data[name] = fieldValue(tr.querySelector('[data-field="' + name + '"]'), name);
    });
    return data;
  }

  function payloadJson(tr) {
    return JSON.stringify(payloadOf(tr));
  }

  function syncStatusClass(select) {
    STATUS_CLASSES.forEach(function (className) {
      select.classList.remove(className);
    });
    if (select.value) {
      select.classList.add('sak-status-' + select.value);
    }
    var row = select.closest('[data-sak-row]');
    if (row) {
      row.setAttribute('data-status', select.value || '');
    }
  }

  function qualysMeta(text) {
    var span = document.createElement('span');
    span.className = 'sak-qualys-meta';
    span.textContent = text;
    return span;
  }

  function renderQualys(tr, qualys) {
    var el = tr.querySelector('[data-qualys]');
    if (!el) return;
    while (el.firstChild) {
      el.removeChild(el.firstChild);
    }
    if (!qualys) return;
    if (!qualys.treff) {
      var none = document.createElement('span');
      none.className = 'sak-qualys-ingen';
      none.textContent = 'Ingen treff i Qualys';
      el.appendChild(none);
      return;
    }
    if (qualys.url) {
      var link = document.createElement('a');
      link.className = 'sak-qualys-link';
      link.href = qualys.url;
      link.textContent = 'Vis i Qualys';
      el.appendChild(link);
    }
    var count = document.createElement('span');
    count.className = 'sak-qualys-count';
    count.textContent = qualys.treff + ' treff';
    el.appendChild(count);
    if (qualys.enheter) {
      el.appendChild(qualysMeta(
        qualys.enheter === 1 ? '1 enhet' : qualys.enheter + ' enheter'
      ));
    }
    if (qualys.alvorlighet) {
      el.appendChild(qualysMeta('alvorlighet ' + qualys.alvorlighet));
    }
    if (qualys.kjent_utnyttet) {
      var flag = document.createElement('span');
      flag.className = 'sak-qualys-flag';
      flag.textContent = 'Kjent utnyttet';
      el.appendChild(flag);
    }
  }

  function setSaveStatus(tr, text, kind) {
    var el = tr.querySelector('.sak-save-status');
    if (!el) return;
    var rowState = state(tr);
    clearTimeout(rowState.savedTimer);
    el.textContent = text || '';
    el.className = 'sak-save-status small';
    if (kind === 'error') {
      el.classList.add('text-danger');
    } else if (kind === 'ok') {
      el.classList.add('text-success');
    } else {
      el.classList.add('text-muted');
    }
    if (kind === 'ok') {
      rowState.savedTimer = setTimeout(function () {
        if (el.textContent === 'Lagret') {
          el.textContent = '';
        }
      }, SAVED_STATUS_MS);
    }
  }

  function clearSavingStatus(tr) {
    var el = tr.querySelector('.sak-save-status');
    if (!el) return;
    if (el.textContent === 'Lagrer…' || el.textContent === 'Lagrer..') {
      el.textContent = '';
    }
  }

  function formatErrors(errors) {
    var parts = [];
    Object.keys(errors).forEach(function (key) {
      var msgs = errors[key];
      var text = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
      var label = FIELD_LABELS[key];
      parts.push(label ? label + ': ' + text : text);
    });
    return parts.join(' ') || 'Kunne ikke lagre.';
  }

  function csrfToken() {
    var el = document.querySelector('#sarbarhetssak-csrf [name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  function saveUrl(table, tr) {
    var pk = tr.getAttribute('data-pk');
    if (!pk) {
      return table.getAttribute('data-create-url');
    }
    return table.getAttribute('data-update-url').replace(/\/0\/lagre\/$/, '/' + pk + '/lagre/');
  }

  function readJson(response) {
    return response.text().then(function (text) {
      var data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (e) {
          var parseError = new Error('Sesjonen er utløpt. Last siden på nytt.');
          parseError.sessionExpired = true;
          throw parseError;
        }
      }
      if (response.status === 401 || (data && data.error === 'session_expired')) {
        var expired = new Error('Sesjonen er utløpt. Last siden på nytt.');
        expired.sessionExpired = true;
        throw expired;
      }
      if (!response.ok || !data || data.ok === false) {
        var message = 'Kunne ikke lagre.';
        if (data && data.errors) {
          message = formatErrors(data.errors);
        } else if (data && data.error) {
          message = data.error;
        }
        var fail = new Error(message);
        fail.data = data;
        throw fail;
      }
      return data;
    });
  }

  function applySaved(tr, sent, data) {
    FIELDS.forEach(function (name) {
      var el = tr.querySelector('[data-field="' + name + '"]');
      if (!el || document.activeElement === el) {
        return;
      }
      if (el.value !== data[name] && fieldValue(el, name) === sent[name]) {
        el.value = data[name];
      }
    });
    var status = tr.querySelector('[data-field="saksstatus"]');
    if (status) {
      syncStatusClass(status);
    }
    var updated = tr.querySelector('.sak-updated');
    if (updated) {
      updated.textContent = data.sist_oppdatert || '';
      updated.title = data.sist_oppdatert_tidspunkt || '';
    }
    var uke = tr.querySelector('.sak-uke');
    if (uke) {
      uke.textContent = data.lagt_til_uke || '';
    }
    if (Object.prototype.hasOwnProperty.call(data, 'qualys')) {
      renderQualys(tr, data.qualys);
    }
    tr.setAttribute('data-pk', String(data.pk));
    tr.removeAttribute('data-new');
  }

  function missingRequired(payload) {
    return !payload.tittel;
  }

  function visLukkede() {
    var box = document.getElementById('sarbarhetssak-vis-lukkede');
    return !!(box && box.checked);
  }

  function rowErLukket(tr) {
    var status = tr.querySelector('[data-field="saksstatus"]');
    return !!(status && status.value === STATUS_LUKKET);
  }

  function applyRowVisibility(tr) {
    if (tr.getAttribute('data-new') === '1') {
      tr.hidden = false;
      return;
    }
    var lukket = rowErLukket(tr);
    tr.hidden = visLukkede() ? !lukket : lukket;
  }

  function syncFilterUrl(showClosed) {
    if (!window.history || !window.URLSearchParams) return;
    var params = new URLSearchParams(window.location.search);
    if (showClosed) {
      params.set('vis_lukkede', '1');
    } else {
      params.delete('vis_lukkede');
    }
    var query = params.toString();
    var next = window.location.pathname + (query ? '?' + query : '') + window.location.hash;
    history.replaceState(null, '', next);
  }

  function refreshCount(tbody) {
    var el = document.getElementById('sarbarhetssak-antall');
    var empty = document.getElementById('sarbarhetssak-tom');
    var savedVisible = 0;
    var anyVisible = false;
    tbody.querySelectorAll('[data-sak-row]').forEach(function (tr) {
      if (tr.hidden) return;
      anyVisible = true;
      if (tr.getAttribute('data-pk')) {
        savedVisible += 1;
      }
    });
    var showClosed = visLukkede();
    if (el) {
      if (savedVisible < 1) {
        el.hidden = true;
      } else {
        var suffix = showClosed
          ? (el.getAttribute('data-suffix-lukkede') || 'lukkede saker')
          : (el.getAttribute('data-suffix-aktive') || 'aktive saker');
        el.textContent = savedVisible + ' ' + suffix + '.';
        el.hidden = false;
      }
    }
    if (empty) {
      empty.hidden = anyVisible;
      if (!anyVisible) {
        empty.textContent = showClosed
          ? (empty.getAttribute('data-tom-lukkede') || 'Ingen lukkede saker.')
          : (empty.getAttribute('data-tom-aktive') || 'Ingen aktive saker.');
      }
    }
  }

  function applyLukketFilter(tbody) {
    var showClosed = visLukkede();
    tbody.querySelectorAll('[data-sak-row]').forEach(applyRowVisibility);
    refreshCount(tbody);
    syncFilterUrl(showClosed);
  }

  function flush(table, tr, keepalive) {
    var rowState = state(tr);
    clearTimeout(rowState.timer);
    rowState.timer = null;
    var payload = payloadOf(tr);
    if (tr.getAttribute('data-new') === '1' && missingRequired(payload)) {
      if (!keepalive && (payload.cve || payload.tittel || payload.tiltakseier || payload.saksreferanse || payload.oppgavestatus)) {
        setSaveStatus(tr, 'Fyll inn tittel.', 'muted');
      }
      return Promise.resolve();
    }
    var json = JSON.stringify(payload);
    if (json === rowState.snapshot) {
      // 2026-09-25: Follow-up flush with nothing new. Replace a leftover "Lagrer…".
      if (!rowState.inflight && !keepalive) {
        var stuck = tr.querySelector('.sak-save-status');
        if (stuck && (stuck.textContent === 'Lagrer…' || stuck.textContent === 'Lagrer..')) {
          setSaveStatus(tr, 'Lagret', 'ok');
        }
      }
      return Promise.resolve();
    }
    if (rowState.inflight) {
      if (json !== rowState.sending) {
        rowState.queued = true;
      }
      return rowState.inflight;
    }
    // 2026-09-25: Lock before the status text changes, so a sync focusout cannot start a second request.
    rowState.inflight = {};
    rowState.sending = json;
    if (!keepalive) {
      setSaveStatus(tr, 'Lagrer…', 'muted');
    }
    var sent = payload;
    var requestJson = json;
    var outcome = null;
    var outcomeError = null;
    var promise = fetch(saveUrl(table, tr), {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: !!keepalive,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: json,
    }).then(readJson).then(function (data) {
      applySaved(tr, sent, data);
      // 2026-09-25: Remember what was sent. A newer owner choice must still be posted.
      rowState.snapshot = requestJson;
      applyRowVisibility(tr);
      refreshCount(tr.parentNode);
      if (payloadJson(tr) !== requestJson) {
        rowState.queued = true;
      }
      outcome = 'ok';
    }).catch(function (err) {
      outcome = 'error';
      outcomeError = err;
    }).then(function () {
      var again = rowState.queued;
      rowState.queued = false;
      rowState.inflight = null;
      rowState.sending = null;
      if (again) {
        return flush(table, tr, false);
      }
      if (keepalive) {
        return null;
      }
      if (outcome === 'ok') {
        setSaveStatus(tr, 'Lagret', 'ok');
      } else if (outcome === 'error') {
        setSaveStatus(tr, (outcomeError && outcomeError.message) || 'Kunne ikke lagre.', 'error');
      } else {
        clearSavingStatus(tr);
      }
      return null;
    });
    rowState.inflight = promise;
    return promise;
  }

  function schedule(table, tr) {
    var rowState = state(tr);
    clearTimeout(rowState.timer);
    rowState.timer = setTimeout(function () {
      rowState.timer = null;
      flush(table, tr, false);
    }, AUTOSAVE_DELAY_MS);
  }

  function fieldFromEvent(event) {
    if (!event.target || !event.target.closest) return null;
    var field = event.target.closest('[data-field]');
    if (!field || field.disabled) return null;
    return field;
  }

  function rowFromEvent(event) {
    var field = fieldFromEvent(event);
    if (!field) return null;
    return field.closest('[data-sak-row]');
  }

  function init() {
    var table = document.getElementById('sarbarhetssak-tabell');
    var tbody = document.getElementById('sarbarhetssak-rader');
    if (!table || !tbody) return;

    tbody.querySelectorAll('[data-sak-row]').forEach(function (tr) {
      state(tr).snapshot = payloadJson(tr);
      var status = tr.querySelector('[data-field="saksstatus"]');
      if (status) {
        syncStatusClass(status);
      }
    });

    tbody.addEventListener('input', function (event) {
      var tr = rowFromEvent(event);
      if (tr) schedule(table, tr);
    });

    tbody.addEventListener('change', function (event) {
      var field = fieldFromEvent(event);
      var tr = field && field.closest('[data-sak-row]');
      if (!field || !tr || !tbody.contains(tr)) return;
      if (field.getAttribute('data-field') === 'saksstatus') {
        syncStatusClass(field);
      }
      flush(table, tr, false);
    });

    tbody.addEventListener('focusout', function (event) {
      var field = fieldFromEvent(event);
      var tr = field && field.closest('[data-sak-row]');
      if (!field || !tr || !tbody.contains(tr)) return;
      var name = field.getAttribute('data-field');
      if (TEXT_FIELDS.indexOf(name) !== -1) {
        field.value = fieldValue(field, name);
      }
      if (event.relatedTarget && tr.contains(event.relatedTarget)) return;
      flush(table, tr, false);
    });

    var visLukkedeInput = document.getElementById('sarbarhetssak-vis-lukkede');
    if (visLukkedeInput) {
      visLukkedeInput.addEventListener('change', function () {
        applyLukketFilter(tbody);
      });
    }

    var addButton = document.getElementById('sarbarhetssak-ny');
    var mal = document.getElementById('sarbarhetssak-ny-mal');
    if (addButton && mal) {
      addButton.addEventListener('click', function () {
        var pending = tbody.querySelector('[data-new="1"]');
        if (pending) {
          var pendingTitle = pending.querySelector('[data-field="tittel"]');
          if (pendingTitle) pendingTitle.focus();
          return;
        }
        var row = mal.content.firstElementChild.cloneNode(true);
        tbody.insertBefore(row, tbody.firstChild);
        var empty = document.getElementById('sarbarhetssak-tom');
        if (empty) empty.hidden = true;
        var title = row.querySelector('[data-field="tittel"]');
        if (title) title.focus();
      });
    }

    window.addEventListener('pagehide', function () {
      tbody.querySelectorAll('[data-sak-row]').forEach(function (tr) {
        flush(table, tr, true);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
