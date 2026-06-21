// Change log:
// 2026-06-21: Apply lock UI after saved viewport restore – fixes pan shift on locked reload.
// 2026-06-21: System detail dependency chart – separate from virksomhet graph JS.
// 2026-06-21: Defer fcose until container is sized; randomize true – fixes diagonal node line.

(function () {
  'use strict';

  const IDEAL_EDGE_LENGTH = 100;
  const BTN_RESET = 'btn-system-avhengigheter-graph-reset';
  const BTN_DOWNLOAD_SVG = 'btn-system-avhengigheter-download-svg';
  const BTN_LOCK = 'btn-system-avhengigheter-graph-lock';

  function initSystemAvhengigheterGraph(config) {
    if (!config || !config.graphElements) {
      return null;
    }

    const container = document.getElementById('cy_ny');
    if (!container || typeof cytoscape !== 'function') {
      return null;
    }

    const CSRF = config.csrf || '';
    const urlSave = config.urlSave || '';
    const urlToggleLock = config.urlToggleLock || '';
    const savedLayout = config.savedLayout || null;
    const systemPk = config.systemPk;
    const canSave = !!config.canSave;

    const hasSaved = !!(savedLayout && savedLayout.positions && Object.keys(savedLayout.positions).length);

    let saveTimeout = null;
    let isRestoring = false;
    let resetInProgress = false;
    let restoreGraceUntil = 0;
    let initialLayoutStarted = false;

    function buildFcoseLayoutOpts() {
      return {
        name: 'fcose',
        fit: false,
        packComponents: true,
        animationDuration: 0,
        idealEdgeLength: IDEAL_EDGE_LENGTH,
        quality: 'proof',
        numIter: 50000,
        nodeSeparation: 80,
        uniformNodeDimensions: true,
        randomize: true,
      };
    }

    function runFcoseLayout(onStop) {
      cy.resize();
      const layout = cy.layout(buildFcoseLayoutOpts());
      if (onStop) {
        layout.one('layoutstop', onStop);
      }
      layout.run();
      return layout;
    }

    function runInitialFcoseLayout() {
      if (initialLayoutStarted) {
        return;
      }
      initialLayoutStarted = true;
      isRestoring = true;
      runFcoseLayout(() => {
        cy.fit(undefined, 50);
        cy.resize();
        isRestoring = false;
        restoreGraceUntil = Date.now() + 200;
      });
    }

    const savedPositionsRaw = {};
    if (hasSaved) {
      for (const [id, p] of Object.entries(savedLayout.positions)) {
        const x = p && Number.isFinite(+p.x) ? +p.x : null;
        const y = p && Number.isFinite(+p.y) ? +p.y : null;
        if (x !== null && y !== null) savedPositionsRaw[id] = { x, y };
      }
    }

    const cy = cytoscape({
      container: container,
      zoomingEnabled: true,
      panningEnabled: true,
      wheelSensitivity: 0.1,
      minZoom: 0.1,
      maxZoom: 5,
      autolock: false,
      autoungrabify: !canSave,
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
            'compound-sizing-wrt-labels': 'exclude',
          },
        },
      ],
      layout: hasSaved
        ? { name: 'preset', positions: savedPositionsRaw, fit: false }
        : { name: 'null' },
    });

    if (!hasSaved) {
      cy.once('render', () => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => runInitialFcoseLayout());
        });
      });
    }

    cy.on('tap', 'node', function () {
      const href = this.data('href');
      if (href) {
        try { window.open(href, '_self'); }
        catch (e) { window.location.href = href; }
      }
    });

    function scheduleSave(source) {
      if (!canSave || !urlSave) {
        return;
      }
      const now = Date.now();
      if (isRestoring || resetInProgress || now < restoreGraceUntil) {
        return;
      }
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => saveLayout(source), 800);
    }

    function clampViewportForCy(cyInstance, z, pan) {
      const minZ = Math.max(0.02, cyInstance.minZoom() || 0.01);
      const maxZ = Math.min(8, cyInstance.maxZoom() || 10);
      const zoom = Math.min(maxZ, Math.max(minZ, Number.isFinite(z) ? z : 1));
      return {
        zoom,
        pan: {
          x: (pan && Number.isFinite(pan.x)) ? pan.x : 0,
          y: (pan && Number.isFinite(pan.y)) ? pan.y : 0,
        },
      };
    }

    async function saveLayout() {
      if (!canSave || !urlSave) {
        return;
      }
      saveTimeout = null;

      const v = clampViewportForCy(cy, cy.zoom(), cy.pan());
      const positions = {};
      cy.nodes(':childless:visible').forEach(n => {
        const p = n.position();
        positions[n.id()] = { x: p.x, y: p.y };
      });

      try {
        await fetch(urlSave, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF,
          },
          credentials: 'same-origin',
          body: JSON.stringify({ positions, zoom: v.zoom, pan: v.pan }),
        });
      } catch (_err) {
        // ignore network errors
      }
    }

    function endRestore() {
      if (!isRestoring) return;
      isRestoring = false;
      restoreGraceUntil = Date.now() + 200;
    }

    function applyViewportOnce(zoom, pan) {
      const v = clampViewportForCy(cy, zoom, pan);
      cy.startBatch();

      if (hasSaved) {
        cy.nodes(':childless').forEach(n => {
          const sp = savedPositionsRaw[n.id()];
          if (sp) n.position(sp);
        });
      }

      cy.zoom(v.zoom);
      cy.pan(v.pan);
      cy.endBatch();
      cy.resize();
      cy.style().update();
    }

    if (hasSaved) {
      isRestoring = true;
      let applied = false;
      function applyOnce() {
        if (applied) return;
        applied = true;
        applyViewportOnce(savedLayout.zoom, savedLayout.pan);
        endRestore();
        applyLockStateUI(isGraphLocked);
      }

      cy.once('render', () => requestAnimationFrame(() => applyOnce()));
      setTimeout(() => applyOnce(), 1000);
    }

    let isGraphLocked = !!(savedLayout && savedLayout.locked);

    function updateLockButton(locked) {
      const lockBtn = document.getElementById(BTN_LOCK);
      if (!lockBtn) return;
      lockBtn.textContent = locked ? '🔒 Lås opp' : 'Lås';
      lockBtn.classList.add('btn', 'btn-sm');
      lockBtn.classList.toggle('btn-danger', locked);
    }

    function applyLockStateUI(locked) {
      updateLockButton(locked);

      cy.autolock(locked);
      if (canSave) {
        cy.autoungrabify(locked);
      }

      if (isRestoring) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            cy.zoomingEnabled(!locked);
            cy.panningEnabled(!locked);
          });
        });
      } else {
        cy.zoomingEnabled(!locked);
        cy.panningEnabled(!locked);
      }
    }

    function scheduleSaveLockedSafe(source) {
      if (!isGraphLocked) {
        scheduleSave(source);
      }
    }

    if (canSave) {
      cy.on('position', 'node', () => scheduleSaveLockedSafe('node'));
      cy.on('pan', () => scheduleSaveLockedSafe('pan'));
      cy.on('zoom', () => scheduleSaveLockedSafe('zoom'));
    }

    if (canSave && urlToggleLock) {
      document.getElementById(BTN_LOCK)
        ?.addEventListener('click', async () => {
          const newState = !isGraphLocked;
          try {
            const r = await fetch(urlToggleLock, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
              },
              credentials: 'same-origin',
              body: JSON.stringify({ locked: newState }),
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
    }

    if (hasSaved) {
      updateLockButton(isGraphLocked);
    } else {
      applyLockStateUI(isGraphLocked);
    }

    document.getElementById(BTN_RESET)
      ?.addEventListener('click', () => {
        resetInProgress = true;

        cy.startBatch();
        cy.nodes(':childless').forEach(n => n.removeData('position'));
        cy.zoom(1);
        cy.pan({ x: 0, y: 0 });
        cy.endBatch();

        runFcoseLayout(() => {
          cy.fit(undefined, 50);
          setTimeout(() => {
            resetInProgress = false;
            restoreGraceUntil = Date.now() + 500;
          }, 0);
        });
      });

    document.getElementById(BTN_DOWNLOAD_SVG)
      ?.addEventListener('click', () => {
        if (typeof cy.svg !== 'function') {
          alert('SVG-eksport er ikke tilgjengelig.');
          return;
        }

        const svgContent = cy.svg({
          full: true,
          scale: 1,
          bg: '#FCFCFC',
        });

        const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
        const filename = `systemavhengigheter_${systemPk}_${new Date().toISOString().replace(/[:.]/g, '-')}.svg`;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });

    return cy;
  }

  window.initSystemAvhengigheterGraph = initSystemAvhengigheterGraph;
})();
