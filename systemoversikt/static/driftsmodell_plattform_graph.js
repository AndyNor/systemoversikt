// Change log:
// 2026-11-05: Larger node label font (~2x) to match node size.
// 2026-11-05: Virksomhet filter on → show lokal drift separately; off → group again.
// 2026-11-05: Type color as left stripe only (not full node fill).
// 2026-11-05: Virksomhet filter = single toggle (all vs one org); not multi-checkbox.
// 2026-11-05: Dual fixed-color badges inside nodes; virksomhet filter; type colors (no heat/badge gradients).
// 2026-11-05: Badge color gradient by system_count; fcose must include edges (fixes flat grid).
// 2026-11-05: Heat map from tilgjengelighetsvurdering; count badges beside nodes; no size-by-count scaling.
// 2026-11-05: Optional toggle collapses platforms named «Lokal drift …» into one graph node.
// 2026-11-05: Configurable container/reset – reused on driftsmodell alle overview.
// 2026-11-05: Cytoscape neighborhood graph for driftsmodell detail – platforms linked via overordnet_plattform.

(function () {
  'use strict';

  const IDEAL_EDGE_LENGTH = 140;
  const LOKAL_DRIFT_GROUP_ID = 'gruppe_lokal_drift';
  const VIRKSOMHET_NONE = '';
  // 2026-11-05: Fixed badge colors (no gradient) – system count vs høy tilgjengelighet.
  const BADGE_SYSTEM_COLOR = '#d6eaf8';
  const BADGE_HOY_COLOR = '#f5b7b1';
  const BADGE_TEXT_DARK = '#1a1a1a';
  // 2026-11-05: Node body is neutral; type color only on a left stripe.
  const NODE_BODY_COLOR = '#F7F7F9';
  const NODE_STRIPE_WIDTH_PCT = '10%';

  function stripeGradientStops(color) {
    const c = color || '#E8E8E8';
    return c + ' ' + c + ' ' + NODE_BODY_COLOR + ' ' + NODE_BODY_COLOR;
  }

  function stripeGradientPositions() {
    return '0% ' + NODE_STRIPE_WIDTH_PCT + ' ' + NODE_STRIPE_WIDTH_PCT + ' 100%';
  }

  function cloneElements(elements) {
    return JSON.parse(JSON.stringify(elements || []));
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

  function virksomhetKey(virksomhetId) {
    if (virksomhetId === null || virksomhetId === undefined || virksomhetId === '') {
      return VIRKSOMHET_NONE;
    }
    return String(virksomhetId);
  }

  function filterElementsByVirksomhet(baseNodes, baseEdges, selectedKeys) {
    if (!selectedKeys) {
      return {
        nodes: cloneElements(baseNodes),
        edges: cloneElements(baseEdges),
      };
    }
    const allowed = {};
    selectedKeys.forEach(function (key) {
      allowed[key] = true;
    });
    const nodes = [];
    const keepIds = {};
    (baseNodes || []).forEach(function (node) {
      const data = node.data || {};
      const key = virksomhetKey(data.virksomhet_id);
      if (!allowed[key]) {
        return;
      }
      nodes.push(node);
      keepIds[data.id] = true;
    });
    const edges = [];
    (baseEdges || []).forEach(function (edge) {
      const data = edge.data || {};
      if (keepIds[data.source] && keepIds[data.target]) {
        edges.push(edge);
      }
    });
    return { nodes: cloneElements(nodes), edges: cloneElements(edges) };
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

    otherNodes.push({
      data: {
        id: LOKAL_DRIFT_GROUP_ID,
        name: 'Lokal drift\n' + lokalCount + ' plattformer',
        plattform_navn: 'Lokal drift',
        system_count: systemSum,
        hoy_kritisk_count: hoySum,
        vurdert_count: vurdertSum,
        tilgjengelighet_fordeling: fordeling,
        is_group: true,
        is_lokal_drift: false,
        is_current: false,
        shape: 'roundrectangle',
        color: '#E8E8E8',
        href: null,
        virksomhet_id: null,
        virksomhet_forkortelse: null,
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
    const virksomhetFilterId = config.virksomhetFilterContainerId || null;
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
        return !node.data('is_count_badge') && !node.data('is_hoy_badge');
      });
    }

    function isBadgeNode(node) {
      return !!(node.data('is_count_badge') || node.data('is_hoy_badge'));
    }

    function systemBadgeIdFor(nodeId) {
      return 'badge_sys_' + nodeId;
    }

    function hoyBadgeIdFor(nodeId) {
      return 'badge_hoy_' + nodeId;
    }

    function removeCountBadges() {
      cy.nodes('[?is_count_badge], [?is_hoy_badge]').remove();
    }

    function positionBadgesForNode(node) {
      if (!showCountBadges || isBadgeNode(node)) {
        return;
      }
      const bb = node.boundingBox({ includeLabels: false });
      const sysBadge = cy.getElementById(systemBadgeIdFor(node.id()));
      const hoyBadge = cy.getElementById(hoyBadgeIdFor(node.id()));
      // 2026-11-05: Stack badges inside the node frame (top-right).
      const badgeX = bb.x2 - 24;
      if (!sysBadge.empty()) {
        sysBadge.position({
          x: badgeX,
          y: bb.y1 + 20,
        });
      }
      if (!hoyBadge.empty()) {
        hoyBadge.position({
          x: badgeX,
          y: bb.y1 + 54,
        });
      }
    }

    function ensureBadge(id, label, color, platformId, flag) {
      let badge = cy.getElementById(id);
      const data = {
        id: id,
        name: String(label),
        is_count_badge: flag === 'system',
        is_hoy_badge: flag === 'hoy',
        platform_id: platformId,
        shape: 'roundrectangle',
        color: color,
        href: null,
      };
      if (badge.empty()) {
        cy.add({
          group: 'nodes',
          data: data,
          grabbable: false,
          selectable: false,
        });
        badge = cy.getElementById(id);
      } else {
        badge.data('name', data.name);
        badge.data('color', color);
        badge.data('platform_id', platformId);
        badge.data('is_count_badge', data.is_count_badge);
        badge.data('is_hoy_badge', data.is_hoy_badge);
      }
      return badge;
    }

    function syncCountBadges() {
      if (!showCountBadges || syncingBadges) {
        return;
      }
      syncingBadges = true;
      try {
        const keep = {};
        platformNodes().forEach(function (node) {
          const systemCount = node.data('system_count');
          if (systemCount === null || systemCount === undefined) {
            return;
          }
          const hoyCount = node.data('hoy_kritisk_count') || 0;
          const sysId = systemBadgeIdFor(node.id());
          const hoyId = hoyBadgeIdFor(node.id());
          keep[sysId] = true;
          keep[hoyId] = true;
          ensureBadge(sysId, systemCount, BADGE_SYSTEM_COLOR, node.id(), 'system');
          ensureBadge(hoyId, hoyCount, BADGE_HOY_COLOR, node.id(), 'hoy');
          positionBadgesForNode(node);
        });
        cy.nodes('[?is_count_badge], [?is_hoy_badge]').forEach(function (badge) {
          if (!keep[badge.id()]) {
            badge.remove();
          }
        });
      } finally {
        syncingBadges = false;
      }
    }

    // 2026-11-05: null = show all; otherwise only the one active virksomhet key.
    function selectedVirksomhetKeys() {
      if (!virksomhetFilterId) {
        return null;
      }
      const root = document.getElementById(virksomhetFilterId);
      if (!root) {
        return null;
      }
      const active = root.querySelector(
        'button[data-virksomhet-filter].active, [data-virksomhet-filter][aria-pressed="true"]'
      );
      if (!active) {
        return null;
      }
      return [active.value];
    }

    function syncVirksomhetFilterUi(activeBtn) {
      if (!virksomhetFilterId) {
        return;
      }
      const root = document.getElementById(virksomhetFilterId);
      if (!root) {
        return;
      }
      root.querySelectorAll('[data-virksomhet-filter]').forEach(function (btn) {
        const isActive = activeBtn != null && btn === activeBtn;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
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
      const filtered = filterElementsByVirksomhet(
        baseNodes,
        baseEdges,
        selectedVirksomhetKeys()
      );
      const elements = buildGroupedElements(
        filtered.nodes,
        filtered.edges,
        groupLokal && canGroupLokalDrift
      );
      cy.elements().remove();
      cy.add(elements);
      runFcoseLayout(fitAfterLayout);
    }

    const initialFiltered = filterElementsByVirksomhet(
      baseNodes,
      baseEdges,
      selectedVirksomhetKeys()
    );
    const initialElements = buildGroupedElements(
      initialFiltered.nodes,
      initialFiltered.edges,
      groupLokalDrift
    );

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
            // 2026-11-05: Type color as left stripe; rest of node is neutral.
            'background-fill': 'linear-gradient',
            'background-gradient-direction': 'to-right',
            'background-gradient-stop-colors': function (ele) {
              return stripeGradientStops(ele.data('color'));
            },
            'background-gradient-stop-positions': stripeGradientPositions(),
            'background-color': NODE_BODY_COLOR,
            label: 'data(name)',
            // 2026-11-05: Larger labels; nodes widened to fit.
            'font-size': '26px',
            color: '#222',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': showCountBadges ? 200 : 250,
            width: showCountBadges ? 270 : 250,
            height: showCountBadges ? 108 : 92,
            'border-width': 1,
            'border-color': '#999',
            padding: '8px',
            cursor: 'pointer',
          },
        },
        {
          selector: 'node[?is_current]',
          style: {
            'border-width': 3,
            'border-color': '#2A2859',
            'font-weight': 'bold',
            width: showCountBadges ? 290 : 270,
            height: showCountBadges ? 120 : 104,
          },
        },
        {
          selector: 'node[?is_group]',
          style: {
            'border-width': 2,
            'border-style': 'dashed',
            'border-color': '#666',
            'font-weight': 'bold',
            width: showCountBadges ? 290 : 270,
            height: showCountBadges ? 120 : 104,
          },
        },
        {
          selector: 'node[?is_count_badge], node[?is_hoy_badge]',
          style: {
            shape: 'roundrectangle',
            'background-fill': 'solid',
            'background-color': 'data(color)',
            label: 'data(name)',
            color: BADGE_TEXT_DARK,
            'font-size': '16px',
            'font-weight': 'bold',
            'text-valign': 'center',
            'text-halign': 'center',
            width: 44,
            height: 30,
            'border-width': 1,
            'border-color': '#fff',
            padding: 0,
            'z-index': 10,
            'text-max-width': 40,
            cursor: 'pointer',
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

    function navigateFromNode(node) {
      if (node.data('is_group') || node.data('is_current')) {
        return;
      }
      let href = node.data('href');
      if (!href && isBadgeNode(node)) {
        const platform = cy.getElementById(node.data('platform_id'));
        if (!platform.empty()) {
          if (platform.data('is_group') || platform.data('is_current')) {
            return;
          }
          href = platform.data('href');
        }
      }
      if (!href) {
        return;
      }
      window.location.href = href;
    }

    cy.on('tap', 'node', function (evt) {
      navigateFromNode(evt.target);
    });

    cy.on('drag', 'node', function (evt) {
      if (!showCountBadges || isBadgeNode(evt.target)) {
        return;
      }
      positionBadgesForNode(evt.target);
    });

    cy.on('position', 'node', function (evt) {
      if (!showCountBadges || isBadgeNode(evt.target) || syncingBadges) {
        return;
      }
      positionBadgesForNode(evt.target);
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

    if (virksomhetFilterId) {
      const filterRoot = document.getElementById(virksomhetFilterId);
      if (filterRoot) {
        filterRoot.addEventListener('click', function (evt) {
          const btn = evt.target.closest('[data-virksomhet-filter]');
          if (!btn || !filterRoot.contains(btn)) {
            return;
          }
          const turningOff = btn.classList.contains('active');
          syncVirksomhetFilterUi(turningOff ? null : btn);
          // 2026-11-05: One virksomhet → expand lokal drift; show-all → group again.
          if (canGroupLokalDrift) {
            groupLokalDrift = turningOff;
            syncGroupToggleUi();
          }
          loadElements(groupLokalDrift);
        });
      }
    }

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
