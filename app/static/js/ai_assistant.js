/**
 * app/static/js/ai_assistant.js
 *
 * Floating AI assistant widget.
 * - Opens/closes the panel via the toggle button in base.html
 * - Maintains a local conversation history (last 10 turns)
 * - Sends car context (window.AI_CAR_CONTEXT) when on a detail page
 * - Calls POST /api/ai-assistant and streams the response token-by-token
 * - Auto-resizes the textarea, handles Enter-to-send (Shift+Enter for newline)
 * - Quick-prompt chips, clear conversation, and typing indicator
 */

(function () {
  'use strict';

  const API_URL       = '/api/ai-assistant';
  const MAX_HISTORY   = 10;   // pairs kept in context
  const STORAGE_KEY   = 'av_ai_history';

  /* ── DOM refs ── */
  const toggleBtn  = document.getElementById('ai-toggle');
  const panel      = document.getElementById('ai-panel');
  const messagesEl = document.getElementById('ai-messages');
  const inputEl    = document.getElementById('ai-input');
  const sendBtn    = document.getElementById('ai-send');
  const clearBtn   = document.getElementById('ai-clear');
  const chips      = document.querySelectorAll('.ai-chip');

  if (!toggleBtn || !panel) return;

  /* ── Conversation history [{role, content}] ── */
  let history = [];

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      history = raw ? JSON.parse(raw) : [];
    } catch (_) {
      history = [];
    }
  }

  function saveHistory() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-MAX_HISTORY * 2)));
    } catch (_) { /* storage quota */ }
  }

  /* ── CSRF ── */
  function getCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  /* ── Panel open/close ── */
  function openPanel() {
    panel.hidden = false;
    toggleBtn.setAttribute('aria-expanded', 'true');
    inputEl?.focus();
  }

  function closePanel() {
    panel.hidden = true;
    toggleBtn.setAttribute('aria-expanded', 'false');
  }

  toggleBtn.addEventListener('click', () => {
    panel.hidden ? openPanel() : closePanel();
  });

  /* Close on Escape */
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden) closePanel();
  });

  /* ── Append a message bubble ── */
  function appendMessage(role, text) {
    const row = document.createElement('div');
    row.className = `ai-msg ai-msg--${role === 'user' ? 'user' : 'bot'}`;

    const bubble = document.createElement('div');
    bubble.className = 'ai-msg-bubble';
    bubble.textContent = text;

    row.appendChild(bubble);
    messagesEl.appendChild(row);
    scrollToBottom();
    return bubble;
  }

  /* ── Typing indicator ── */
  function showTyping() {
    const row = document.createElement('div');
    row.className = 'ai-msg ai-msg--bot ai-msg-typing';
    row.id = 'ai-typing';
    row.innerHTML = `<div class="ai-msg-bubble">
      <span class="ai-dot"></span>
      <span class="ai-dot"></span>
      <span class="ai-dot"></span>
    </div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function removeTyping() {
    document.getElementById('ai-typing')?.remove();
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  /* ── Build system prompt with optional car context ── */
  function buildSystemPrompt() {
    let base = `You are AutoVault AI, a knowledgeable and friendly automotive assistant 
built into the AutoVault car marketplace. You help users with:
- Buying and selling advice
- Understanding car listings and specs  
- Financing and payment questions
- What to look for in a used car inspection
- Comparing vehicles
- General automotive knowledge

Keep responses concise and practical. Use plain text only, no markdown.`;

    const ctx = window.AI_CAR_CONTEXT;
    if (ctx && ctx.make) {
      base += `\n\nThe user is currently viewing this listing:
${ctx.year} ${ctx.make} ${ctx.model}${ctx.trim ? ' ' + ctx.trim : ''}
Price: ${ctx.price} | Mileage: ${ctx.mileage} | Condition: ${ctx.condition}
Fuel: ${ctx.fuel_type} | Transmission: ${ctx.transmission} | Body: ${ctx.body_type}
Location: ${ctx.city}, ${ctx.state}

Reference this vehicle when relevant to the user's question.`;
    }

    return base;
  }

  /* ── Send a message ── */
  async function sendMessage(text) {
    text = text.trim();
    if (!text) return;

    /* Clear input */
    if (inputEl) {
      inputEl.value = '';
      inputEl.style.height = 'auto';
    }

    /* Hide quick chips after first message */
    const suggestions = document.getElementById('ai-suggestions');
    if (suggestions) suggestions.style.display = 'none';

    /* Append user bubble */
    appendMessage('user', text);

    /* Add to history */
    history.push({ role: 'user', content: text });
    saveHistory();

    /* Disable send while streaming */
    if (sendBtn) sendBtn.disabled = true;
    showTyping();

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken':  getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({
          messages: history.slice(-MAX_HISTORY * 2),
          system:   buildSystemPrompt(),
        }),
      });

      removeTyping();

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        appendMessage('assistant', err.error || 'Something went wrong. Please try again.');
        return;
      }

      const data = await res.json();
      const reply = data.content || 'Sorry, I could not generate a response.';

      /* Stream the reply character-by-character for a typing feel */
      const bubble = appendMessage('assistant', '');
      await streamText(bubble, reply);

      history.push({ role: 'assistant', content: reply });
      saveHistory();

    } catch (err) {
      removeTyping();
      appendMessage('assistant', 'Connection error. Please check your internet and try again.');
      console.error('[ai_assistant] fetch failed:', err);
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      inputEl?.focus();
    }
  }

  /* ── Fake streaming: reveal text char-by-char ── */
  function streamText(el, text) {
    return new Promise(resolve => {
      let i = 0;
      /* Fast stream: ~20 chars/frame to feel responsive without being slow */
      function step() {
        if (i >= text.length) { resolve(); return; }
        const chunk = Math.min(3, text.length - i);
        el.textContent += text.slice(i, i + chunk);
        i += chunk;
        scrollToBottom();
        requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  /* ── Clear conversation ── */
  function clearConversation() {
    history = [];
    saveHistory();
    /* Reset messages to just the welcome */
    messagesEl.innerHTML = `
      <div class="ai-msg ai-msg--bot">
        <div class="ai-msg-bubble">
          Hi! I'm your AutoVault assistant. Ask me anything about buying or selling a car,
          financing, what to look for in a listing, or specific vehicles.
        </div>
      </div>`;
    const suggestions = document.getElementById('ai-suggestions');
    if (suggestions) suggestions.style.display = '';
  }

  /* ── Textarea auto-resize ── */
  if (inputEl) {
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
    });

    /* Enter sends, Shift+Enter inserts newline */
    inputEl.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(inputEl.value);
      }
    });
  }

  /* ── Send button ── */
  sendBtn?.addEventListener('click', () => {
    if (inputEl) sendMessage(inputEl.value);
  });

  /* ── Clear button ── */
  clearBtn?.addEventListener('click', clearConversation);

  /* ── Quick-prompt chips ── */
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt;
      if (prompt) {
        openPanel();
        sendMessage(prompt);
      }
    });
  });

  /* ── Init: restore history and replay into UI ── */
  loadHistory();

  if (history.length > 0) {
    const suggestions = document.getElementById('ai-suggestions');
    if (suggestions) suggestions.style.display = 'none';
    history.forEach(msg => appendMessage(msg.role, msg.content));
  }

})();