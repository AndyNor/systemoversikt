// Change log:
// 2026-10-15: Toggle labels Rediger/Avbryt for button-style edit controls.
// 2026-10-15: Inline editors for SystemBruk Initiell registrering and Vurderinger on bruksdetaljer.

(function () {
  'use strict';

  function getCsrfToken(config) {
    if (config && config.csrf) {
      return config.csrf;
    }
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function escapeHtml(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function nl2br(text) {
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  function renderAnsvarligChip(ansvarlig) {
    const style = ansvarlig.deaktivert ? 'text-decoration: line-through;' : '';
    return (
      '<span class="badge badge-light rolle-chip mr-1 mb-1" data-id="' + ansvarlig.id + '">' +
      '<a href="' + escapeHtml(ansvarlig.url || '#') + '" style="' + style + '">' +
      escapeHtml(ansvarlig.label) +
      '</a> ' +
      '<button type="button" class="btn btn-link btn-sm p-0 ml-1 sb-fjern" aria-label="Fjern">&times;</button>' +
      '</span>'
    );
  }

  function renderAnsvarligView(ansvarlige) {
    if (!ansvarlige || !ansvarlige.length) {
      return '<span style="background-color: #ffacac">Mangler</span><br>';
    }
    return ansvarlige
      .map(function (a) {
        const style = a.deaktivert ? 'text-decoration: line-through;' : '';
        return (
          '👤 <a href="' +
          escapeHtml(a.url || '#') +
          '" style="' +
          style +
          '">' +
          escapeHtml(a.label) +
          '</a><br>'
        );
      })
      .join('');
  }

  function displayOrDash(value) {
    if (value === null || value === undefined || value === '') {
      return '-';
    }
    return String(value);
  }

  window.initSystembrukEditor = function initSystembrukEditor(config) {
    if (!config) {
      return;
    }
    const csrf = getCsrfToken(config);
    let initiell = config.initiell || {};
    let vurderinger = config.vurderinger || {};
    const m2mCache = {};
    let searchTimer = null;

    function setStatus(el, message, isError) {
      if (!el) {
        return;
      }
      el.textContent = message || '';
      el.className = isError ? 'text-danger small' : 'text-muted small';
    }

    function syncM2mCacheFromInitiell() {
      ['systemeier_kontaktpersoner_referanse', 'systemforvalter_kontaktpersoner_referanse'].forEach(
        function (field) {
          m2mCache[field] = {};
          (initiell[field] || []).forEach(function (a) {
            m2mCache[field][a.id] = a;
          });
        }
      );
    }
    syncM2mCacheFromInitiell();

    function currentM2mIds(field) {
      const row = document.querySelector('.sb-m2m-edit[data-field="' + field + '"]');
      if (!row) {
        return [];
      }
      const ids = [];
      row.querySelectorAll('.rolle-chip').forEach(function (chip) {
        ids.push(parseInt(chip.getAttribute('data-id'), 10));
      });
      return ids;
    }

    function fillInitiellForm() {
      document.getElementById('sb-edit-ibruk').checked = !!initiell.ibruk;
      document.getElementById('sb-edit-tatt_i_bruk').value = initiell.tatt_i_bruk || '';
      document.getElementById('sb-edit-avsluttet').value = initiell.avsluttet || '';
      document.getElementById('sb-edit-kommentar').value = initiell.kommentar || '';
      document.getElementById('sb-edit-antall_brukere').value =
        initiell.antall_brukere === null || initiell.antall_brukere === undefined
          ? ''
          : initiell.antall_brukere;
      ['systemeier_kontaktpersoner_referanse', 'systemforvalter_kontaktpersoner_referanse'].forEach(
        function (field) {
          const row = document.querySelector('.sb-m2m-edit[data-field="' + field + '"]');
          if (!row) {
            return;
          }
          row.querySelector('.sb-ansvarlig-sok').value = '';
          row.querySelector('.sb-ansvarlig-treff').innerHTML = '';
          const list = row.querySelector('.sb-ansvarlige-list');
          list.innerHTML = '';
          (initiell[field] || []).forEach(function (a) {
            m2mCache[field][a.id] = a;
            list.insertAdjacentHTML('beforeend', renderAnsvarligChip(a));
          });
        }
      );
    }

    function refreshInitiellView() {
      document.getElementById('sb-view-ibruk').textContent = initiell.ibruk ? 'Ja' : 'Nei';
      document.getElementById('sb-view-tatt_i_bruk').textContent = displayOrDash(initiell.tatt_i_bruk);
      document.getElementById('sb-view-avsluttet').textContent = displayOrDash(initiell.avsluttet);
      const kommentarEl = document.getElementById('sb-view-kommentar');
      if (initiell.kommentar) {
        kommentarEl.innerHTML = nl2br(initiell.kommentar);
      } else {
        kommentarEl.textContent = '-';
      }
      document.getElementById('sb-view-antall_brukere').textContent = displayOrDash(
        initiell.antall_brukere
      );
      document.getElementById('sb-view-systemeier_kontaktpersoner_referanse').innerHTML =
        renderAnsvarligView(initiell.systemeier_kontaktpersoner_referanse);
      document.getElementById('sb-view-systemforvalter_kontaktpersoner_referanse').innerHTML =
        renderAnsvarligView(initiell.systemforvalter_kontaktpersoner_referanse);
      if (initiell.sist_oppdatert_display) {
        document.getElementById('sb-view-sist_oppdatert').textContent =
          initiell.sist_oppdatert_display;
      }
    }

    function setInitiellToggleLabel(editing) {
      const toggle = document.getElementById('sb-initiell-toggle');
      if (!toggle) {
        return;
      }
      toggle.textContent = editing ? 'Avbryt' : 'Rediger';
    }

    function setVurderingerToggleLabel(editing) {
      const toggle = document.getElementById('sb-vurderinger-toggle');
      if (!toggle) {
        return;
      }
      toggle.textContent = editing ? 'Avbryt' : 'Rediger';
    }

    function openInitiellEdit() {
      fillInitiellForm();
      document.getElementById('sb-initiell-view').hidden = true;
      document.getElementById('sb-initiell-edit').hidden = false;
      setInitiellToggleLabel(true);
      setStatus(document.getElementById('sb-initiell-status'), '');
    }

    function closeInitiellEdit() {
      fillInitiellForm();
      document.getElementById('sb-initiell-edit').hidden = true;
      document.getElementById('sb-initiell-view').hidden = false;
      setInitiellToggleLabel(false);
      setStatus(document.getElementById('sb-initiell-status'), '');
    }

    function fillVurderingerForm() {
      [
        'strategisk_egnethet',
        'teknisk_egnethet',
        'funksjonell_egnethet',
        'konfidensialitetsvurdering',
        'integritetsvurdering',
        'tilgjengelighetsvurdering',
      ].forEach(function (field) {
        const el = document.getElementById('sb-edit-' + field);
        if (!el) {
          return;
        }
        const val = vurderinger[field];
        el.value = val === null || val === undefined ? '' : String(val);
      });
      document.getElementById('sb-edit-risikovurdering_tekst').value =
        vurderinger.risikovurdering_tekst || '';
      document.getElementById('sb-edit-url_risikovurdering').value =
        vurderinger.url_risikovurdering || '';
      document.getElementById('sb-edit-dato_sist_ros').value = vurderinger.dato_sist_ros || '';
    }

    function refreshVurderingerView() {
      function setText(id, value) {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = displayOrDash(value);
        }
      }
      setText('sb-view-strategisk_egnethet', vurderinger.strategisk_egnethet_display);
      setText('sb-view-teknisk_egnethet', vurderinger.teknisk_egnethet_display);
      setText('sb-view-funksjonell_egnethet', vurderinger.funksjonell_egnethet_display);
      setText(
        'sb-view-konfidensialitetsvurdering',
        vurderinger.konfidensialitetsvurdering_display
      );
      setText('sb-view-integritetsvurdering', vurderinger.integritetsvurdering_display);
      setText(
        'sb-view-tilgjengelighetsvurdering',
        vurderinger.tilgjengelighetsvurdering_display
      );
      const tekstEl = document.getElementById('sb-view-risikovurdering_tekst');
      if (tekstEl) {
        tekstEl.textContent = displayOrDash(vurderinger.risikovurdering_tekst);
      }
      const urlEl = document.getElementById('sb-view-url_risikovurdering');
      if (urlEl) {
        if (vurderinger.url_risikovurdering) {
          urlEl.innerHTML =
            '<a href="' +
            escapeHtml(vurderinger.url_risikovurdering) +
            '">Link til risikovurdering</a>';
        } else {
          urlEl.textContent = '-';
        }
      }
      const rosEl = document.getElementById('sb-view-dato_sist_ros');
      if (rosEl) {
        rosEl.textContent = vurderinger.dato_sist_ros_display
          ? vurderinger.dato_sist_ros_display
          : '-';
      }
    }

    function openVurderingerEdit() {
      fillVurderingerForm();
      document.getElementById('sb-vurderinger-view').hidden = true;
      document.getElementById('sb-vurderinger-edit').hidden = false;
      setVurderingerToggleLabel(true);
      setStatus(document.getElementById('sb-vurderinger-status'), '');
    }

    function closeVurderingerEdit() {
      fillVurderingerForm();
      document.getElementById('sb-vurderinger-edit').hidden = true;
      document.getElementById('sb-vurderinger-view').hidden = false;
      setVurderingerToggleLabel(false);
      setStatus(document.getElementById('sb-vurderinger-status'), '');
    }

    function ensureAnsvarlig(item) {
      if (!item.create) {
        return Promise.resolve({
          id: item.id,
          label: item.label,
          url: item.url,
          deaktivert: !!item.deaktivert,
        });
      }
      if (!config.canAddAnsvarlig) {
        return Promise.reject(new Error('Mangler rettighet til å opprette ansvarlig'));
      }
      return fetch(config.urlCreate, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
        },
        body: JSON.stringify({ user_pk: item.user_pk }),
      }).then(function (response) {
        if (!response.ok) {
          throw new Error('Kunne ikke opprette ansvarlig');
        }
        return response.json();
      });
    }

    const initiellPanel = document.getElementById('sb-initiell-panel');
    if (initiellPanel) {
      document.getElementById('sb-initiell-toggle').addEventListener('click', function () {
        const edit = document.getElementById('sb-initiell-edit');
        if (edit.hidden) {
          openInitiellEdit();
        } else {
          closeInitiellEdit();
        }
      });
      document.getElementById('sb-initiell-avbryt').addEventListener('click', closeInitiellEdit);

      initiellPanel.addEventListener('click', function (event) {
        const removeBtn = event.target.closest('.sb-fjern');
        if (removeBtn) {
          const chip = removeBtn.closest('.rolle-chip');
          if (chip) {
            chip.remove();
          }
          return;
        }
        const pickBtn = event.target.closest('.sb-pick');
        if (pickBtn) {
          const row = pickBtn.closest('.sb-m2m-edit');
          const field = row.getAttribute('data-field');
          const payload = {
            create: pickBtn.getAttribute('data-create') === '1',
            user_pk: pickBtn.getAttribute('data-user-pk')
              ? parseInt(pickBtn.getAttribute('data-user-pk'), 10)
              : null,
            id: pickBtn.getAttribute('data-id')
              ? parseInt(pickBtn.getAttribute('data-id'), 10)
              : null,
            label: pickBtn.getAttribute('data-label') || '',
            url: pickBtn.getAttribute('data-url') || '#',
            deaktivert: pickBtn.getAttribute('data-deaktivert') === '1',
          };
          ensureAnsvarlig(payload)
            .then(function (ansvarlig) {
              m2mCache[field][ansvarlig.id] = ansvarlig;
              const ids = currentM2mIds(field);
              if (ids.indexOf(ansvarlig.id) === -1) {
                row
                  .querySelector('.sb-ansvarlige-list')
                  .insertAdjacentHTML('beforeend', renderAnsvarligChip(ansvarlig));
              }
              row.querySelector('.sb-ansvarlig-sok').value = '';
              row.querySelector('.sb-ansvarlig-treff').innerHTML = '';
            })
            .catch(function (err) {
              setStatus(
                document.getElementById('sb-initiell-status'),
                err.message || 'Feil',
                true
              );
            });
        }
      });

      initiellPanel.addEventListener('input', function (event) {
        const input = event.target.closest('.sb-ansvarlig-sok');
        if (!input) {
          return;
        }
        const row = input.closest('.sb-m2m-edit');
        const hits = row.querySelector('.sb-ansvarlig-treff');
        const q = input.value.trim();
        clearTimeout(searchTimer);
        if (q.length < 2) {
          hits.innerHTML = '';
          return;
        }
        searchTimer = setTimeout(function () {
          const exclude = currentM2mIds(row.getAttribute('data-field')).join(',');
          const url =
            config.urlSearch +
            '?q=' +
            encodeURIComponent(q) +
            '&exclude_ids=' +
            encodeURIComponent(exclude);
          fetch(url, { credentials: 'same-origin' })
            .then(function (response) {
              if (!response.ok) {
                throw new Error('Søk feilet');
              }
              return response.json();
            })
            .then(function (data) {
              hits.innerHTML = (data.results || [])
                .map(function (item) {
                  if (item.create) {
                    return (
                      '<button type="button" class="btn btn-link btn-sm sb-pick" data-create="1" data-user-pk="' +
                      item.user_pk +
                      '" data-label="' +
                      escapeHtml(item.label) +
                      '">+ Opprett «' +
                      escapeHtml(item.label) +
                      '»</button>'
                    );
                  }
                  return (
                    '<button type="button" class="btn btn-link btn-sm sb-pick" data-id="' +
                    item.id +
                    '" data-label="' +
                    escapeHtml(item.label) +
                    '" data-url="' +
                    escapeHtml(item.url || '#') +
                    '" data-deaktivert="' +
                    (item.deaktivert ? '1' : '0') +
                    '">' +
                    escapeHtml(item.label) +
                    '</button>'
                  );
                })
                .join('');
            })
            .catch(function () {
              hits.innerHTML = '<span class="text-danger small">Søk feilet</span>';
            });
        }, 250);
      });

      document.getElementById('sb-initiell-lagre').addEventListener('click', function () {
        const statusEl = document.getElementById('sb-initiell-status');
        setStatus(statusEl, 'Lagrer…');
        const payload = {
          ibruk: document.getElementById('sb-edit-ibruk').checked,
          tatt_i_bruk: document.getElementById('sb-edit-tatt_i_bruk').value,
          avsluttet: document.getElementById('sb-edit-avsluttet').value,
          kommentar: document.getElementById('sb-edit-kommentar').value,
          antall_brukere: document.getElementById('sb-edit-antall_brukere').value,
          systemeier_kontaktpersoner_referanse: currentM2mIds(
            'systemeier_kontaktpersoner_referanse'
          ),
          systemforvalter_kontaktpersoner_referanse: currentM2mIds(
            'systemforvalter_kontaktpersoner_referanse'
          ),
        };
        fetch(config.urlSaveInitiell, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
          },
          body: JSON.stringify(payload),
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { ok: response.ok, data: data };
            });
          })
          .then(function (result) {
            if (!result.ok || !result.data.ok) {
              throw new Error(result.data.error || 'Lagring feilet');
            }
            initiell = result.data.initiell;
            syncM2mCacheFromInitiell();
            refreshInitiellView();
            closeInitiellEdit();
            setStatus(statusEl, 'Lagret');
          })
          .catch(function (err) {
            setStatus(statusEl, err.message || 'Lagring feilet', true);
          });
      });
    }

    const vurderingerPanel = document.getElementById('sb-vurderinger-panel');
    if (vurderingerPanel) {
      document.getElementById('sb-vurderinger-toggle').addEventListener('click', function () {
        const edit = document.getElementById('sb-vurderinger-edit');
        if (edit.hidden) {
          openVurderingerEdit();
        } else {
          closeVurderingerEdit();
        }
      });
      document
        .getElementById('sb-vurderinger-avbryt')
        .addEventListener('click', closeVurderingerEdit);

      const nowBtn = document.getElementById('sb-edit-dato_sist_ros-now');
      if (nowBtn) {
        nowBtn.addEventListener('click', function () {
          const now = new Date();
          const pad = function (n) {
            return n < 10 ? '0' + n : String(n);
          };
          const local =
            now.getFullYear() +
            '-' +
            pad(now.getMonth() + 1) +
            '-' +
            pad(now.getDate()) +
            'T' +
            pad(now.getHours()) +
            ':' +
            pad(now.getMinutes());
          document.getElementById('sb-edit-dato_sist_ros').value = local;
        });
      }

      document.getElementById('sb-vurderinger-lagre').addEventListener('click', function () {
        const statusEl = document.getElementById('sb-vurderinger-status');
        setStatus(statusEl, 'Lagrer…');
        const payload = {
          strategisk_egnethet: document.getElementById('sb-edit-strategisk_egnethet').value,
          teknisk_egnethet: document.getElementById('sb-edit-teknisk_egnethet').value,
          funksjonell_egnethet: document.getElementById('sb-edit-funksjonell_egnethet').value,
          konfidensialitetsvurdering: document.getElementById(
            'sb-edit-konfidensialitetsvurdering'
          ).value,
          integritetsvurdering: document.getElementById('sb-edit-integritetsvurdering').value,
          tilgjengelighetsvurdering: document.getElementById(
            'sb-edit-tilgjengelighetsvurdering'
          ).value,
          risikovurdering_tekst: document.getElementById('sb-edit-risikovurdering_tekst').value,
          url_risikovurdering: document.getElementById('sb-edit-url_risikovurdering').value,
          dato_sist_ros: document.getElementById('sb-edit-dato_sist_ros').value,
        };
        fetch(config.urlSaveVurderinger, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
          },
          body: JSON.stringify(payload),
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { ok: response.ok, data: data };
            });
          })
          .then(function (result) {
            if (!result.ok || !result.data.ok) {
              throw new Error(result.data.error || 'Lagring feilet');
            }
            vurderinger = result.data.vurderinger;
            refreshVurderingerView();
            closeVurderingerEdit();
            setStatus(statusEl, 'Lagret');
          })
          .catch(function (err) {
            setStatus(statusEl, err.message || 'Lagring feilet', true);
          });
      });
    }

  };
})();
