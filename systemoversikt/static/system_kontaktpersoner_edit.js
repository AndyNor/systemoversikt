// Change log:
// 2026-11-01: Person/seksjon search across virksomheter (prefer draft virksomhet_id when set).
// 2026-11-01: Also edit seksjon (HRorg) and forvaltning_epost on systemdetaljer eierskap.
// 2026-11-01: Also edit organizational Systemeier/Systemforvalter (virksomhet pickers).
// 2026-11-01: Inline editor for Systemeier/Systemforvalter contact persons on systemdetaljer.

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

  function renderAnsvarligChip(ansvarlig) {
    const style = ansvarlig.deaktivert ? 'text-decoration: line-through;' : '';
    return (
      '<span class="badge badge-light rolle-chip mr-1 mb-1" data-id="' +
      ansvarlig.id +
      '">' +
      '<a href="' +
      escapeHtml(ansvarlig.url || '#') +
      '" style="' +
      style +
      '">' +
      escapeHtml(ansvarlig.label) +
      '</a> ' +
      '<button type="button" class="btn btn-link btn-sm p-0 ml-1 sk-fjern" aria-label="Fjern">&times;</button>' +
      '</span>'
    );
  }

  function renderAnsvarligView(ansvarlige, twoColumns) {
    if (!ansvarlige || !ansvarlige.length) {
      return '<span style="background-color: #ffacac">Mangler</span><br>';
    }
    return ansvarlige
      .map(function (a) {
        const style = a.deaktivert ? 'text-decoration: line-through;' : '';
        const email = a.email ? escapeHtml(a.email) + '<br>' : '';
        const body =
          '👤 <a href="' +
          escapeHtml(a.url || '#') +
          '" style="' +
          style +
          '">' +
          escapeHtml(a.label) +
          '</a><br>' +
          email;
        if (twoColumns) {
          return '<div class="ansvarlig-kontakt-item">' + body + '</div>';
        }
        return body;
      })
      .join('');
  }

  function renderVirksomhetLink(virksomhet) {
    if (!virksomhet) {
      return '<span class="text-muted">Ikke angitt</span>';
    }
    return (
      '<a class="virksomhet-lenke" href="' +
      escapeHtml(virksomhet.url || '#') +
      '">' +
      escapeHtml(virksomhet.label) +
      '</a>'
    );
  }

  function renderEnhetLink(enhet) {
    if (!enhet) {
      return '<span class="text-muted">Ikke angitt</span>';
    }
    return (
      '<a href="' +
      escapeHtml(enhet.url || '#') +
      '">' +
      escapeHtml(enhet.label) +
      '</a>'
    );
  }

  window.initSystemKontaktpersonerEditor = function initSystemKontaktpersonerEditor(config) {
    const panel = document.getElementById('system-eierskap-kontakt-panel');
    if (!panel || !config) {
      return;
    }

    const viewEl = document.getElementById('system-eierskap-kontakt-view');
    const editEl = document.getElementById('system-eierskap-kontakt-edit');
    const toggleBtn = document.getElementById('system-eierskap-kontakt-toggle');
    const saveBtn = document.getElementById('system-eierskap-kontakt-lagre');
    const cancelBtn = document.getElementById('system-eierskap-kontakt-avbryt');
    const statusEl = document.getElementById('system-eierskap-kontakt-status');
    const epostInput = document.getElementById('sk-edit-forvaltning_epost');
    const csrf = getCsrfToken(config);
    const personFields = [
      'systemeier_kontaktpersoner_referanse',
      'systemforvalter_kontaktpersoner_referanse',
    ];
    const virksomhetFields = ['systemeier', 'systemforvalter'];

    let data = config.eierskap || {};
    const m2mCache = {};
    const draftVirksomhet = {
      systemeier: data.systemeier || null,
      systemforvalter: data.systemforvalter || null,
    };
    let draftEnhet = data.systemforvalter_avdeling_referanse || null;
    let searchTimer = null;
    let virksomhetSearchTimer = null;
    let enhetSearchTimer = null;

    function setStatus(message, isError) {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message || '';
      statusEl.className = isError ? 'text-danger small' : 'text-muted small';
    }

    function syncCache() {
      personFields.forEach(function (field) {
        m2mCache[field] = {};
        (data[field] || []).forEach(function (a) {
          m2mCache[field][a.id] = a;
        });
      });
    }
    syncCache();

    function currentIds(field) {
      const row = panel.querySelector('.sk-m2m-edit[data-field="' + field + '"]');
      if (!row) {
        return [];
      }
      const ids = [];
      row.querySelectorAll('.rolle-chip').forEach(function (chip) {
        ids.push(parseInt(chip.getAttribute('data-id'), 10));
      });
      return ids;
    }

    function virksomhetFieldForPerson(field) {
      if (field === 'systemeier_kontaktpersoner_referanse') {
        return 'systemeier';
      }
      if (field === 'systemforvalter_kontaktpersoner_referanse') {
        return 'systemforvalter';
      }
      return null;
    }

    function renderVirksomhetPicker(field) {
      const box = panel.querySelector('.sk-virksomhet-edit[data-field="' + field + '"]');
      if (!box) {
        return;
      }
      const selected = box.querySelector('.sk-virksomhet-selected');
      const clearBtn = box.querySelector('.sk-virksomhet-fjern');
      const virksomhet = draftVirksomhet[field];
      selected.innerHTML = renderVirksomhetLink(virksomhet);
      if (clearBtn) {
        clearBtn.hidden = !virksomhet || field === 'systemforvalter';
      }
    }

    function renderEnhetPicker() {
      const box = panel.querySelector('.sk-enhet-edit');
      if (!box) {
        return;
      }
      box.querySelector('.sk-enhet-selected').innerHTML = renderEnhetLink(draftEnhet);
      const clearBtn = box.querySelector('.sk-enhet-fjern');
      if (clearBtn) {
        clearBtn.hidden = !draftEnhet;
      }
    }

    function clearEnhetDraft() {
      draftEnhet = null;
      renderEnhetPicker();
      const box = panel.querySelector('.sk-enhet-edit');
      if (box) {
        box.querySelector('.sk-enhet-sok').value = '';
        box.querySelector('.sk-enhet-treff').innerHTML = '';
      }
    }

    function fillEditForm() {
      draftVirksomhet.systemeier = data.systemeier || null;
      draftVirksomhet.systemforvalter = data.systemforvalter || null;
      draftEnhet = data.systemforvalter_avdeling_referanse || null;
      virksomhetFields.forEach(renderVirksomhetPicker);
      renderEnhetPicker();
      if (epostInput) {
        epostInput.value = data.forvaltning_epost || '';
      }
      panel.querySelectorAll('.sk-virksomhet-sok').forEach(function (input) {
        input.value = '';
      });
      panel.querySelectorAll('.sk-virksomhet-treff').forEach(function (el) {
        el.innerHTML = '';
      });
      panel.querySelectorAll('.sk-enhet-sok').forEach(function (input) {
        input.value = '';
      });
      panel.querySelectorAll('.sk-enhet-treff').forEach(function (el) {
        el.innerHTML = '';
      });
      personFields.forEach(function (field) {
        const row = panel.querySelector('.sk-m2m-edit[data-field="' + field + '"]');
        if (!row) {
          return;
        }
        row.querySelector('.sk-ansvarlig-sok').value = '';
        row.querySelector('.sk-ansvarlig-treff').innerHTML = '';
        const list = row.querySelector('.sk-ansvarlige-list');
        list.innerHTML = '';
        (data[field] || []).forEach(function (a) {
          m2mCache[field][a.id] = a;
          list.insertAdjacentHTML('beforeend', renderAnsvarligChip(a));
        });
      });
    }

    function refreshView() {
      const eierVirksomhet = document.getElementById('sk-view-systemeier');
      const forvVirksomhet = document.getElementById('sk-view-systemforvalter');
      if (eierVirksomhet) {
        eierVirksomhet.innerHTML = renderVirksomhetLink(data.systemeier);
      }
      if (forvVirksomhet) {
        forvVirksomhet.innerHTML = renderVirksomhetLink(data.systemforvalter);
      }

      const seksjonEl = document.getElementById('sk-view-systemforvalter_avdeling');
      if (seksjonEl) {
        if (data.systemforvalter_avdeling_referanse) {
          seksjonEl.innerHTML =
            'Seksjon: ' + renderEnhetLink(data.systemforvalter_avdeling_referanse);
          seksjonEl.hidden = false;
        } else {
          seksjonEl.innerHTML = '';
          seksjonEl.hidden = true;
        }
      }

      const epostEl = document.getElementById('sk-view-forvaltning_epost');
      if (epostEl) {
        if (data.forvaltning_epost) {
          epostEl.textContent =
            'E-post til forvaltergruppen: ' + data.forvaltning_epost;
          epostEl.hidden = false;
        } else {
          epostEl.textContent = '';
          epostEl.hidden = true;
        }
      }

      const eierEl = document.getElementById('sk-view-systemeier_kontaktpersoner_referanse');
      const forvEl = document.getElementById('sk-view-systemforvalter_kontaktpersoner_referanse');
      if (eierEl) {
        eierEl.innerHTML = renderAnsvarligView(
          data.systemeier_kontaktpersoner_referanse,
          false
        );
      }
      if (forvEl) {
        forvEl.innerHTML = renderAnsvarligView(
          data.systemforvalter_kontaktpersoner_referanse,
          true
        );
      }
    }

    function setToggleLabel(editing) {
      if (!toggleBtn) {
        return;
      }
      toggleBtn.textContent = editing ? 'Avbryt' : 'Rediger';
    }

    function openEdit() {
      fillEditForm();
      if (viewEl) {
        viewEl.hidden = true;
      }
      if (editEl) {
        editEl.hidden = false;
      }
      setToggleLabel(true);
      setStatus('');
    }

    function closeEdit() {
      fillEditForm();
      if (editEl) {
        editEl.hidden = true;
      }
      if (viewEl) {
        viewEl.hidden = false;
      }
      setToggleLabel(false);
    }

    function ensureAnsvarlig(item, field) {
      if (!item.create) {
        return Promise.resolve({
          id: item.id,
          label: item.label,
          url: item.url || '#',
          deaktivert: !!item.deaktivert,
          email: item.email || '',
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
        body: JSON.stringify({
          user_pk: item.user_pk,
          field: field,
        }),
      }).then(function (response) {
        if (!response.ok) {
          throw new Error('Kunne ikke opprette ansvarlig');
        }
        return response.json();
      });
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        if (editEl.hidden) {
          openEdit();
        } else {
          closeEdit();
          setStatus('');
        }
      });
    }
    if (cancelBtn) {
      cancelBtn.addEventListener('click', function () {
        closeEdit();
        setStatus('');
      });
    }

    panel.addEventListener('click', function (event) {
      const clearVirksomhet = event.target.closest('.sk-virksomhet-fjern');
      if (clearVirksomhet) {
        const box = clearVirksomhet.closest('.sk-virksomhet-edit');
        const field = box.getAttribute('data-field');
        if (field === 'systemforvalter') {
          return;
        }
        draftVirksomhet[field] = null;
        renderVirksomhetPicker(field);
        box.querySelector('.sk-virksomhet-sok').value = '';
        box.querySelector('.sk-virksomhet-treff').innerHTML = '';
        return;
      }

      const pickVirksomhet = event.target.closest('.sk-virksomhet-pick');
      if (pickVirksomhet) {
        const box = pickVirksomhet.closest('.sk-virksomhet-edit');
        const field = box.getAttribute('data-field');
        const previousId = draftVirksomhet[field] ? draftVirksomhet[field].id : null;
        const nextId = parseInt(pickVirksomhet.getAttribute('data-id'), 10);
        draftVirksomhet[field] = {
          id: nextId,
          label: pickVirksomhet.getAttribute('data-label') || '',
          forkortelse: pickVirksomhet.getAttribute('data-forkortelse') || '',
          url: pickVirksomhet.getAttribute('data-url') || '#',
        };
        renderVirksomhetPicker(field);
        box.querySelector('.sk-virksomhet-sok').value = '';
        box.querySelector('.sk-virksomhet-treff').innerHTML = '';
        if (field === 'systemforvalter' && previousId !== nextId) {
          clearEnhetDraft();
        }
        return;
      }

      const clearEnhet = event.target.closest('.sk-enhet-fjern');
      if (clearEnhet) {
        clearEnhetDraft();
        return;
      }

      const pickEnhet = event.target.closest('.sk-enhet-pick');
      if (pickEnhet) {
        draftEnhet = {
          id: parseInt(pickEnhet.getAttribute('data-id'), 10),
          label: pickEnhet.getAttribute('data-label') || '',
          url: pickEnhet.getAttribute('data-url') || '#',
        };
        renderEnhetPicker();
        const box = pickEnhet.closest('.sk-enhet-edit');
        box.querySelector('.sk-enhet-sok').value = '';
        box.querySelector('.sk-enhet-treff').innerHTML = '';
        return;
      }

      const removeBtn = event.target.closest('.sk-fjern');
      if (removeBtn) {
        const chip = removeBtn.closest('.rolle-chip');
        if (chip) {
          chip.remove();
        }
        return;
      }
      const pickBtn = event.target.closest('.sk-pick');
      if (pickBtn) {
        const row = pickBtn.closest('.sk-m2m-edit');
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
          email: pickBtn.getAttribute('data-email') || '',
        };
        ensureAnsvarlig(payload, field)
          .then(function (ansvarlig) {
            m2mCache[field][ansvarlig.id] = ansvarlig;
            const ids = currentIds(field);
            if (ids.indexOf(ansvarlig.id) === -1) {
              row
                .querySelector('.sk-ansvarlige-list')
                .insertAdjacentHTML('beforeend', renderAnsvarligChip(ansvarlig));
            }
            row.querySelector('.sk-ansvarlig-sok').value = '';
            row.querySelector('.sk-ansvarlig-treff').innerHTML = '';
          })
          .catch(function (err) {
            setStatus(err.message || 'Feil', true);
          });
      }
    });

    panel.addEventListener('input', function (event) {
      const virksomhetInput = event.target.closest('.sk-virksomhet-sok');
      if (virksomhetInput) {
        const box = virksomhetInput.closest('.sk-virksomhet-edit');
        const hits = box.querySelector('.sk-virksomhet-treff');
        const q = virksomhetInput.value.trim();
        clearTimeout(virksomhetSearchTimer);
        if (q.length < 2) {
          hits.innerHTML = '';
          return;
        }
        virksomhetSearchTimer = setTimeout(function () {
          const url =
            config.urlVirksomhetSearch + '?q=' + encodeURIComponent(q);
          fetch(url, { credentials: 'same-origin' })
            .then(function (response) {
              if (!response.ok) {
                throw new Error('Søk feilet');
              }
              return response.json();
            })
            .then(function (payload) {
              hits.innerHTML = (payload.results || [])
                .map(function (item) {
                  return (
                    '<button type="button" class="btn btn-link btn-sm sk-virksomhet-pick" data-id="' +
                    item.id +
                    '" data-label="' +
                    escapeHtml(item.label) +
                    '" data-forkortelse="' +
                    escapeHtml(item.forkortelse || '') +
                    '" data-url="' +
                    escapeHtml(item.url || '#') +
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
        return;
      }

      const enhetInput = event.target.closest('.sk-enhet-sok');
      if (enhetInput) {
        const box = enhetInput.closest('.sk-enhet-edit');
        const hits = box.querySelector('.sk-enhet-treff');
        const q = enhetInput.value.trim();
        clearTimeout(enhetSearchTimer);
        if (q.length < 2) {
          hits.innerHTML = '';
          return;
        }
        enhetSearchTimer = setTimeout(function () {
          // 2026-11-01: Cross-virksomhet search; draft systemforvalter only for sort preference.
          const virksomhet = draftVirksomhet.systemforvalter;
          let url =
            config.urlEnhetSearch + '?q=' + encodeURIComponent(q);
          if (virksomhet && virksomhet.id) {
            url += '&virksomhet_id=' + encodeURIComponent(virksomhet.id);
          }
          fetch(url, { credentials: 'same-origin' })
            .then(function (response) {
              if (!response.ok) {
                throw new Error('Søk feilet');
              }
              return response.json();
            })
            .then(function (payload) {
              hits.innerHTML = (payload.results || [])
                .map(function (item) {
                  return (
                    '<button type="button" class="btn btn-link btn-sm sk-enhet-pick" data-id="' +
                    item.id +
                    '" data-label="' +
                    escapeHtml(item.label) +
                    '" data-url="' +
                    escapeHtml(item.url || '#') +
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
        return;
      }

      const input = event.target.closest('.sk-ansvarlig-sok');
      if (!input) {
        return;
      }
      const row = input.closest('.sk-m2m-edit');
      const field = row.getAttribute('data-field');
      const hits = row.querySelector('.sk-ansvarlig-treff');
      const q = input.value.trim();
      clearTimeout(searchTimer);
      if (q.length < 2) {
        hits.innerHTML = '';
        return;
      }
      searchTimer = setTimeout(function () {
        // 2026-11-01: Cross-virksomhet search; draft virksomhet only for sort preference.
        const exclude = currentIds(field).join(',');
        const virksomhetField = virksomhetFieldForPerson(field);
        const virksomhet = virksomhetField ? draftVirksomhet[virksomhetField] : null;
        let url =
          config.urlSearch +
          '?q=' +
          encodeURIComponent(q) +
          '&field=' +
          encodeURIComponent(field) +
          '&exclude_ids=' +
          encodeURIComponent(exclude);
        if (virksomhet && virksomhet.id) {
          url += '&virksomhet_id=' + encodeURIComponent(virksomhet.id);
        }
        fetch(url, { credentials: 'same-origin' })
          .then(function (response) {
            if (!response.ok) {
              throw new Error('Søk feilet');
            }
            return response.json();
          })
          .then(function (payload) {
            hits.innerHTML = (payload.results || [])
              .map(function (item) {
                if (item.create) {
                  return (
                    '<button type="button" class="btn btn-link btn-sm sk-pick" data-create="1" data-user-pk="' +
                    item.user_pk +
                    '" data-label="' +
                    escapeHtml(item.label) +
                    '">+ Opprett «' +
                    escapeHtml(item.label) +
                    '»</button>'
                  );
                }
                return (
                  '<button type="button" class="btn btn-link btn-sm sk-pick" data-id="' +
                  item.id +
                  '" data-label="' +
                  escapeHtml(item.label) +
                  '" data-url="' +
                  escapeHtml(item.url || '#') +
                  '" data-email="' +
                  escapeHtml(item.email || '') +
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

    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        if (!draftVirksomhet.systemforvalter || !draftVirksomhet.systemforvalter.id) {
          setStatus('Systemforvalter (virksomhet) er påkrevd', true);
          return;
        }
        setStatus('Lagrer…');
        saveBtn.disabled = true;
        const payload = {
          systemeier: draftVirksomhet.systemeier
            ? draftVirksomhet.systemeier.id
            : null,
          systemforvalter: draftVirksomhet.systemforvalter.id,
          systemforvalter_avdeling_referanse: draftEnhet ? draftEnhet.id : null,
          forvaltning_epost: epostInput ? epostInput.value.trim() : '',
          systemeier_kontaktpersoner_referanse: currentIds(
            'systemeier_kontaktpersoner_referanse'
          ),
          systemforvalter_kontaktpersoner_referanse: currentIds(
            'systemforvalter_kontaktpersoner_referanse'
          ),
        };
        fetch(config.urlSave, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
          },
          body: JSON.stringify(payload),
        })
          .then(function (response) {
            return response.json().then(function (body) {
              return { ok: response.ok, body: body };
            });
          })
          .then(function (result) {
            if (!result.ok || !result.body.ok) {
              const err = result.body.error || 'Lagring feilet';
              if (err === 'invalid_email') {
                throw new Error('Ugyldig e-postadresse');
              }
              throw new Error(err);
            }
            data = result.body.eierskap;
            syncCache();
            refreshView();
            closeEdit();
            if (result.body.can_still_edit === false) {
              if (toggleBtn) {
                toggleBtn.hidden = true;
              }
              setStatus(
                'Lagret. Du har ikke lenger rettighet til å endre dette systemet.'
              );
            } else {
              setStatus('Lagret');
            }
          })
          .catch(function (err) {
            setStatus(err.message || 'Lagring feilet', true);
          })
          .finally(function () {
            saveBtn.disabled = false;
          });
      });
    }
  };
})();
