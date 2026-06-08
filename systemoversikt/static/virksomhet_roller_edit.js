// Change log:
// 2026-06-08: Inline sentrale roller editor with ansvarlig search on virksomhet detail page.

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
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderAnsvarligChip(ansvarlig) {
    const style = ansvarlig.deaktivert ? 'text-decoration: line-through;' : '';
    return (
      '<span class="badge badge-light rolle-chip mr-1 mb-1" data-id="' + ansvarlig.id + '">' +
      '<a href="' + escapeHtml(ansvarlig.url) + '" style="' + style + '">' + escapeHtml(ansvarlig.label) + '</a> ' +
      '<button type="button" class="btn btn-link btn-sm p-0 ml-1 rolle-fjern" aria-label="Fjern">&times;</button>' +
      '</span>'
    );
  }

  function renderViewRow(label, ansvarlige, extraHtml) {
    let cell = '';
    if (extraHtml) {
      cell = extraHtml;
    } else if (!ansvarlige.length) {
      cell = '<span style="background-color: #ffacac">Mangler</span><br>';
    } else {
      ansvarlige.forEach(function (a) {
        const style = a.deaktivert ? 'text-decoration: line-through;' : '';
        cell += '👤 <a href="' + escapeHtml(a.url) + '" style="' + style + '">' + escapeHtml(a.label) + '</a><br>';
      });
    }
    return '<tr><td>' + escapeHtml(label) + '</td><td>' + cell + '</td></tr>';
  }

  function initVirksomhetRollerEdit(config) {
    const panel = document.getElementById('sentrale-roller-panel');
    if (!panel || !config) {
      return;
    }

    const viewEl = document.getElementById('sentrale-roller-view');
    const editEl = document.getElementById('sentrale-roller-edit');
    const toggleBtn = document.getElementById('sentrale-roller-toggle');
    const saveBtn = document.getElementById('sentrale-roller-lagre');
    const cancelBtn = document.getElementById('sentrale-roller-avbryt');
    const statusEl = document.getElementById('sentrale-roller-status');
    const csrf = getCsrfToken(config);

    let draft = {};
    let searchTimer = null;

    function setStatus(message, isError) {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message || '';
      statusEl.className = isError ? 'text-danger small' : 'text-muted small';
    }

    function loadDraftFromDom() {
      draft = {};
      panel.querySelectorAll('.rolle-edit').forEach(function (row) {
        const field = row.getAttribute('data-field');
        draft[field] = [];
        row.querySelectorAll('.rolle-chip').forEach(function (chip) {
          draft[field].push(parseInt(chip.getAttribute('data-id'), 10));
        });
      });
    }

    function currentIdsForField(field) {
      return (draft[field] || []).slice();
    }

    function renderEditChips(row, field) {
      const list = row.querySelector('.rolle-ansvarlige-list');
      const ansvarlige = config.initialRoller.find(function (r) { return r.field === field; });
      const byId = {};
      if (ansvarlige) {
        ansvarlige.ansvarlige.forEach(function (a) { byId[a.id] = a; });
      }
      list.innerHTML = '';
      currentIdsForField(field).forEach(function (id) {
        const data = byId[id] || { id: id, label: '#' + id, url: '#', deaktivert: false };
        list.insertAdjacentHTML('beforeend', renderAnsvarligChip(data));
      });
    }

    function showView() {
      resetEditFromInitial();
      editEl.hidden = true;
      viewEl.hidden = false;
      if (toggleBtn) {
        toggleBtn.textContent = 'Rediger';
      }
      setStatus('');
    }

    function showEdit() {
      resetEditFromInitial();
      viewEl.hidden = true;
      editEl.hidden = false;
      if (toggleBtn) {
        toggleBtn.textContent = 'Avbryt';
      }
    }

    function refreshViewTable(roller) {
      const tbody = viewEl.querySelector('tbody');
      let html = renderViewRow('Etatsdirektør', [], config.etatsdirektorHtml || '<i>Ingen data fra HR tilgjengelig</i>');

      roller.forEach(function (rolle) {
        html += renderViewRow(rolle.label, rolle.ansvarlige);
      });

      html += renderViewRow(
        'Autoriserte bestillere av sertifikater fra Buypass via Sopra Steria',
        [],
        'Se <a href="' + escapeHtml(config.sertifikatUrl) + '">avgitte fullmakter</a>'
      );

      tbody.innerHTML = html;
      config.initialRoller = roller;
      panel.querySelectorAll('.rolle-edit').forEach(function (row) {
        const field = row.getAttribute('data-field');
        const match = roller.find(function (r) { return r.field === field; });
        if (match) {
          row.querySelector('.rolle-ansvarlige-list').innerHTML = match.ansvarlige.map(renderAnsvarligChip).join('');
        }
      });
    }

    function resetEditFromInitial() {
      panel.querySelectorAll('.rolle-edit').forEach(function (row) {
        const field = row.getAttribute('data-field');
        const rolle = config.initialRoller.find(function (r) { return r.field === field; });
        draft[field] = rolle ? rolle.ansvarlige.map(function (a) { return a.id; }) : [];
        row.querySelector('.rolle-sok').value = '';
        row.querySelector('.rolle-sok-treff').innerHTML = '';
        renderEditChips(row, field);
      });
    }

    function ensureAnsvarlig(item, field) {
      if (!item.create) {
        return Promise.resolve({
          id: item.id,
          label: item.label,
          url: item.url,
          deaktivert: !!item.deaktivert,
        });
      }
      return fetch(config.urlCreate, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
        },
        body: JSON.stringify({ user_pk: item.user_pk, field: field }),
      }).then(function (response) {
        if (!response.ok) {
          throw new Error('Kunne ikke opprette ansvarlig');
        }
        return response.json();
      });
    }

    panel.addEventListener('click', function (event) {
      const removeBtn = event.target.closest('.rolle-fjern');
      if (removeBtn) {
        const row = removeBtn.closest('.rolle-edit');
        const chip = removeBtn.closest('.rolle-chip');
        const field = row.getAttribute('data-field');
        const id = parseInt(chip.getAttribute('data-id'), 10);
        draft[field] = currentIdsForField(field).filter(function (x) { return x !== id; });
        renderEditChips(row, field);
        return;
      }

      const pickBtn = event.target.closest('.rolle-pick');
      if (pickBtn) {
        const row = pickBtn.closest('.rolle-edit');
        const field = row.getAttribute('data-field');
        const payload = {
          create: pickBtn.getAttribute('data-create') === '1',
          user_pk: pickBtn.getAttribute('data-user-pk') ? parseInt(pickBtn.getAttribute('data-user-pk'), 10) : null,
          id: pickBtn.getAttribute('data-id') ? parseInt(pickBtn.getAttribute('data-id'), 10) : null,
          label: pickBtn.getAttribute('data-label') || '',
          url: pickBtn.getAttribute('data-url') || '#',
          deaktivert: pickBtn.getAttribute('data-deaktivert') === '1',
        };
        ensureAnsvarlig(payload, field).then(function (ansvarlig) {
          const ids = currentIdsForField(field);
          if (ids.indexOf(ansvarlig.id) === -1) {
            draft[field] = ids.concat([ansvarlig.id]);
          }
          const rolle = config.initialRoller.find(function (r) { return r.field === field; });
          if (rolle) {
            const exists = rolle.ansvarlige.some(function (a) { return a.id === ansvarlig.id; });
            if (!exists) {
              rolle.ansvarlige.push(ansvarlig);
            }
          }
          renderEditChips(row, field);
          row.querySelector('.rolle-sok').value = '';
          row.querySelector('.rolle-sok-treff').innerHTML = '';
        }).catch(function (err) {
          setStatus(err.message || 'Feil ved opprettelse', true);
        });
      }
    });

    panel.addEventListener('input', function (event) {
      const input = event.target.closest('.rolle-sok');
      if (!input) {
        return;
      }
      const row = input.closest('.rolle-edit');
      const field = row.getAttribute('data-field');
      const hits = row.querySelector('.rolle-sok-treff');
      const q = input.value.trim();

      clearTimeout(searchTimer);
      if (q.length < 2) {
        hits.innerHTML = '';
        return;
      }

      searchTimer = setTimeout(function () {
        const exclude = currentIdsForField(field).join(',');
        const url = config.urlSearch + '?q=' + encodeURIComponent(q) + '&exclude_field=' + encodeURIComponent(field) + '&exclude_ids=' + encodeURIComponent(exclude);
        fetch(url, { credentials: 'same-origin' })
          .then(function (response) {
            if (!response.ok) {
              throw new Error('Søk feilet');
            }
            return response.json();
          })
          .then(function (data) {
            if (!data.results.length) {
              hits.innerHTML = '<div class="text-muted small">Ingen treff</div>';
              return;
            }
            hits.innerHTML = data.results.map(function (item) {
              const suffix = item.create ? ' (opprett ny ansvarlig)' : '';
              let attrs = 'class="btn btn-link btn-sm d-block text-left p-0 rolle-pick" data-label="' + escapeHtml(item.label) + '"';
              if (item.create) {
                attrs += ' data-create="1" data-user-pk="' + item.user_pk + '"';
              } else {
                attrs += ' data-id="' + item.id + '" data-url="' + escapeHtml(item.url) + '"';
                if (item.deaktivert) {
                  attrs += ' data-deaktivert="1"';
                }
              }
              return '<button type="button" ' + attrs + '>' + escapeHtml(item.label) + suffix + '</button>';
            }).join('');
          })
          .catch(function () {
            hits.innerHTML = '<div class="text-danger small">Søk feilet</div>';
          });
      }, 250);
    });

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function (event) {
        event.preventDefault();
        if (editEl.hidden) {
          showEdit();
        } else {
          showView();
        }
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', function (event) {
        event.preventDefault();
        showView();
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', function (event) {
        event.preventDefault();
        loadDraftFromDom();
        setStatus('Lagrer…', false);
        saveBtn.disabled = true;

        fetch(config.urlSave, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
          },
          body: JSON.stringify({ roles: draft }),
        }).then(function (response) {
          if (!response.ok) {
            throw new Error('Lagring feilet');
          }
          return response.json();
        }).then(function (data) {
          refreshViewTable(data.roller);
          showView();
          setStatus('Lagret.', false);
        }).catch(function () {
          setStatus('Kunne ikke lagre endringene.', true);
        }).finally(function () {
          saveBtn.disabled = false;
        });
      });
    }
  }

  window.initVirksomhetRollerEdit = initVirksomhetRollerEdit;
})();
