// 2026-07-06: Detail page – unlink scenario from subcategory via linkDelete API.
// 2026-07-06: Kartlegging eskaleres_only filter – scenarios linked to flagged tiltak.
// 2026-07-06: Kartlegging risk cells use risiko-level-tag (colored tags like scope table).
// 2026-07-06: Kartlegging – derive risk labels from matrix when API omits precomputed labels.
// 2026-07-06: Kartlegging table – nåværende and etter-tiltak risk badges.
// 2026-07-06: Category-level rating modal – prefill from data attributes on hovedkategori.
// 2026-07-06: Mal editor – hide koblinger count on taxonomy nodes (template has no live mappings).
// 2026-07-06: Automatic category numbering in mal editor – no manual nummer input.
// 2026-07-06: Client logic for sammenstilling rollup, mapping, and superuser mal editor.
(function (window) {
  'use strict';

  function getCsrfToken() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function parseUrls(root) {
    try {
      return JSON.parse(root.getAttribute('data-api-urls') || '{}');
    } catch (e) {
      return {};
    }
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(body || {}),
    }).then(function (r) { return r.json(); });
  }

  function getJson(url) {
    return fetch(url, { credentials: 'same-origin' }).then(function (r) { return r.json(); });
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  function initRollup(root) {
    if (!root) return;
    var urls = parseUrls(root);
    var currentNodePk = null;
    var modal = document.getElementById('rammeverk-rating-modal');
    var drillModal = document.getElementById('rammeverk-drilldown-modal');

    root.addEventListener('click', function (ev) {
      var unlinkBtn = ev.target.closest('.js-unlink-scenario');
      if (unlinkBtn) {
        var linkId = unlinkBtn.getAttribute('data-link-pk');
        if (!linkId || !urls.linkDelete) return;
        if (!window.confirm('Fjerne koblingen mellom dette scenarioet og underkategorien?')) return;
        postJson(urls.linkDelete.replace('{id}', linkId), {}).then(function (data) {
          if (!data.ok) {
            alert(data.error || 'Kunne ikke fjerne kobling');
            return;
          }
          window.location.reload();
        });
        return;
      }
      var editBtn = ev.target.closest('.js-edit-rating');
      if (editBtn) {
        currentNodePk = editBtn.getAttribute('data-node-pk');
        var sEl = document.getElementById('rammeverk-rating-s');
        var kEl = document.getElementById('rammeverk-rating-k');
        var bEl = document.getElementById('rammeverk-rating-begrunnelse');
        if (sEl) sEl.value = editBtn.getAttribute('data-s') || '';
        if (kEl) kEl.value = editBtn.getAttribute('data-k') || '';
        if (bEl) bEl.value = editBtn.getAttribute('data-begrunnelse') || '';
        if (modal) window.jQuery(modal).modal('show');
        return;
      }
      var drillBtn = ev.target.closest('.js-drilldown');
      if (drillBtn) {
        var nid = drillBtn.getAttribute('data-node-pk');
        var body = document.getElementById('rammeverk-drilldown-body');
        if (!urls.nodeScenarios || !body) return;
        body.innerHTML = '<p class="p-3 mb-0 text-muted">Laster…</p>';
        window.jQuery(drillModal).modal('show');
        getJson(urls.nodeScenarios.replace('{id}', nid)).then(function (data) {
          if (!data.ok) {
            body.innerHTML = '<p class="p-3 text-danger">' + (data.error || 'Feil') + '</p>';
            return;
          }
          if (!data.scenarios.length) {
            body.innerHTML = '<p class="p-3 mb-0 text-muted">Ingen kartlagte scenarioer.</p>';
            return;
          }
          var html = '<table class="table table-sm mb-0"><thead><tr><th>R#</th><th>Samling</th><th>Hendelse</th><th>Nå</th><th>Rest</th></tr></thead><tbody>';
          data.scenarios.forEach(function (s) {
            html += '<tr><td>' + s.display_id + '</td><td><a href="/sikkerhet/risiko/collection/' + s.scope_pk + '/">' + escapeHtml(s.scope_title) + '</a></td>';
            html += '<td>' + escapeHtml(s.uonsket_hendelse.substring(0, 120)) + '</td>';
            html += '<td><span class="badge ' + s.current_css + '">' + (s.current_label || '—') + '</span></td>';
            html += '<td><span class="badge ' + s.residual_css + '">' + (s.residual_label || '—') + '</span></td></tr>';
          });
          html += '</tbody></table>';
          body.innerHTML = html;
        });
      }
    });

    var saveBtn = document.getElementById('rammeverk-save-rating');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        if (!currentNodePk || !urls.assessmentSave) return;
        var s = parseInt(document.getElementById('rammeverk-rating-s').value, 10);
        var k = parseInt(document.getElementById('rammeverk-rating-k').value, 10);
        var begrunnelse = document.getElementById('rammeverk-rating-begrunnelse').value;
        postJson(urls.assessmentSave.replace('{id}', currentNodePk), {
          sannsynlighet_nivaa: s,
          konsekvens_nivaa: k,
          begrunnelse: begrunnelse,
        }).then(function (data) {
          if (!data.ok) {
            alert(data.error || 'Kunne ikke lagre');
            return;
          }
          window.location.reload();
        });
      });
    }

    var applyBtn = document.getElementById('rammeverk-apply-suggestion');
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        if (!currentNodePk || !urls.assessmentApply) return;
        postJson(urls.assessmentApply.replace('{id}', currentNodePk), {}).then(function (data) {
          if (!data.ok) {
            alert(data.error || 'Kunne ikke overføre');
            return;
          }
          window.location.reload();
        });
      });
    }
  }

  function initKartlegging(root) {
    if (!root) return;
    var urls = parseUrls(root);
    var riskMeta = {};
    try {
      riskMeta = JSON.parse(root.getAttribute('data-risk-meta') || '{}');
    } catch (e) {
      riskMeta = {};
    }
    var riskMatrix = riskMeta.risk_matrix || {};
    var tbody = document.getElementById('kartlegging-scenarios-body');
    var nodeSelect = document.getElementById('kartlegging-target-node');

    function riskCellClass(label) {
      if (label === 'Lav') return 'risk-cell-lav';
      if (label === 'Middels') return 'risk-cell-middels';
      if (label === 'Høy') return 'risk-cell-hoy';
      return 'risk-cell-empty';
    }

    function matrixRiskLabel(sannsynlighet, konsekvens) {
      if (!sannsynlighet || !konsekvens) return '';
      var row = riskMatrix[sannsynlighet] || riskMatrix[String(sannsynlighet)];
      if (!row) return '';
      return row[konsekvens] || row[String(konsekvens)] || '';
    }

    function scenarioCurrentLabel(scenario) {
      return scenario.current_label || scenario.risiko_etikett
        || matrixRiskLabel(scenario.sannsynlighet_nivaa, scenario.konsekvens_nivaa);
    }

    function scenarioResidualLabel(scenario) {
      var direct = scenario.residual_label || scenario.restrisiko_etikett;
      if (direct) return direct;
      var konsekvens = scenario.konsekvens_etter || scenario.konsekvens_nivaa;
      var sannsynlighet = scenario.sannsynlighet_etter || scenario.sannsynlighet_nivaa;
      return matrixRiskLabel(sannsynlighet, konsekvens);
    }

    function riskLevelTag(label, css) {
      if (!label) return '—';
      var cls = css || riskCellClass(label) || 'risk-cell-empty';
      return '<span class="risiko-level-tag ' + escapeHtml(cls) + '">' + escapeHtml(label) + '</span>';
    }

    function loadNodes() {
      if (!urls.activeNodes || !nodeSelect) return;
      getJson(urls.activeNodes).then(function (data) {
        if (!data.ok) return;
        nodeSelect.innerHTML = '<option value="">Velg underkategori…</option>';
        data.nodes.forEach(function (n) {
          var opt = document.createElement('option');
          opt.value = n.pk;
          opt.textContent = n.display_code + ' ' + n.title;
          nodeSelect.appendChild(opt);
        });
      });
    }

    function search() {
      if (!urls.scenarioSearch || !tbody) return;
      var colCount = 7;
      var params = new URLSearchParams();
      var virksomhetEl = document.getElementById('kartlegging-virksomhet');
      var q = document.getElementById('kartlegging-q').value;
      if (virksomhetEl && virksomhetEl.value) params.set('virksomhet_id', virksomhetEl.value);
      if (q) params.set('q', q);
      if (document.getElementById('kartlegging-unmapped').checked) params.set('unmapped_only', '1');
      var eskaleresEl = document.getElementById('kartlegging-eskaleres');
      if (eskaleresEl && eskaleresEl.checked) params.set('eskaleres_only', '1');
      tbody.innerHTML = '<tr><td colspan="' + colCount + '" class="text-muted">Laster…</td></tr>';
      getJson(urls.scenarioSearch + '?' + params.toString()).then(function (data) {
        if (!data.ok) {
          tbody.innerHTML = '<tr><td colspan="' + colCount + '" class="text-danger">' + (data.error || 'Feil') + '</td></tr>';
          return;
        }
        if (!data.scenarios.length) {
          tbody.innerHTML = '<tr><td colspan="' + colCount + '" class="text-muted">Ingen treff.</td></tr>';
          return;
        }
        tbody.innerHTML = '';
        data.scenarios.forEach(function (s) {
          var tr = document.createElement('tr');
          var mapped = (s.mappings || []).map(function (m) { return m.display_code; }).join(', ');
          var curLabel = scenarioCurrentLabel(s);
          var resLabel = scenarioResidualLabel(s);
          tr.innerHTML =
            '<td><input type="checkbox" class="kartlegging-scenario-cb" value="' + s.pk + '"></td>' +
            '<td>' + escapeHtml(s.display_id) + '</td>' +
            '<td>' + escapeHtml((s.virksomhet ? s.virksomhet + ' – ' : '') + s.scope_title) + '</td>' +
            '<td>' + escapeHtml(s.uonsket_hendelse.substring(0, 100)) + '</td>' +
            '<td class="kartlegging-risk-cell">' + riskLevelTag(curLabel, s.current_css || s.risiko_css) + '</td>' +
            '<td class="kartlegging-risk-cell">' + riskLevelTag(resLabel, s.residual_css || s.restrisiko_css) + '</td>' +
            '<td>' + escapeHtml(mapped) + '</td>';
          tbody.appendChild(tr);
        });
      });
    }

    document.getElementById('kartlegging-search').addEventListener('click', search);
    document.getElementById('kartlegging-link-btn').addEventListener('click', function () {
      var nodePk = nodeSelect.value;
      var ids = Array.prototype.map.call(
        document.querySelectorAll('.kartlegging-scenario-cb:checked'),
        function (cb) { return parseInt(cb.value, 10); }
      );
      if (!nodePk || !ids.length) {
        alert('Velg scenarioer og underkategori.');
        return;
      }
      postJson(urls.linkCreate, { node_pk: parseInt(nodePk, 10), scenario_ids: ids }).then(function (data) {
        if (!data.ok) {
          alert(data.error || 'Kunne ikke knytte');
          return;
        }
        search();
      });
    });

    var selectAll = document.getElementById('kartlegging-select-all');
    if (selectAll) {
      selectAll.addEventListener('change', function () {
        document.querySelectorAll('.kartlegging-scenario-cb').forEach(function (cb) {
          cb.checked = selectAll.checked;
        });
      });
    }

    loadNodes();
    search();
  }

  function initEditor(root) {
    if (!root) return;
    var urls = parseUrls(root);
    var treeRoot = document.getElementById('rammeverk-tree-root');
    var cachedTree = [];
    var cachedCategories = [];

    function renderTree(tree) {
      if (!treeRoot) return;
      treeRoot.innerHTML = '';
      tree.forEach(function (cat) {
        var card = document.createElement('div');
        card.className = 'card mb-2';
        card.innerHTML =
          '<div class="card-header py-2 d-flex justify-content-between">' +
          '<strong>' + cat.display_code + '. ' + escapeHtml(cat.title) + '</strong>' +
          '<span><button type="button" class="btn btn-outline-secondary btn-sm js-edit-node" data-pk="' + cat.pk + '">Rediger</button> ' +
          '<button type="button" class="btn btn-outline-success btn-sm js-add-child" data-parent="' + cat.pk + '">+ Underkategori</button></span></div>' +
          '<ul class="list-group list-group-flush"></ul>';
        var ul = card.querySelector('ul');
        (cat.children || []).forEach(function (child) {
          var li = document.createElement('li');
          li.className = 'list-group-item py-2 d-flex justify-content-between';
          li.innerHTML =
            '<span><strong>' + child.display_code + '</strong> ' + escapeHtml(child.title) + '</span>' +
            '<button type="button" class="btn btn-outline-secondary btn-sm js-edit-node" data-pk="' + child.pk + '">Rediger</button>';
          ul.appendChild(li);
        });
        treeRoot.appendChild(card);
      });
    }

    function loadCategories() {
      if (!urls.activeNodes) return Promise.resolve();
      return getJson(urls.activeNodes).then(function (data) {
        if (data.ok) {
          cachedCategories = data.categories || [];
        }
      });
    }

    function loadTree() {
      if (!urls.taxonomy) return;
      getJson(urls.taxonomy).then(function (data) {
        if (data.ok) {
          cachedTree = data.tree || [];
          renderTree(cachedTree);
        }
      });
    }

    function findNode(pk, tree) {
      var pkStr = String(pk);
      for (var i = 0; i < tree.length; i++) {
        if (String(tree[i].pk) === pkStr) return tree[i];
        for (var j = 0; j < (tree[i].children || []).length; j++) {
          if (String(tree[i].children[j].pk) === pkStr) return tree[i].children[j];
        }
      }
      return null;
    }

    function populateMoveSelect(currentParentPk) {
      var section = document.getElementById('rammeverk-move-section');
      var sel = document.getElementById('rammeverk-node-move-parent');
      if (!section || !sel) return;
      sel.innerHTML = '';
      cachedCategories.forEach(function (cat) {
        if (String(cat.pk) === String(currentParentPk)) return;
        var opt = document.createElement('option');
        opt.value = cat.pk;
        opt.textContent = cat.display_code + ' ' + cat.title;
        sel.appendChild(opt);
      });
      section.style.display = cachedCategories.length > 1 ? '' : 'none';
    }

    function openNodeModal(node, parentPk) {
      document.getElementById('rammeverk-node-pk').value = node ? node.pk : '';
      document.getElementById('rammeverk-node-parent-pk').value = parentPk || (node ? node.parent_pk : '') || '';
      document.getElementById('rammeverk-node-title').value = node ? node.title : '';
      document.getElementById('rammeverk-node-forklaring').value = node ? node.forklaring : '';
      var numberInfo = document.getElementById('rammeverk-node-number-info');
      if (numberInfo) {
        if (node) {
          numberInfo.textContent = 'Nummer: ' + node.display_code;
        } else {
          numberInfo.textContent = 'Nummer tildeles automatisk ved lagring.';
        }
      }
      document.getElementById('rammeverk-node-modal-title').textContent = node ? 'Rediger node' : 'Ny node';
      var moveSection = document.getElementById('rammeverk-move-section');
      if (moveSection) {
        if (node && node.parent_pk) {
          populateMoveSelect(node.parent_pk);
          moveSection.style.display = '';
        } else {
          moveSection.style.display = 'none';
        }
      }
      window.jQuery('#rammeverk-node-modal').modal('show');
    }

    root.addEventListener('click', function (ev) {
      var editBtn = ev.target.closest('.js-edit-node');
      if (editBtn) {
        var pk = parseInt(editBtn.getAttribute('data-pk'), 10);
        openNodeModal(findNode(pk, cachedTree), null);
        return;
      }
      var addChild = ev.target.closest('.js-add-child');
      if (addChild) {
        openNodeModal(null, addChild.getAttribute('data-parent'));
      }
    });

    document.getElementById('rammeverk-add-category').addEventListener('click', function () {
      openNodeModal(null, null);
    });

    document.getElementById('rammeverk-node-save').addEventListener('click', function () {
      var pk = document.getElementById('rammeverk-node-pk').value;
      var body = {
        title: document.getElementById('rammeverk-node-title').value,
        forklaring: document.getElementById('rammeverk-node-forklaring').value,
        parent_pk: document.getElementById('rammeverk-node-parent-pk').value || null,
      };
      var url = pk ? urls.nodeUpdate.replace('{id}', pk) : urls.nodeCreate;
      postJson(url, body).then(function (data) {
        if (!data.ok) {
          alert(data.error || 'Kunne ikke lagre');
          return;
        }
        window.jQuery('#rammeverk-node-modal').modal('hide');
        loadCategories().then(loadTree);
      });
    });

    var moveBtn = document.getElementById('rammeverk-node-move-btn');
    if (moveBtn) {
      moveBtn.addEventListener('click', function () {
        var pk = document.getElementById('rammeverk-node-pk').value;
        var parentId = document.getElementById('rammeverk-node-move-parent').value;
        if (!pk || !parentId || !urls.nodeMove) return;
        postJson(urls.nodeMove.replace('{id}', pk), { parent_id: parseInt(parentId, 10) }).then(function (data) {
          if (!data.ok) {
            alert(data.error || 'Kunne ikke flytte');
            return;
          }
          window.jQuery('#rammeverk-node-modal').modal('hide');
          loadCategories().then(loadTree);
        });
      });
    }

    loadCategories().then(loadTree);
  }

  window.RisikoRammeverk = {
    initRollup: initRollup,
    initKartlegging: initKartlegging,
    initEditor: initEditor,
  };
})(window);
