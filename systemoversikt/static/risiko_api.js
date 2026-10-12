// Change log:
// 2026-10-12: Only treat 401/redirect/session_expired as login expiry – not HTML 500/CSRF pages.
// 2026-08-23: Shared fetch wrapper – session expiry detection, CSRF, and heartbeat for risk AJAX pages.

(function (window) {
  'use strict';

  var DEFAULT_SESSION_PING_URL = '/sikkerhet/risiko/api/session/';
  var DEFAULT_SESSION_PING_MS = 5 * 60 * 1000;
  var sessionPingTimer = null;
  var sessionPingUrl = DEFAULT_SESSION_PING_URL;
  var sessionExpiredPromptShown = false;
  var visibilityListenerBound = false;

  function getCsrfToken() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) {
      return el.value;
    }
    var match = document.cookie.match(/(?:^|;\s*)kartotek_csrf_cookie=([^;]+)/);
    if (match) {
      return decodeURIComponent(match[1]);
    }
    match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function sessionExpiredError(message, response, data) {
    var err = new Error(message || 'Sesjonen er utløpt');
    err.isSessionExpired = true;
    err.status = response ? response.status : 401;
    err.data = data || null;
    return err;
  }

  function isSessionExpiredResponse(response, data) {
    if (!response) {
      return false;
    }
    if (response.redirected) {
      return true;
    }
    if (response.status === 401) {
      return true;
    }
    if (data && data.error === 'session_expired') {
      return true;
    }
    return false;
  }

  function unexpectedResponseError(response) {
    var status = response ? response.status : 0;
    var message =
      status === 403
        ? 'Forespørselen ble avvist. Last siden på nytt og prøv igjen.'
        : status
          ? 'Uventet svar fra serveren (HTTP ' + status + '). Prøv å laste siden på nytt.'
          : 'Uventet svar fra serveren. Prøv å laste siden på nytt.';
    var err = new Error(message);
    err.status = status;
    err.data = null;
    return err;
  }

  function handleSessionExpired() {
    if (sessionExpiredPromptShown) {
      return;
    }
    sessionExpiredPromptShown = true;
    var reload = window.confirm(
      'Innloggingssesjonen er utløpt. Last siden på nytt for å logge inn?'
    );
    if (reload) {
      window.location.reload();
    } else {
      sessionExpiredPromptShown = false;
    }
  }

  function parseJsonResponse(response) {
    var ct = (response.headers.get('content-type') || '').toLowerCase();
    if (isSessionExpiredResponse(response, null)) {
      handleSessionExpired();
      return Promise.reject(sessionExpiredError('Sesjonen er utløpt', response, null));
    }
    if (ct.indexOf('application/json') === -1 && ct.indexOf('+json') === -1) {
      // Non-JSON (HTML 500/CSRF/proxy) – not necessarily a lost login session.
      return Promise.reject(unexpectedResponseError(response));
    }
    return response.text().then(function (text) {
      var data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (e) {
          return Promise.reject(unexpectedResponseError(response));
        }
      } else {
        data = {};
      }
      if (isSessionExpiredResponse(response, data)) {
        handleSessionExpired();
        return Promise.reject(sessionExpiredError('Sesjonen er utløpt', response, data));
      }
      if (!response.ok) {
        var err = new Error((data && data.error) || 'Forespørsel feilet');
        err.data = data;
        err.status = response.status;
        throw err;
      }
      return data;
    });
  }

  function fetchJson(url, options) {
    var opts = options || {};
    opts.credentials = 'same-origin';
    opts.headers = opts.headers || {};
    if (opts.body && !opts.headers['Content-Type'] && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
    }
    var method = (opts.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD' && !opts.headers['X-CSRFToken']) {
      opts.headers['X-CSRFToken'] = opts.csrfToken || getCsrfToken();
    }
    delete opts.csrfToken;
    return fetch(url, opts).then(parseJsonResponse);
  }

  function fetchFormData(url, formData, method, csrfToken) {
    return fetch(url, {
      method: method || 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken || getCsrfToken() },
      body: formData,
    }).then(parseJsonResponse);
  }

  function getJson(url) {
    return fetchJson(url, { method: 'GET' });
  }

  function postJson(url, body, method) {
    return fetchJson(url, {
      method: method || 'POST',
      body: JSON.stringify(body || {}),
    });
  }

  function pingSession() {
    if (document.visibilityState && document.visibilityState !== 'visible') {
      return;
    }
    fetch(sessionPingUrl, { credentials: 'same-origin', method: 'GET' })
      .then(function (response) {
        if (isSessionExpiredResponse(response, null)) {
          handleSessionExpired();
          return null;
        }
        var ct = (response.headers.get('content-type') || '').toLowerCase();
        if (ct.indexOf('application/json') === -1) {
          handleSessionExpired();
          return null;
        }
        return response.json().then(function (data) {
          if (isSessionExpiredResponse(response, data) || !response.ok) {
            handleSessionExpired();
          }
        });
      })
      .catch(function () {
        // Network blips – next user action or ping will retry.
      });
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'visible') {
      pingSession();
    }
  }

  function stopSessionPing() {
    if (sessionPingTimer) {
      clearInterval(sessionPingTimer);
      sessionPingTimer = null;
    }
    if (visibilityListenerBound) {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      visibilityListenerBound = false;
    }
  }

  function startSessionPing(url, intervalMs) {
    stopSessionPing();
    sessionPingUrl = url || DEFAULT_SESSION_PING_URL;
    var ms = typeof intervalMs === 'number' && intervalMs > 0 ? intervalMs : DEFAULT_SESSION_PING_MS;
    sessionPingTimer = setInterval(pingSession, ms);
    if (!visibilityListenerBound) {
      document.addEventListener('visibilitychange', onVisibilityChange);
      visibilityListenerBound = true;
    }
  }

  window.RisikoApi = {
    getCsrfToken: getCsrfToken,
    fetchJson: fetchJson,
    fetchFormData: fetchFormData,
    getJson: getJson,
    postJson: postJson,
    parseJsonResponse: parseJsonResponse,
    isSessionExpiredResponse: isSessionExpiredResponse,
    handleSessionExpired: handleSessionExpired,
    startSessionPing: startSessionPing,
    stopSessionPing: stopSessionPing,
    DEFAULT_SESSION_PING_URL: DEFAULT_SESSION_PING_URL,
  };
})(window);
