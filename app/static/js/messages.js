/**
 * app/static/js/messages.js
 *
 * Handles the conversation page.
 * Polls /api/messages/poll every 5 seconds for new incoming messages
 * and appends them without a full reload.
 * Intercepts the send form to submit via AJAX and append optimistically.
 */

(function () {
  'use strict';

  const POLL_INTERVAL = 5000;

  const form     = document.getElementById('send-form');
  const thread   = document.getElementById('thread-scroll');
  const sendBtn  = document.getElementById('send-btn');
  const textarea = document.getElementById('send-content');

  const CAR_ID   = window.CONVO_CAR_ID;
  const OTHER_ID = window.CONVO_OTHER_ID;
  let   lastId   = window.LAST_MSG_ID || 0;

  if (!CAR_ID || !OTHER_ID || !thread) return;

  /* ── CSRF ── */
  function getCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const m = document.cookie.match(/csrf_token=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  /* ── Scroll thread to bottom ── */
  function scrollBottom() {
    thread.scrollTop = thread.scrollHeight;
  }

  /* ── Escape HTML ── */
  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* ── Build a message bubble row ── */
  function buildRow(msg) {
    const mine  = msg.mine;
    const init  = mine ? (document.body.dataset.userInit || '?') : (window.OTHER_INIT || '?');
    const row   = document.createElement('div');
    row.className = `msg-row ${mine ? 'msg-row--mine' : ''}`;
    row.dataset.msgId = msg.id;
    row.innerHTML = `
      <div class="msg-avatar ${mine ? 'msg-avatar--me' : ''}">
        ${init}
      </div>
      <div class="msg-bubble-wrap">
        <div class="msg-bubble ${mine ? 'msg-bubble--mine' : 'msg-bubble--other'}">
          ${esc(msg.content)}
        </div>
        <span class="msg-time">${esc(msg.time)}</span>
      </div>`;
    return row;
  }

  /* ── AJAX send ── */
  if (form) {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const content = textarea ? textarea.value.trim() : '';
      if (!content) return;

      /* Optimistic append */
      const optimistic = buildRow({
        id:      Date.now(),
        mine:    true,
        content: content,
        time:    'just now',
      });
      thread.appendChild(optimistic);
      scrollBottom();

      if (textarea) {
        textarea.value = '';
        textarea.style.height = 'auto';
        const cc = document.getElementById('char-count');
        if (cc) cc.textContent = '0 / 2000';
      }

      if (sendBtn) sendBtn.disabled = true;

      try {
        const res = await fetch('/api/messages/send', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':  getCsrf(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            car_id:      CAR_ID,
            receiver_id: OTHER_ID,
            content:     content,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          /* Replace optimistic row with confirmed id */
          if (data.message_id) {
            optimistic.dataset.msgId = data.message_id;
            lastId = Math.max(lastId, data.message_id);
          }
        } else {
          /* Server rejected — remove optimistic, restore textarea */
          optimistic.remove();
          if (textarea) textarea.value = content;
          showSendError();
        }
      } catch (_) {
        optimistic.remove();
        if (textarea) textarea.value = content;
        showSendError();
      } finally {
        if (sendBtn) sendBtn.disabled = false;
        textarea?.focus();
      }
    });
  }

  /* ── Poll for new messages ── */
  async function poll() {
    try {
      const url = `/api/messages/poll?car_id=${CAR_ID}&other_id=${OTHER_ID}&since_id=${lastId}`;
      const res = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!res.ok) return;

      const data = await res.json();
      if (!data.messages || data.messages.length === 0) return;

      const wasAtBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 60;

      data.messages.forEach(msg => {
        /* Skip messages already in DOM */
        if (document.querySelector(`[data-msg-id="${msg.id}"]`)) return;
        thread.appendChild(buildRow(msg));
        lastId = Math.max(lastId, msg.id);
      });

      if (wasAtBottom) scrollBottom();
    } catch (_) {
      /* Polling errors are silent — retry next interval */
    }
  }

  /* ── Send error toast ── */
  function showSendError() {
    const stack = document.querySelector('.toast-stack');
    if (!stack) return;
    const el = document.createElement('div');
    el.className = 'toast toast--danger';
    el.setAttribute('data-toast', '');
    el.innerHTML = `
      <span class="toast-icon"><i class="fa-solid fa-circle-xmark"></i></span>
      <span class="toast-msg">Failed to send. Please try again.</span>
      <button class="toast-close" aria-label="Dismiss" onclick="this.closest('[data-toast]').remove()">
        <i class="fa-solid fa-xmark"></i>
      </button>`;
    stack.appendChild(el);
    setTimeout(() => {
      el.classList.add('toast--out');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    }, 4000);
  }

  /* ── Start polling ── */
  const pollTimer = setInterval(poll, POLL_INTERVAL);

  /* Stop polling when page becomes hidden */
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearInterval(pollTimer);
    }
  });

  /* ── Store user initial for bubble builder ── */
  const nameEl = document.querySelector('.convo-user-name');
  if (nameEl) window.OTHER_INIT = (nameEl.textContent.trim()[0] || '?').toUpperCase();

  const bodyData = document.body;
  /* Inject current user initial via data attribute on body set by base.html */

})();