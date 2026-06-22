// 2026-06-22: Programvare nodes use ellipse shape – same black label text as other nodes.
// 2026-06-21: Draggable virksomhet compound boxes – move grouped systems together.
// 2026-06-21: Draggable nodes without persistence – autoungrabify false.
// 2026-06-21: Tjeneste detail ecosystem chart – separate from system_systemavhengigheter_graph.js.

(function () {
  'use strict';

  const IDEAL_EDGE_LENGTH = 110;
  const BTN_RESET = 'btn-tjeneste-okosystem-graph-reset';
  const BTN_DOWNLOAD_SVG = 'btn-tjeneste-okosystem-download-svg';

  function initTjenesteOkosystemGraph(config) {
    if (!config || !config.graphElements) {
      return null;
    }

    const container = document.getElementById('tjeneste_cy');
    if (!container || typeof cytoscape !== 'function') {
      return null;
    }

    const tjenestePk = config.tjenestePk;
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
        nodeSeparation: 90,
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
      runFcoseLayout(() => {
        cy.fit(undefined, 50);
        cy.resize();
      });
    }

    const cy = cytoscape({
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
            'color': '#222',
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
          selector: 'edge[?href]',
          style: {
            'cursor': 'pointer',
            'overlay-opacity': 0,
            'overlay-padding': 12,
            'z-index': 10,
          },
        },
        {
          selector: ':parent',
          style: {
            'label': 'data(name)',
            'background-color': 'data(color)',
            'padding': 14,
            'compound-sizing-wrt-labels': 'exclude',
            'font-size': '12px',
            'font-weight': 'bold',
            'cursor': 'grab',
            'text-valign': 'top',
            'text-halign': 'center',
            'text-margin-y': -6,
          },
        },
      ],
      layout: { name: 'null' },
    });

    cy.once('render', () => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => runInitialFcoseLayout());
      });
    });

    let suppressNodeTap = false;

    cy.on('grab', 'node', () => {
      suppressNodeTap = false;
    });

    cy.on('drag', 'node', () => {
      suppressNodeTap = true;
    });

    function navigateFromElement(ele) {
      const href = ele.data('href');
      if (href) {
        if (/^https?:\/\//i.test(href)) {
          window.open(href, '_blank', 'noopener');
        } else {
          window.location.href = href;
        }
      }
    }

    cy.on('tap', 'node', function () {
      if (suppressNodeTap || this.isParent()) {
        return;
      }
      navigateFromElement(this);
    });

    cy.on('tap', function (evt) {
      const ele = evt.target;
      if (ele.isEdge()) {
        navigateFromElement(ele);
      }
    });

    document.getElementById(BTN_RESET)
      ?.addEventListener('click', () => {
        cy.startBatch();
        cy.nodes().forEach(n => n.removeData('position'));
        cy.zoom(1);
        cy.pan({ x: 0, y: 0 });
        cy.endBatch();

        runFcoseLayout(() => {
          cy.fit(undefined, 50);
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
        const filename = `tjeneste_okosystem_${tjenestePk}_${new Date().toISOString().replace(/[:.]/g, '-')}.svg`;
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

  window.initTjenesteOkosystemGraph = initTjenesteOkosystemGraph;
})();
