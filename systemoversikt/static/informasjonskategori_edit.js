// Change log:
// 2026-09-15: Inline OKA category editor for system defaults and systembruk extras/opt-outs.

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

  function renderMeta(kat) {
    const inactive = kat.aktiv === false
      ? ' <span class="badge badge-warning">Utfaset i OKA</span>'
      : '';
    let html =
      '<div class="oka-kat' + (kat.aktiv === false ? ' oka-kat--inaktiv' : '') + '">' +
      '<div class="oka-kat-hode"><strong class="oka-kat-kode">' + escapeHtml(kat.kode) + '</strong>' +
      '<span class="oka-kat-tittel">' + escapeHtml(kat.tittel) + '</span>' + inactive + '</div>' +
      '<div class="oka-kat-sti text-muted">' + escapeHtml(kat.sti || '') + '</div>';
    if (kat.her_legges) {
      html += '<div class="oka-kat-felt"><span class="oka-kat-felt-navn">Her legges</span> ' + escapeHtml(kat.her_legges) + '</div>';
    }
    if (kat.bk_vurdering) {
      html += '<div class="oka-kat-felt"><span class="oka-kat-felt-navn">BK-vurdering</span> ' + escapeHtml(kat.bk_vurdering) + '</div>';
    }
    if (kat.aktuelt_lovverk) {
      html += '<div class="oka-kat-felt"><span class="oka-kat-felt-navn">Lovverk</span> ' + escapeHtml(kat.aktuelt_lovverk) + '</div>';
    }
    if (kat.kommentar) {
      html += '<div class="oka-kat-felt"><span class="oka-kat-felt-navn">Kommentar</span> ' + escapeHtml(kat.kommentar) + '</div>';
    }
    html += '</div>';
    return html;
  }

  function cloneList(items) {
    return (items || []).map(function (item) {
      return Object.assign({}, item);
    });
  }

  function initSearch(input, hitsEl, searchUrl, excludeIdsFn, onPick) {
    let timer = null;
    input.addEventListener('input', function () {
      const q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) {
        hitsEl.innerHTML = '';
        return;
      }
      timer = setTimeout(function () {
        const params = new URLSearchParams();
        params.set('q', q);
        excludeIdsFn().forEach(function (id) {
          params.append('exclude', String(id));
        });
        fetch(searchUrl + '?' + params.toString(), {
          credentials: 'same-origin',
        }).then(function (res) {
          return res.json();
        }).then(function (data) {
          hitsEl.innerHTML = '';
          (data.results || []).forEach(function (kat) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'oka-treff';
            btn.innerHTML = '<strong>' + escapeHtml(kat.kode) + '</strong> ' +
              escapeHtml(kat.tittel) + '<div class="text-muted small">' + escapeHtml(kat.sti || '') + '</div>';
            btn.addEventListener('click', function () {
              onPick(kat);
              input.value = '';
              hitsEl.innerHTML = '';
            });
            hitsEl.appendChild(btn);
          });
        }).catch(function () {
          hitsEl.innerHTML = '';
        });
      }, 200);
    });
  }

  function initSystemEditor(config) {
    const panel = document.getElementById('oka-system-panel');
    if (!panel || !config) {
      return;
    }
    const viewEl = document.getElementById('oka-system-view');
    const editEl = document.getElementById('oka-system-edit');
    const listEl = document.getElementById('oka-system-edit-list');
    const toggleBtn = document.getElementById('oka-system-toggle');
    const saveBtn = document.getElementById('oka-system-lagre');
    const cancelBtn = document.getElementById('oka-system-avbryt');
    const statusEl = document.getElementById('oka-system-status');
    const sok = document.getElementById('oka-system-sok');
    const treff = document.getElementById('oka-system-sok-treff');
    let draft = cloneList(config.kategorier);

    function setStatus(message, isError) {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message || '';
      statusEl.className = 'oka-status small ' + (isError ? 'text-danger' : 'text-muted');
    }

    function renderDraft() {
      listEl.innerHTML = '';
      if (!draft.length) {
        listEl.innerHTML = '<p class="text-muted">Ingen standardkategorier valgt.</p>';
        return;
      }
      draft.forEach(function (kat, index) {
        const row = document.createElement('div');
        row.className = 'oka-edit-row';
        row.innerHTML = renderMeta(kat) +
          '<button type="button" class="btn btn-link btn-sm oka-fjern" data-index="' + index + '" aria-label="Fjern">&times;</button>';
        listEl.appendChild(row);
      });
    }

    function showView() {
      viewEl.hidden = false;
      editEl.hidden = true;
      if (toggleBtn) {
        toggleBtn.hidden = false;
      }
    }

    function showEdit() {
      draft = cloneList(config.kategorier);
      renderDraft();
      viewEl.hidden = true;
      editEl.hidden = false;
      if (toggleBtn) {
        toggleBtn.hidden = true;
      }
      setStatus('');
    }

    panel.addEventListener('click', function (event) {
      const btn = event.target.closest('.oka-fjern');
      if (!btn || !listEl.contains(btn)) {
        return;
      }
      const index = parseInt(btn.getAttribute('data-index'), 10);
      draft.splice(index, 1);
      renderDraft();
    });

    if (toggleBtn) {
      toggleBtn.addEventListener('click', showEdit);
    }
    if (cancelBtn) {
      cancelBtn.addEventListener('click', showView);
    }
    if (sok && treff) {
      initSearch(sok, treff, config.searchUrl, function () {
        return draft.map(function (k) { return k.id; });
      }, function (kat) {
        if (draft.some(function (k) { return k.id === kat.id; })) {
          return;
        }
        draft.push(kat);
        renderDraft();
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        setStatus('Lagrer…');
        fetch(config.urlSave, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(config),
          },
          body: JSON.stringify({
            ids: draft.map(function (k) { return k.id; }),
          }),
        }).then(function (res) {
          return res.json().then(function (data) {
            return { okHttp: res.ok, data: data };
          });
        }).then(function (result) {
          if (!result.okHttp || !result.data.ok) {
            setStatus('Kunne ikke lagre.', true);
            return;
          }
          config.kategorier = result.data.kategorier || draft;
          if (viewEl) {
            if (!config.kategorier.length) {
              viewEl.innerHTML = '<p class="text-muted">Ingen standard informasjonskategorier er registrert for systemet.</p>';
            } else {
              viewEl.innerHTML = config.kategorier.map(renderMeta).join('');
            }
          }
          showView();
          setStatus('Lagret.');
        }).catch(function () {
          setStatus('Kunne ikke lagre.', true);
        });
      });
    }
  }

  function initSystembrukEditor(config) {
    const panel = document.getElementById('oka-bruk-panel');
    if (!panel || !config) {
      return;
    }
    const viewEl = document.getElementById('oka-bruk-view');
    const editEl = document.getElementById('oka-bruk-edit');
    const standardEl = document.getElementById('oka-bruk-standard-edit');
    const tilleggEl = document.getElementById('oka-bruk-tillegg-edit');
    const toggleBtn = document.getElementById('oka-bruk-toggle');
    const saveBtn = document.getElementById('oka-bruk-lagre');
    const cancelBtn = document.getElementById('oka-bruk-avbryt');
    const statusEl = document.getElementById('oka-bruk-status');
    const sok = document.getElementById('oka-bruk-sok');
    const treff = document.getElementById('oka-bruk-sok-treff');
    let standardDraft = [];
    let tilleggDraft = [];

    function setStatus(message, isError) {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message || '';
      statusEl.className = 'oka-status small ' + (isError ? 'text-danger' : 'text-muted');
    }

    function defaultIds() {
      return (config.standard || []).map(function (k) { return k.id; });
    }

    function renderStandard() {
      standardEl.innerHTML = '';
      if (!standardDraft.length) {
        standardEl.innerHTML = '<p class="text-muted">Systemet har ingen standardkategorier.</p>';
        return;
      }
      standardDraft.forEach(function (kat, index) {
        const wrap = document.createElement('div');
        wrap.className = 'oka-standard-edit' + (kat.unntatt ? ' oka-unntatt' : '');
        wrap.innerHTML = renderMeta(kat) +
          '<label class="small d-block mb-1">' +
          '<input type="checkbox" class="oka-unntak" data-index="' + index + '"' +
          (kat.unntatt ? ' checked' : '') + '> Vi bruker ikke denne</label>' +
          '<textarea class="form-control form-control-sm oka-begrunnelse mb-3" data-index="' + index + '" rows="2" placeholder="Valgfri begrunnelse">' +
          escapeHtml(kat.begrunnelse || '') + '</textarea>';
        standardEl.appendChild(wrap);
      });
    }

    function renderTillegg() {
      tilleggEl.innerHTML = '';
      if (!tilleggDraft.length) {
        tilleggEl.innerHTML = '<p class="text-muted">Ingen tilleggskategorier.</p>';
        return;
      }
      tilleggDraft.forEach(function (kat, index) {
        const row = document.createElement('div');
        row.className = 'oka-edit-row';
        row.innerHTML = renderMeta(kat) +
          '<button type="button" class="btn btn-link btn-sm oka-fjern-tillegg" data-index="' + index + '" aria-label="Fjern">&times;</button>';
        tilleggEl.appendChild(row);
      });
    }

    function showView() {
      viewEl.hidden = false;
      editEl.hidden = true;
      if (toggleBtn) {
        toggleBtn.hidden = false;
      }
    }

    function showEdit() {
      standardDraft = cloneList(config.standard);
      tilleggDraft = cloneList(config.tillegg);
      renderStandard();
      renderTillegg();
      viewEl.hidden = true;
      editEl.hidden = false;
      if (toggleBtn) {
        toggleBtn.hidden = true;
      }
      setStatus('');
    }

    if (standardEl) {
      standardEl.addEventListener('change', function (event) {
        const box = event.target.closest('.oka-unntak');
        if (!box) {
          return;
        }
        const index = parseInt(box.getAttribute('data-index'), 10);
        standardDraft[index].unntatt = box.checked;
        renderStandard();
      });
      standardEl.addEventListener('input', function (event) {
        const area = event.target.closest('.oka-begrunnelse');
        if (!area) {
          return;
        }
        const index = parseInt(area.getAttribute('data-index'), 10);
        standardDraft[index].begrunnelse = area.value;
      });
    }
    if (tilleggEl) {
      tilleggEl.addEventListener('click', function (event) {
        const btn = event.target.closest('.oka-fjern-tillegg');
        if (!btn) {
          return;
        }
        tilleggDraft.splice(parseInt(btn.getAttribute('data-index'), 10), 1);
        renderTillegg();
      });
    }
    if (toggleBtn) {
      toggleBtn.addEventListener('click', showEdit);
    }
    if (cancelBtn) {
      cancelBtn.addEventListener('click', showView);
    }
    if (sok && treff) {
      initSearch(sok, treff, config.searchUrl, function () {
        return defaultIds().concat(tilleggDraft.map(function (k) { return k.id; }));
      }, function (kat) {
        if (defaultIds().indexOf(kat.id) !== -1) {
          setStatus('Dette er allerede en standardkategori. Bruk unntak hvis den ikke gjelder.', true);
          return;
        }
        if (tilleggDraft.some(function (k) { return k.id === kat.id; })) {
          return;
        }
        tilleggDraft.push(kat);
        renderTillegg();
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        setStatus('Lagrer…');
        const unntak = standardDraft.filter(function (k) { return k.unntatt; }).map(function (k) {
          return { id: k.id, begrunnelse: k.begrunnelse || '' };
        });
        const tillegg = tilleggDraft.map(function (k) {
          return { id: k.id, begrunnelse: k.begrunnelse || '' };
        });
        fetch(config.urlSave, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(config),
          },
          body: JSON.stringify({ unntak: unntak, tillegg: tillegg }),
        }).then(function (res) {
          return res.json().then(function (data) {
            return { okHttp: res.ok, data: data };
          });
        }).then(function (result) {
          if (!result.okHttp || !result.data.ok) {
            setStatus('Kunne ikke lagre.', true);
            return;
          }
          window.location.reload();
        }).catch(function () {
          setStatus('Kunne ikke lagre.', true);
        });
      });
    }
  }

  window.initOkaSystemEditor = initSystemEditor;
  window.initOkaSystembrukEditor = initSystembrukEditor;
})();
