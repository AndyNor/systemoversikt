// Change log:
// 2026-09-25: Owner is a radio group. The label shows the checked choice even before the save returns.
// 2026-09-25: Owner choices are labels in the card. Keyboard activates them the same way as a click.
// 2026-09-25: Cases are cards on two lines. Owner is a button group, not a select.
// 2026-09-25: Free-text status field, and Qualys hit summary after a CVE is saved.
// 2026-09-25: Clear "Lagrer…" when the request finishes. A second save starts only if the user edited again.
// 2026-09-25: Keep relative "sist endret" and the exact timestamp tooltip after autosave.
// 2026-09-25: A new row is saved when the title is filled; owner and CVE may be empty.
// 2026-09-25: Show or hide closed cases when the checkbox changes, without reloading.
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
    var value = el ? el.value : '';
    if (TEXT_FIELDS.indexOf(name) !== -1) {
      value = value.trim();
    }
    if (name === 'cve') {
      value = value.toUpperCase();
    }
    return value;
  }

  function ownerValue(tr) {
    var checked = tr.querySelector('.sak-owner-input:checked');
    return checked ? checked.value : '';
  }

  function payloadOf(tr) {
    var data = {};
    FIELDS.forEach(function (name) {
      if (name === 'tiltakseier') {
        data[name] = ownerValue(tr);
        return;
      }
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

  function syncOwnerButtons(row) {
    row.querySelectorAll('.sak-owner-btn').forEach(function (label) {
      var input = label.querySelector('.sak-owner-input');
      var on = !!(input && input.checked);
      label.classList.toggle('is-selected', on);
    });
  }

  function setOwnerValue(tr, value) {
    var next = value || '';
    tr.querySelectorAll('.sak-owner-input').forEach(function (input) {
      input.checked = input.value === next;
    });
    syncOwnerButtons(tr);
  }

  function renameOwnerGroup(tr) {
    var pk = tr.getAttribute('data-pk');
    if (!pk) return;
    var name = 'tiltakseier-' + pk;
    tr.querySelectorAll('.sak-owner-input').forEach(function (input) {
      input.name = name;
    });
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
      if (name === 'tiltakseier') return;
      var el = tr.querySelector('[data-field="' + name + '"]');
      if (!el || document.activeElement === el) {
        return;
      }
      if (el.value !== data[name] && fieldValue(el, name) === sent[name]) {
        el.value = data[name];
      }
    });
    if (Object.prototype.hasOwnProperty.call(data, 'tiltakseier')) {
      var currentOwner = ownerValue(tr);
      var sentOwner = sent.tiltakseier || '';
      if (currentOwner === sentOwner && currentOwner !== (data.tiltakseier || '')) {
        setOwnerValue(tr, data.tiltakseier);
      } else {
        syncOwnerButtons(tr);
      }
    }
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
    syncOwnerButtons(tr);
    tr.setAttribute('data-pk', String(data.pk));
    tr.removeAttribute('data-new');
    renameOwnerGroup(tr);
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
    tr.hidden = !visLukkede() && rowErLukket(tr);
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
          ? (el.getAttribute('data-suffix-alle') || 'saker')
          : (el.getAttribute('data-suffix-aktive') || 'aktive saker');
        el.textContent = savedVisible + ' ' + suffix + '.';
        el.hidden = false;
      }
    }
    if (empty) {
      empty.hidden = anyVisible;
      if (!anyVisible) {
        empty.textContent = showClosed
          ? (empty.getAttribute('data-tom-alle') || 'Ingen saker.')
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
      var editedSinceSend = payloadJson(tr) !== requestJson;
      applySaved(tr, sent, data);
      rowState.snapshot = payloadJson(tr);
      applyRowVisibility(tr);
      refreshCount(tr.parentNode);
      if (editedSinceSend) {
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

  function rowFromEvent(event) {
    if (!event.target.matches || !event.target.matches('[data-field]')) {
      return null;
    }
    return event.target.closest('[data-sak-row]');
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
      syncOwnerButtons(tr);
    });

    tbody.addEventListener('input', function (event) {
      var tr = rowFromEvent(event);
      if (tr) schedule(table, tr);
    });

    tbody.addEventListener('change', function (event) {
      var ownerInput = event.target.closest && event.target.closest('.sak-owner-input');
      if (ownerInput && tbody.contains(ownerInput)) {
        var ownerRow = ownerInput.closest('[data-sak-row]');
        if (!ownerRow) return;
        syncOwnerButtons(ownerRow);
        flush(table, ownerRow, false);
        return;
      }
      var tr = rowFromEvent(event);
      if (!tr) return;
      if (event.target.getAttribute('data-field') === 'saksstatus') {
        syncStatusClass(event.target);
      }
      flush(table, tr, false);
    });

    // 2026-09-25: A second click on the chosen owner clears it. The first click only checks the radio.
    tbody.addEventListener('mousedown', function (event) {
      var label = event.target.closest && event.target.closest('.sak-owner-btn');
      if (!label || !tbody.contains(label)) return;
      var input = label.querySelector('.sak-owner-input');
      if (!input) return;
      input.setAttribute('data-was-checked', input.checked ? '1' : '0');
    });

    tbody.addEventListener('click', function (event) {
      var label = event.target.closest && event.target.closest('.sak-owner-btn');
      if (!label || !tbody.contains(label)) return;
      var input = label.querySelector('.sak-owner-input');
      if (!input || input.getAttribute('data-was-checked') !== '1') return;
      event.preventDefault();
      input.checked = false;
      var tr = label.closest('[data-sak-row]');
      if (!tr) return;
      syncOwnerButtons(tr);
      flush(table, tr, false);
    });

    tbody.addEventListener('focusout', function (event) {
      var tr = rowFromEvent(event);
      if (!tr) return;
      var name = event.target.getAttribute('data-field');
      if (TEXT_FIELDS.indexOf(name) !== -1) {
        event.target.value = fieldValue(event.target, name);
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
