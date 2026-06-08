// Change log:
// 2026-06-08: Extracted from virksomhet_detaljer – dedicated page for dependency graph rendering.

(function () {
  'use strict';

  function initVirksomhetAvhengigheterGraph(config) {
    if (!config || !config.graphElements) {
      return;
    }

    const container = document.getElementById('cy_avhengigheter');
    if (!container || typeof cytoscape !== 'function') {
      return;
    }

    const CSRF = config.csrf || '';
    const urlSave = config.urlSave;
    const urlToggleLock = config.urlToggleLock;
    const savedLayout = config.savedLayout || null;
    const virksomhetPk = config.virksomhetPk;

    const DEBUG = true;
    const log = (...args) => { if (DEBUG) console.log('[Graph]', ...args); };

    const hasSaved = !!(savedLayout && savedLayout.positions && Object.keys(savedLayout.positions).length);
    log('Init: hasSaved =', hasSaved, savedLayout ? {
      zoom: savedLayout.zoom,
      pan: savedLayout.pan,
      positionsCount: Object.keys(savedLayout.positions || {}).length
    } : 'no savedLayout');

    const savedPositionsRaw = {};
    if (hasSaved) {
      for (const [id, p] of Object.entries(savedLayout.positions)) {
        const x = p && Number.isFinite(+p.x) ? +p.x : null;
        const y = p && Number.isFinite(+p.y) ? +p.y : null;
        if (x !== null && y !== null) savedPositionsRaw[id] = { x, y };
      }
    }

    log('Cytoscape init: using layout =', hasSaved ? 'preset' : 'fcose');

    const cy_avhengigheter = cytoscape({
      container: container,

      zoomingEnabled: true,
      panningEnabled: true,
      wheelSensitivity: 0.1,
      minZoom: 0.1,
      maxZoom: 5,
      autolock: false,
      autoungrabify: false,
      boxSelectionEnabled: false,

      elements: config.graphElements,

      style: [
        {
          selector: 'node',
          style: {
            'shape': 'data(shape)',
            'background-color': 'data(color)',
            'label': 'data(name)',
            'font-size': '11px',
          },
        },
        {
          selector: 'edge',
          style: {
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'data(linestyle)',
            'line-color': 'data(linecolor)',
            'target-arrow-color': 'data(linecolor)',
            'width': 'data(linewidth)',
            'target-distance-from-node': 15,
            'source-distance-from-node': 25,
          },
        },
        {
          selector: ':parent',
          style: {
            'label': 'data(name)',
            'background-color': '#F1F9FF',
            'padding': 10,
            'compound-sizing-wrt-labels': 'exclude'
          }
        }
      ],

      layout: hasSaved
        ? { name: 'preset', positions: savedPositionsRaw, fit: false }
        : {
            name: 'fcose',
            fit: true,
            packComponents: true,
            animationDuration: 0,
            idealEdgeLength: 100,
            quality: 'proof',
            numIter: 50000,
            nodeSeparation: 80,
            uniformNodeDimensions: true,
            randomize: false
          }
    });

    cy_avhengigheter.on('tap', 'node', function () {
      const href = this.data('href');
      if (href) {
        log('Node tap → navigating', { id: this.id(), href });
        try { window.open(href, '_self'); }
        catch (e) { window.location.href = href; }
      }
    });

    let saveTimeout = null;
    let isRestoring = false;
    let restoreGraceUntil = 0;

    function scheduleSave(source) {
      const now = Date.now();
      if (isRestoring || now < restoreGraceUntil) {
        return;
      }
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => saveLayout(source), 800);
    }

    function clampViewportForCy(cy, z, pan) {
      const minZ = Math.max(0.02, cy.minZoom() || 0.01);
      const maxZ = Math.min(8, cy.maxZoom() || 10);
      const zoom = Math.min(maxZ, Math.max(minZ, Number.isFinite(z) ? z : 1));
      return {
        zoom,
        pan: {
          x: (pan && Number.isFinite(pan.x)) ? pan.x : 0,
          y: (pan && Number.isFinite(pan.y)) ? pan.y : 0,
        }
      };
    }

    async function saveLayout(source) {
      saveTimeout = null;

      const rawZoom = cy_avhengigheter.zoom();
      const rawPan = cy_avhengigheter.pan();
      const v = clampViewportForCy(cy_avhengigheter, rawZoom, rawPan);

      const positions = {};
      cy_avhengigheter.nodes(':childless:visible').forEach(n => {
        const p = n.position();
        positions[n.id()] = { x: p.x, y: p.y };
      });

      log('SaveLayout → sending', { source, count: Object.keys(positions).length });

      try {
        const resp = await fetch(urlSave, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF
          },
          credentials: 'same-origin',
          body: JSON.stringify({ positions, zoom: v.zoom, pan: v.pan })
        });

        const text = await resp.text();
        if (!resp.ok) {
          log('SaveLayout → non-OK', { status: resp.status, body: text.slice(0, 200) });
        } else {
          log('SaveLayout → success');
        }
      } catch (err) {
        log('SaveLayout → error', err);
      }
    }

    function endRestore(reason) {
      if (!isRestoring) return;
      isRestoring = false;
      restoreGraceUntil = Date.now() + 200;
      log('Restore complete', reason);
    }

    function applyViewportOnce(zoom, pan) {
      const v = clampViewportForCy(cy_avhengigheter, zoom, pan);
      cy_avhengigheter.startBatch();

      if (hasSaved) {
        cy_avhengigheter.nodes(':childless').forEach(n => {
          const sp = savedPositionsRaw[n.id()];
          if (sp) n.position(sp);
        });
      }

      cy_avhengigheter.zoom(v.zoom);
      cy_avhengigheter.pan(v.pan);

      cy_avhengigheter.endBatch();
      cy_avhengigheter.resize();
      cy_avhengigheter.style().update();
    }

    if (hasSaved) {
      isRestoring = true;
      log('Restore start');

      let applied = false;
      function applyOnce(reason) {
        if (applied) return;
        applied = true;
        log('Applying saved viewport', reason);
        applyViewportOnce(savedLayout.zoom, savedLayout.pan);
        endRestore(reason);
      }

      cy_avhengigheter.once('render', () =>
        requestAnimationFrame(() => applyOnce('after-first-render'))
      );

      setTimeout(() => applyOnce('fallback-timeout'), 1000);
    } else {
      log('No saved layout → fcose');
    }

    let isGraphLocked = !!(savedLayout && savedLayout.locked);

    function applyLockStateUI(locked) {
      const btn = document.getElementById('btn-avhengigheter-graph-lock');
      if (!btn) return;

      btn.textContent = locked ? '🔒 Lås opp' : 'Lås';
      btn.classList.add('btn');
      btn.classList.toggle('btn-danger', locked);

      cy_avhengigheter.autolock(locked);
      cy_avhengigheter.autoungrabify(locked);

      if (isRestoring) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            cy_avhengigheter.zoomingEnabled(!locked);
            cy_avhengigheter.panningEnabled(!locked);
          });
        });
      } else {
        cy_avhengigheter.zoomingEnabled(!locked);
        cy_avhengigheter.panningEnabled(!locked);
      }

      log('Lock state:', locked);
    }

    function scheduleSaveLockedSafe(source) {
      if (isGraphLocked) {
        return;
      }
      scheduleSave(source);
    }

    cy_avhengigheter.off('position');
    cy_avhengigheter.off('pan');
    cy_avhengigheter.off('zoom');

    cy_avhengigheter.on('position', 'node', () => scheduleSaveLockedSafe('node'));
    cy_avhengigheter.on('pan', () => scheduleSaveLockedSafe('pan'));
    cy_avhengigheter.on('zoom', () => scheduleSaveLockedSafe('zoom'));

    document.getElementById('btn-avhengigheter-graph-lock')
      ?.addEventListener('click', async () => {
        const newState = !isGraphLocked;
        try {
          const r = await fetch(urlToggleLock, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': CSRF
            },
            credentials: 'same-origin',
            body: JSON.stringify({ locked: newState })
          });
          const result = await r.json();
          if (result.ok) {
            isGraphLocked = result.locked;
            applyLockStateUI(isGraphLocked);
          } else {
            alert('Kunne ikke endre låsestatus.');
          }
        } catch {
          alert('Nettverksfeil ved toggling av lås.');
        }
      });

    applyLockStateUI(isGraphLocked);

    document.getElementById('btn-avhengighetergraph-graph-reset')
      ?.addEventListener('click', () => {
        isRestoring = true;

        cy_avhengigheter.startBatch();
        cy_avhengigheter.nodes(':childless').forEach(n => n.removeData('position'));
        cy_avhengigheter.zoom(1);
        cy_avhengigheter.pan({ x: 0, y: 0 });
        cy_avhengigheter.endBatch();

        const layout = cy_avhengigheter.layout({
          name: 'fcose',
          fit: false,
          packComponents: true,
          animationDuration: 0,
          idealEdgeLength: 100,
          quality: 'proof',
          numIter: 50000,
          nodeSeparation: 80,
          uniformNodeDimensions: true,
          randomize: false
        });

        layout.run();

        cy_avhengigheter.once('layoutstop', () => {
          cy_avhengigheter.fit(undefined, 50);
          setTimeout(() => {
            isRestoring = false;
            restoreGraceUntil = Date.now() + 200;
          }, 0);
        });
      });

    function downloadLayoutAsFile() {
      const positions = {};
      cy_avhengigheter.nodes(':childless:visible').forEach(n => {
        const p = n.position();
        positions[n.id()] = { x: p.x, y: p.y };
      });

      const payload = {
        positions,
        zoom: cy_avhengigheter.zoom(),
        pan: cy_avhengigheter.pan()
      };

      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const filename = `graph_layout_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      URL.revokeObjectURL(url);
    }

    document.getElementById('btn-avhengighetergraph-download')
      ?.addEventListener('click', downloadLayoutAsFile);

    function downloadGraphAsSvg() {
      if (typeof cy_avhengigheter.svg !== 'function') {
        alert('SVG-eksport er ikke tilgjengelig.');
        return;
      }

      const svgContent = cy_avhengigheter.svg({
        full: true,
        scale: 1,
        bg: '#FCFCFC',
      });

      const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
      const filename = `systemavhengigheter_${virksomhetPk}_${new Date().toISOString().replace(/[:.]/g, '-')}.svg`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    document.getElementById('btn-avhengighetergraph-download-svg')
      ?.addEventListener('click', downloadGraphAsSvg);

    function applyImportedLayout(data) {
      if (!data || typeof data !== 'object') {
        alert('Ugyldig layoutfil.');
        return;
      }

      const { positions, zoom, pan } = data;

      if (!positions || typeof positions !== 'object') {
        alert("Layoutfil mangler 'positions'.");
        return;
      }

      log('Import layout');

      isRestoring = true;

      cy_avhengigheter.startBatch();

      cy_avhengigheter.nodes(':childless').forEach(n => {
        const pos = positions[n.id()];
        if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
          n.position({ x: pos.x, y: pos.y });
        }
      });

      if (Number.isFinite(zoom)) cy_avhengigheter.zoom(zoom);
      if (pan && Number.isFinite(pan.x) && Number.isFinite(pan.y)) {
        cy_avhengigheter.pan(pan);
      }

      cy_avhengigheter.endBatch();

      cy_avhengigheter.resize();
      cy_avhengigheter.style().update();

      setTimeout(() => {
        isRestoring = false;
        restoreGraceUntil = Date.now() + 300;
      }, 100);
    }

    document.getElementById('btn-avhengigheter-graph-upload')
      ?.addEventListener('click', () => {
        document.getElementById('btn-avhengigheter-btn-avhengigheter-graph-upload-input').click();
      });

    document.getElementById('btn-avhengigheter-btn-avhengigheter-graph-upload-input')
      ?.addEventListener('change', evt => {
        const fileInput = evt.target;
        const file = fileInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
          try {
            const data = JSON.parse(reader.result);
            applyImportedLayout(data);
          } catch {
            alert('Kunne ikke lese JSON.');
          }
          fileInput.value = '';
        };

        reader.readAsText(file);
      });
  }

  window.initVirksomhetAvhengigheterGraph = initVirksomhetAvhengigheterGraph;
})();
