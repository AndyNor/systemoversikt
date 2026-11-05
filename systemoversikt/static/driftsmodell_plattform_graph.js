// Change log:
// 2026-11-05: Badge color gradient by system_count; fcose must include edges (fixes flat grid).
// 2026-11-05: Heat map from tilgjengelighetsvurdering; count badges beside nodes; no size-by-count scaling.
// 2026-11-05: Optional toggle collapses platforms named «Lokal drift …» into one graph node.
// 2026-11-05: Configurable container/reset – reused on driftsmodell alle overview.
// 2026-11-05: Cytoscape neighborhood graph for driftsmodell detail – platforms linked via overordnet_plattform.

(function () {
  'use strict';

  const IDEAL_EDGE_LENGTH = 140;
  const LOKAL_DRIFT_GROUP_ID = 'gruppe_lokal_drift';
  const HEAT_COOL = [168, 213, 229];
  const HEAT_HOT = [192, 57, 43];
  const HEAT_NEUTRAL = '#E8E8E8';
  // 2026-11-05: Count badge: few systems = light blue, many = light red.
  const BADGE_COOL = [174, 214, 241];
  const BADGE_HOT = [245, 183, 177];
  const BADGE_TEXT_DARK = '#1a1a1a';

  function cloneElements(elements) {
    return JSON.parse(JSON.stringify(elements || []));
  }

  function lerpColor(cool, hot, t) {
    const clamped = Math.max(0, Math.min(1, Number(t) || 0));
    const rgb = cool.map(function (c, i) {
      return Math.round(c + (hot[i] - c) * clamped);
    });
    return (
      '#' +
      rgb
        .map(function (v) {
          return ('0' + v.toString(16)).slice(-2);
        })
        .join('')
    );
  }

  function heatColorFromShare(heat) {
    if (heat === null || heat === undefined || isNaN(heat)) {
      return HEAT_NEUTRAL;
    }
    return lerpColor(HEAT_COOL, HEAT_HOT, heat);
  }

  function badgeColorFromCount(count, minCount, maxCount) {
    if (maxCount <= minCount) {
      return lerpColor(BADGE_COOL, BADGE_HOT, 0.5);
    }
    const t = (Number(count) - minCount) / (maxCount - minCount);
    return lerpColor(BADGE_COOL, BADGE_HOT, t);
  }

  function emptyFordeling() {
    return { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, uvurdert: 0 };
  }

  function mergeFordeling(into, from) {
    const result = into || emptyFordeling();
    const src = from || emptyFordeling();
    [1, 2, 3, 4, 5].forEach(function (key) {
      const add = src[key] || src[String(key)] || 0;
      result[key] = (result[key] || 0) + add;
    });
    result.uvurdert = (result.uvurdert || 0) + (src.uvurdert || 0);
    return result;
  }

  function buildGroupedElements(baseNodes, baseEdges, groupLokalDrift) {
    if (!groupLokalDrift) {
      return {
        nodes: cloneElements(baseNodes),
        edges: cloneElements(baseEdges),
      };
    }

    const lokalIds = {};
    let lokalCount = 0;
    let systemSum = 0;
    let hoySum = 0;
    let vurdertSum = 0;
    let fordeling = emptyFordeling();
    const otherNodes = [];

    (baseNodes || []).forEach(function (node) {
      const data = node.data || {};
      if (data.is_lokal_drift) {
        lokalIds[data.id] = true;
        lokalCount += 1;
        systemSum += data.system_count || 0;
        hoySum += data.hoy_kritisk_count || 0;
        vurdertSum += data.vurdert_count || 0;
        fordeling = mergeFordeling(fordeling, data.tilgjengelighet_fordeling);
        return;
      }
      otherNodes.push(node);
    });

    if (lokalCount < 2) {
      return {
        nodes: cloneElements(baseNodes),
        edges: cloneElements(baseEdges),
      };
    }

    const heat = vurdertSum ? hoySum / vurdertSum : null;
    const heatColor = heatColorFromShare(heat);
    const groupLabelParts = ['Lokal drift', lokalCount + ' plattformer'];
    if (hoySum) {
      groupLabelParts.push(hoySum + ' høy');
    }

    otherNodes.push({
      data: {
        id: LOKAL_DRIFT_GROUP_ID,
        name: groupLabelParts.join('\n'),
        plattform_navn: 'Lokal drift',
        system_count: systemSum,
        hoy_kritisk_count: hoySum,
        vurdert_count: vurdertSum,
        heat: heat,
        heat_color: heatColor,
        tilgjengelighet_fordeling: fordeling,
        is_group: true,
        is_lokal_drift: false,
        is_current: false,
        shape: 'roundrectangle',
        color: heatColor,
        href: null,
      },
    });

    const edgeKeys = {};
    const newEdges = [];
    (baseEdges || []).forEach(function (edge) {
      const data = edge.data || {};
      let source = data.source;
      let target = data.target;
      const sourceLokal = !!lokalIds[source];
      const targetLokal = !!lokalIds[target];
      if (sourceLokal && targetLokal) {
        return;
      }
      if (sourceLokal) {
        source = LOKAL_DRIFT_GROUP_ID;
      }
      if (targetLokal) {
        target = LOKAL_DRIFT_GROUP_ID;
      }
      if (source === target) {
        return;
      }
      const key = source + '->' + target;
      if (edgeKeys[key]) {
        return;
      }
      edgeKeys[key] = true;
      newEdges.push({
        data: {
          id: 'edge_grp_' + key.replace(/[^a-zA-Z0-9_>-]/g, '_'),
          source: source,
          target: target,
          linestyle: data.linestyle || 'solid',
          linecolor: data.linecolor || '#888',
          linewidth: data.linewidth || 2,
          label: data.label || 'kjører på',
        },
      });
    });

    return { nodes: otherNodes, edges: newEdges };
  }

  function initDriftsmodellPlattformGraph(config) {
    if (!config || !config.graphElements) {
      return null;
    }

    const containerId = config.containerId || 'driftsmodell_cy';
    const resetBtnId = config.resetBtnId || 'btn-driftsmodell-plattform-graph-reset';
    const groupToggleId = config.groupLokalDriftToggleId || null;
    const showCountBadges = !!config.showCountBadges;
    const container = document.getElementById(containerId);
    if (!container || typeof cytoscape !== 'function') {
      return null;
    }

    const baseNodes = cloneElements(config.graphElements.nodes || []);
    const baseEdges = cloneElements(config.graphElements.edges || []);
    if (!baseNodes.length) {
      return null;
    }

    const lokalDriftCount = baseNodes.filter(function (node) {
      return !!(node.data && node.data.is_lokal_drift);
    }).length;
    const canGroupLokalDrift = lokalDriftCount >= 2;

    let groupLokalDrift = canGroupLokalDrift && config.groupLokalDriftDefault !== false;
    const idealEdgeLength = config.idealEdgeLength || IDEAL_EDGE_LENGTH;
    const nodeSeparation = config.nodeSeparation || 100;

    let layoutGeneration = 0;
    let syncingBadges = false;

    function platformNodes() {
      return cy.nodes().filter(function (node) {
        return !node.data('is_count_badge');
      });
    }

    function badgeIdFor(nodeId) {
      return 'badge_' + nodeId;
    }

    function removeCountBadges() {
      cy.nodes('[?is_count_badge]').remove();
    }

    function countRange() {
      let minCount = null;
      let maxCount = null;
      platformNodes().forEach(function (node) {
        const count = node.data('system_count');
        if (count === null || count === undefined) {
          return;
        }
        const n = Number(count);
        if (minCount === null || n < minCount) {
          minCount = n;
        }
        if (maxCount === null || n > maxCount) {
          maxCount = n;
        }
      });
      if (minCount === null) {
        return { minCount: 0, maxCount: 0 };
      }
      return { minCount: minCount, maxCount: maxCount };
    }

    function positionBadgeForNode(node) {
      if (!showCountBadges || node.data('is_count_badge')) {
        return;
      }
      const badge = cy.getElementById(badgeIdFor(node.id()));
      if (badge.empty()) {
        return;
      }
      const bb = node.boundingBox({ includeLabels: false });
      badge.position({
        x: bb.x2 + 14,
        y: bb.y1 + 10,
      });
    }

    function syncCountBadges() {
      if (!showCountBadges || syncingBadges) {
        return;
      }
      syncingBadges = true;
      try {
        const range = countRange();
        const keep = {};
        platformNodes().forEach(function (node) {
          const count = node.data('system_count');
          if (count === null || count === undefined) {
            return;
          }
          const id = badgeIdFor(node.id());
          keep[id] = true;
          const color = badgeColorFromCount(count, range.minCount, range.maxCount);
          let badge = cy.getElementById(id);
          if (badge.empty()) {
            cy.add({
              group: 'nodes',
              data: {
                id: id,
                name: String(count),
                system_count: count,
                is_count_badge: true,
                shape: 'ellipse',
                color: color,
                href: null,
              },
              grabbable: false,
              selectable: false,
            });
            badge = cy.getElementById(id);
          } else {
            badge.data('name', String(count));
            badge.data('system_count', count);
            badge.data('color', color);
          }
          positionBadgeForNode(node);
        });
        cy.nodes('[?is_count_badge]').forEach(function (badge) {
          if (!keep[badge.id()]) {
            badge.remove();
          }
        });
      } finally {
        syncingBadges = false;
      }
    }

    function buildFcoseLayoutOpts() {
      // 2026-11-05: Include edges – layout on nodes-only made a flat grid with no clustering.
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
        nodeRepulsion: 4500,
        edgeElasticity: 0.45,
      };
    }

    function runFcoseLayout(onStop) {
      cy.resize();
      removeCountBadges();
      const generation = ++layoutGeneration;
      const layout = cy.layout(buildFcoseLayoutOpts());
      if (onStop) {
        layout.one('layoutstop', function () {
          if (generation !== layoutGeneration) {
            return;
          }
          onStop();
        });
      }
      layout.run();
      return layout;
    }

    function fitAfterLayout() {
      syncCountBadges();
      cy.fit(undefined, 40);
      cy.resize();
      syncCountBadges();
    }

    function loadElements(groupLokal) {
      const elements = buildGroupedElements(baseNodes, baseEdges, groupLokal && canGroupLokalDrift);
      cy.elements().remove();
      cy.add(elements);
      runFcoseLayout(fitAfterLayout);
    }

    const initialElements = buildGroupedElements(baseNodes, baseEdges, groupLokalDrift);

    const cy = cytoscape({
      container: container,
      zoomingEnabled: true,
      panningEnabled: true,
      wheelSensitivity: 0.1,
      minZoom: 0.15,
      maxZoom: 3,
      autoungrabify: false,
      boxSelectionEnabled: false,
      elements: initialElements,
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
          selector: 'node[?is_group]',
          style: {
            'border-width': 2,
            'border-style': 'dashed',
            'border-color': '#666',
            'font-weight': 'bold',
            width: 170,
            height: 64,
          },
        },
        {
          selector: 'node[?is_count_badge]',
          style: {
            shape: 'ellipse',
            'background-color': 'data(color)',
            label: 'data(name)',
            color: BADGE_TEXT_DARK,
            'font-size': '10px',
            'font-weight': 'bold',
            'text-valign': 'center',
            'text-halign': 'center',
            width: 28,
            height: 28,
            'border-width': 1,
            'border-color': '#fff',
            padding: 0,
            'z-index': 10,
            'text-max-width': 40,
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

    cy.on('tap', 'node', function (evt) {
      const node = evt.target;
      if (node.data('is_count_badge') || node.data('is_group') || node.data('is_current')) {
        return;
      }
      const href = node.data('href');
      if (!href) {
        return;
      }
      window.location.href = href;
    });

    cy.on('drag', 'node', function (evt) {
      if (!showCountBadges || evt.target.data('is_count_badge')) {
        return;
      }
      positionBadgeForNode(evt.target);
    });

    cy.on('position', 'node', function (evt) {
      if (!showCountBadges || evt.target.data('is_count_badge') || syncingBadges) {
        return;
      }
      positionBadgeForNode(evt.target);
    });

    function syncGroupToggleUi() {
      const toggleBtn = groupToggleId ? document.getElementById(groupToggleId) : null;
      if (!toggleBtn) {
        return;
      }
      if (!canGroupLokalDrift) {
        toggleBtn.style.display = 'none';
        return;
      }
      toggleBtn.style.display = '';
      toggleBtn.setAttribute('aria-pressed', groupLokalDrift ? 'true' : 'false');
      toggleBtn.classList.toggle('active', groupLokalDrift);
      toggleBtn.textContent = groupLokalDrift
        ? 'Vis lokal drift separat'
        : 'Grupper lokal drift';
    }

    const toggleBtn = groupToggleId ? document.getElementById(groupToggleId) : null;
    if (toggleBtn && canGroupLokalDrift) {
      toggleBtn.addEventListener('click', function () {
        groupLokalDrift = !groupLokalDrift;
        syncGroupToggleUi();
        loadElements(groupLokalDrift);
      });
    }
    syncGroupToggleUi();

    const resetBtn = document.getElementById(resetBtnId);
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        loadElements(groupLokalDrift);
      });
    }

    let initialLayoutStarted = false;
    function runInitialFcoseLayout() {
      if (initialLayoutStarted) {
        return;
      }
      initialLayoutStarted = true;
      runFcoseLayout(fitAfterLayout);
    }

    if (typeof ResizeObserver === 'function') {
      const observer = new ResizeObserver(function () {
        cy.resize();
        if (!initialLayoutStarted) {
          runInitialFcoseLayout();
        } else if (showCountBadges) {
          syncCountBadges();
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
