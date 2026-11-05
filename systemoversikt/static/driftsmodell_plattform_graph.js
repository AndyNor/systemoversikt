// Change log:
// 2026-11-05: Configurable container/reset – reused on driftsmodell alle overview.
// 2026-11-05: Cytoscape neighborhood graph for driftsmodell detail – platforms linked via overordnet_plattform.

(function () {
  'use strict';

  const IDEAL_EDGE_LENGTH = 140;

  function initDriftsmodellPlattformGraph(config) {
    if (!config || !config.graphElements) {
      return null;
    }

    const containerId = config.containerId || 'driftsmodell_cy';
    const resetBtnId = config.resetBtnId || 'btn-driftsmodell-plattform-graph-reset';
    const container = document.getElementById(containerId);
    if (!container || typeof cytoscape !== 'function') {
      return null;
    }

    const nodes = config.graphElements.nodes || [];
    if (!nodes.length) {
      return null;
    }

    const idealEdgeLength = config.idealEdgeLength || IDEAL_EDGE_LENGTH;
    const nodeSeparation = config.nodeSeparation || 100;
    const scaleByCount = !!config.scaleByCount;

    let maxCount = 1;
    if (scaleByCount) {
      nodes.forEach(function (node) {
        const count = (node.data && node.data.system_count) || 0;
        if (count > maxCount) {
          maxCount = count;
        }
      });
    }

    function nodeSize(count) {
      if (!scaleByCount) {
        return { width: 150, height: 56 };
      }
      const ratio = Math.sqrt(Math.max(count, 1) / maxCount);
      return {
        width: Math.round(110 + ratio * 80),
        height: Math.round(48 + ratio * 28),
      };
    }

    let initialLayoutStarted = false;

    function buildFcoseLayoutOpts() {
      return {
        name: 'fcose',
        fit: false,
        packComponents: true,
        animationDuration: 0,
        idealEdgeLength: idealEdgeLength,
        quality: 'proof',
        numIter: config.numIter || 25000,
        nodeSeparation: nodeSeparation,
        uniformNodeDimensions: false,
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
      runFcoseLayout(function () {
        cy.fit(undefined, 40);
        cy.resize();
      });
    }

    const cy = cytoscape({
      container: container,
      zoomingEnabled: true,
      panningEnabled: true,
      wheelSensitivity: 0.1,
      minZoom: 0.15,
      maxZoom: 3,
      autoungrabify: false,
      boxSelectionEnabled: false,
      elements: {
        nodes: nodes,
        edges: config.graphElements.edges || [],
      },
      style: [
        {
          selector: 'node',
          style: {
            shape: 'data(shape)',
            'background-color': 'data(color)',
            label: 'data(name)',
            'font-size': '11px',
            color: '#222',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': 140,
            width: 150,
            height: 56,
            'border-width': 1,
            'border-color': '#999',
            padding: '8px',
          },
        },
        {
          selector: 'node[?is_current]',
          style: {
            'border-width': 3,
            'border-color': '#2A2859',
            'font-weight': 'bold',
            width: 170,
            height: 64,
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
            width: 'data(linewidth)',
            label: 'data(label)',
            'font-size': '9px',
            color: '#666',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            'target-distance-from-node': 6,
            'source-distance-from-node': 6,
          },
        },
      ],
    });

    if (scaleByCount) {
      cy.nodes().forEach(function (node) {
        const size = nodeSize(node.data('system_count') || 0);
        node.style({
          width: size.width,
          height: size.height,
        });
      });
    }

    cy.on('tap', 'node', function (evt) {
      const href = evt.target.data('href');
      if (!href) {
        return;
      }
      if (evt.target.data('is_current')) {
        return;
      }
      window.location.href = href;
    });

    const resetBtn = document.getElementById(resetBtnId);
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        initialLayoutStarted = false;
        runInitialFcoseLayout();
      });
    }

    if (typeof ResizeObserver === 'function') {
      const observer = new ResizeObserver(function () {
        cy.resize();
        if (!initialLayoutStarted) {
          runInitialFcoseLayout();
        }
      });
      observer.observe(container);
    }

    if (container.clientWidth > 0 && container.clientHeight > 0) {
      runInitialFcoseLayout();
    } else {
      requestAnimationFrame(runInitialFcoseLayout);
    }

    return cy;
  }

  window.initDriftsmodellPlattformGraph = initDriftsmodellPlattformGraph;
})();
