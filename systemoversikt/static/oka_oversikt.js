// Change log:
// 2026-09-15: Client-side search, nivå filter and expand/collapse for the OKA overview tree.

(function () {
  'use strict';

  function normalize(text) {
    return String(text || '').toLowerCase();
  }

  function isDetails(node) {
    return node && node.tagName === 'DETAILS';
  }

  function ancestors(node) {
    const list = [];
    let current = node.parentElement;
    while (current) {
      if (current.classList && current.classList.contains('oka-node')) {
        list.push(current);
      }
      current = current.parentElement;
    }
    return list;
  }

  document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('oka-oversikt-sok');
    const nivaaSelect = document.getElementById('oka-oversikt-nivaa');
    const utfasetCheck = document.getElementById('oka-oversikt-utfaset');
    const statusEl = document.getElementById('oka-oversikt-status');
    const emptyEl = document.getElementById('oka-oversikt-ingen');
    const utvidBtn = document.getElementById('oka-oversikt-utvid');
    const skjulBtn = document.getElementById('oka-oversikt-skjul');
    if (!searchInput || !nivaaSelect || !utfasetCheck) {
      return;
    }

    const nodes = Array.prototype.slice.call(document.querySelectorAll('.oka-node'));

    function applyFilter() {
      const q = normalize(searchInput.value).trim();
      const nivaa = nivaaSelect.value;
      const visUtfaset = utfasetCheck.checked;
      const filterAktivt = Boolean(q || nivaa);

      nodes.forEach(function (node) {
        node.classList.remove('oka-node--hidden', 'oka-node--treff');
      });

      const treff = [];
      nodes.forEach(function (node) {
        const aktiv = node.getAttribute('data-aktiv') === '1';
        if (!aktiv && !visUtfaset) {
          return;
        }
        if (nivaa && node.getAttribute('data-nivaa') !== nivaa) {
          return;
        }
        const text = normalize(node.getAttribute('data-text'));
        if (q && text.indexOf(q) === -1) {
          return;
        }
        treff.push(node);
      });

      const vis = {};
      treff.forEach(function (node) {
        vis[node.id] = true;
        node.classList.add('oka-node--treff');
        ancestors(node).forEach(function (parent) {
          vis[parent.id] = true;
        });
      });

      nodes.forEach(function (node) {
        const aktiv = node.getAttribute('data-aktiv') === '1';
        if (!aktiv && !visUtfaset) {
          node.classList.add('oka-node--hidden');
          if (isDetails(node)) {
            node.open = false;
          }
          return;
        }
        if (filterAktivt && !vis[node.id]) {
          node.classList.add('oka-node--hidden');
          if (isDetails(node)) {
            node.open = false;
          }
          return;
        }
        if (filterAktivt && isDetails(node) && vis[node.id]) {
          node.open = true;
        }
      });

      const synlige = nodes.filter(function (node) {
        return !node.classList.contains('oka-node--hidden');
      }).length;
      if (statusEl) {
        if (!nodes.length) {
          statusEl.textContent = '';
        } else if (filterAktivt) {
          statusEl.textContent = treff.length + ' treff' +
            (synlige > treff.length ? ' (viser også overordnede)' : '');
        } else {
          statusEl.textContent = synlige + ' koder vises';
        }
      }
      if (emptyEl) {
        emptyEl.hidden = synlige > 0 || nodes.length === 0;
      }
    }

    let timer = null;
    searchInput.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(applyFilter, 150);
    });
    nivaaSelect.addEventListener('change', applyFilter);
    utfasetCheck.addEventListener('change', applyFilter);

    if (utvidBtn) {
      utvidBtn.addEventListener('click', function () {
        nodes.forEach(function (node) {
          if (isDetails(node) && !node.classList.contains('oka-node--hidden')) {
            node.open = true;
          }
        });
      });
    }
    if (skjulBtn) {
      skjulBtn.addEventListener('click', function () {
        nodes.forEach(function (node) {
          if (isDetails(node)) {
            node.open = false;
          }
        });
      });
    }

    applyFilter();
  });
})();
