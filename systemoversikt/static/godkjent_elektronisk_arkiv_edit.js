/* Change log:
 * 2026-11-04: Support lagrer_ikke_dokumentasjon checkbox and warning banner.
 * 2026-10-12: Inline editor for GodkjentElektroniskArkiv on system details.
 */
(function () {
  function getCsrfToken(config) {
    if (config && config.csrf) {
      return config.csrf;
    }
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function setViewMode(root, editing) {
    var viewEl = root.querySelector('[data-gea-view]');
    var editEl = root.querySelector('[data-gea-edit]');
    if (viewEl) {
      viewEl.hidden = editing;
    }
    if (editEl) {
      editEl.hidden = !editing;
    }
  }

  function renderView(root, data) {
    var statusEl = root.querySelector('[data-gea-status]');
    var infoEl = root.querySelector('[data-gea-info]');
    var henvisningEl = root.querySelector('[data-gea-henvisning-view]');
    var lagrerIkkeEl = root.querySelector('[data-gea-lagrer-ikke]');
    var godkjent = !!data.godkjent;
    var dato = data.dato_godkjent_elektronisk_arkiv || '';
    var henvisning = data.henvisning || '';
    var lagrerIkke = !!data.lagrer_ikke_dokumentasjon;

    if (statusEl) {
      if (godkjent) {
        var datoTekst = dato
          ? ' (' + dato + ')'
          : ' (dato for godkjenning er ikke registrert)';
        statusEl.className =
          'system-detalj-arkiv-integrasjon system-detalj-arkiv-integrasjon--ja';
        statusEl.innerHTML =
          '<span class="system-detalj-arkiv-integrasjon-symbol" aria-hidden="true">🗁</span>' +
          '<span>Systemet er godkjent som elektronisk arkiv' +
          datoTekst +
          '</span>';
      } else {
        statusEl.className =
          'system-detalj-arkiv-integrasjon system-detalj-arkiv-integrasjon--nei';
        statusEl.innerHTML =
          '<span class="system-detalj-arkiv-integrasjon-symbol" aria-hidden="true">⚠</span>' +
          '<span>Systemet er ikke godkjent som elektronisk arkiv</span>';
      }
    }
    if (infoEl) {
      infoEl.hidden = !godkjent;
    }
    if (henvisningEl) {
      if (henvisning) {
        henvisningEl.hidden = false;
        henvisningEl.textContent = 'Henvisning: ' + henvisning;
      } else {
        henvisningEl.hidden = true;
        henvisningEl.textContent = '';
      }
    }
    if (lagrerIkkeEl) {
      lagrerIkkeEl.hidden = !lagrerIkke;
    }
  }

  function fillForm(root, data) {
    var godkjentInput = root.querySelector('[data-gea-input-godkjent]');
    var datoInput = root.querySelector('[data-gea-input-dato]');
    var henvisningInput = root.querySelector('[data-gea-input-henvisning]');
    var lagrerIkkeInput = root.querySelector('[data-gea-input-lagrer-ikke]');
    if (godkjentInput) {
      godkjentInput.checked = !!data.godkjent;
    }
    if (datoInput) {
      datoInput.value = data.dato_godkjent_elektronisk_arkiv || '';
    }
    if (henvisningInput) {
      henvisningInput.value = data.henvisning || '';
    }
    if (lagrerIkkeInput) {
      lagrerIkkeInput.checked = !!data.lagrer_ikke_dokumentasjon;
    }
  }

  function readForm(root) {
    var godkjentInput = root.querySelector('[data-gea-input-godkjent]');
    var datoInput = root.querySelector('[data-gea-input-dato]');
    var henvisningInput = root.querySelector('[data-gea-input-henvisning]');
    var lagrerIkkeInput = root.querySelector('[data-gea-input-lagrer-ikke]');
    return {
      godkjent: !!(godkjentInput && godkjentInput.checked),
      dato_godkjent_elektronisk_arkiv: datoInput ? datoInput.value : '',
      henvisning: henvisningInput ? henvisningInput.value : '',
      lagrer_ikke_dokumentasjon: !!(lagrerIkkeInput && lagrerIkkeInput.checked),
    };
  }

  function setStatus(root, message, isError) {
    var status = root.querySelector('[data-gea-save-status]');
    if (!status) {
      return;
    }
    status.textContent = message || '';
    status.classList.toggle('text-danger', !!isError);
  }

  window.initGodkjentElektroniskArkivEditor = function (config) {
    var root = document.getElementById(config.rootId || 'gea-panel');
    if (!root) {
      return;
    }

    var state = {
      godkjent: !!config.godkjent,
      dato_godkjent_elektronisk_arkiv: config.dato_godkjent_elektronisk_arkiv || '',
      henvisning: config.henvisning || '',
      lagrer_ikke_dokumentasjon: !!config.lagrer_ikke_dokumentasjon,
    };

    renderView(root, state);
    fillForm(root, state);
    setViewMode(root, false);

    var toggleBtn = root.querySelector('[data-gea-toggle]');
    var cancelBtn = root.querySelector('[data-gea-cancel]');
    var saveBtn = root.querySelector('[data-gea-save]');

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        fillForm(root, state);
        setStatus(root, '');
        setViewMode(root, true);
      });
    }
    if (cancelBtn) {
      cancelBtn.addEventListener('click', function () {
        fillForm(root, state);
        setStatus(root, '');
        setViewMode(root, false);
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var payload = readForm(root);
        setStatus(root, 'Lagrer…');
        saveBtn.disabled = true;
        fetch(config.urlSave, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(config),
          },
          body: JSON.stringify(payload),
        })
          .then(function (response) {
            return response.json().then(function (body) {
              return { ok: response.ok, body: body };
            });
          })
          .then(function (result) {
            saveBtn.disabled = false;
            if (!result.ok || !result.body || !result.body.ok) {
              setStatus(root, 'Kunne ikke lagre.', true);
              return;
            }
            state = {
              godkjent: !!result.body.godkjent,
              dato_godkjent_elektronisk_arkiv:
                result.body.dato_godkjent_elektronisk_arkiv || '',
              henvisning: result.body.henvisning || '',
              lagrer_ikke_dokumentasjon: !!result.body.lagrer_ikke_dokumentasjon,
            };
            renderView(root, state);
            fillForm(root, state);
            setStatus(root, 'Lagret.');
            setViewMode(root, false);
          })
          .catch(function () {
            saveBtn.disabled = false;
            setStatus(root, 'Kunne ikke lagre.', true);
          });
      });
    }
  };
})();
