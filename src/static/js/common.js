// Common shared utilities for LPS2 UI (chat + admin)
(function(global){
  const state = { AUTH_SESSION:false, CSRF_TOKEN:null, USER:null, IS_ADMIN:false };
  async function refreshAuth(){
    try { const r = await fetch('/auth/status'); if(!r.ok) return state; const j = await r.json(); state.AUTH_SESSION=!!j.authenticated; state.CSRF_TOKEN=j.csrf_token||null; state.USER=j.user||null; state.IS_ADMIN=!!j.is_admin; return state; } catch(e){ return state; }
  }
  // No longer using the separate authHeaders function - 
  // Headers are now managed directly in fetchWithCsrf
  async function fetchWithCsrf(url,opt={}, {unsafe=false}={}){ 
    // Always refresh auth before CSRF-required operations
    if (unsafe) {
      await refreshAuth();
    }
    
    const o = {...opt}; 
    
    // Setup headers
    if (!o.headers) o.headers = {};
    
    // Always set content type for POST/PUT operations
    if ((opt.method === 'POST' || opt.method === 'PUT') && !o.headers['Content-Type']) {
      o.headers['Content-Type'] = 'application/json';
    }
    
    // Add authorization headers (API key or CSRF)
    if (!state.AUTH_SESSION) {
      // API key auth for non-session requests
      if (!o.headers['Authorization'] && !o.headers['X-API-Key']) { 
        o.headers['Authorization'] = 'Bearer ' + (global.LPS2_DEMO_KEY || 'secret12345'); 
      }
    } else if (unsafe) {
      // Add CSRF token directly for unsafe methods when using session auth
      if (state.CSRF_TOKEN) {
        o.headers['X-CSRF-Token'] = state.CSRF_TOKEN;
        
        // Debug log
        console.log(`CSRF Debug: Sending request to ${url} with token ${state.CSRF_TOKEN.substring(0,5)}...`);
      } else {
        console.warn("No CSRF token available for unsafe request!");
      }
    }
    
    // If sending JSON body, make sure it's properly stringified
    if (o.body && typeof o.body === 'object' && !(o.body instanceof FormData)) {
      o.body = JSON.stringify(o.body);
    }
    
    const res = await fetch(url, o); 
    
    if (!res.ok) { 
      let data = {};
      try {
        data = await res.json();
      } catch (e) { 
        console.error("Failed to parse error response", e);
      } 
      
      if (data && (data.error === 'csrf_missing' || data.error === 'csrf_invalid')) {
        console.warn(`CSRF Error: ${data.error} for ${url}. Refreshing auth...`);
        await refreshAuth(); 
        
        if (data.error === 'csrf_invalid') {
          // Alert user about token issues
          alert("Session validation error. Please try again.");
          return res;
        }
      } else if (!res.ok) {
        console.error(`Request failed: ${url}`, data);
      }
    } 
    return res; 
  }

  // Toast system (idempotent mount)
  function ensureToastContainer(){ let c=document.getElementById('toastContainer'); if(!c){ c=document.createElement('div'); c.id='toastContainer'; c.style.cssText='position:fixed;top:14px;right:14px;z-index:3000;display:flex;flex-direction:column;gap:8px;max-width:280px;'; document.body.appendChild(c);} return c; }
  function showToast(msg,type='info',timeout=3200){ const c=ensureToastContainer(); const el=document.createElement('div'); const colors={info:'#2563eb',success:'#059669',error:'#dc2626',warn:'#d97706'}; const bg=colors[type]||colors.info; el.style.cssText=`background:${bg};color:#fff;padding:8px 12px;border-radius:10px;font-size:0.7rem;font-weight:500;box-shadow:0 4px 18px rgba(0,0,0,0.3);opacity:0;transform:translateY(-6px);transition:.25s;`; el.textContent=msg; c.appendChild(el); requestAnimationFrame(()=>{ el.style.opacity='1'; el.style.transform='translateY(0)'; }); setTimeout(()=>{ el.style.opacity='0'; el.style.transform='translateY(-6px)'; setTimeout(()=> el.remove(),260); }, timeout); }

  // Confirm modal (lazy create)
  function ensureConfirm(){ let modal=document.getElementById('confirmModal'); if(!modal){ modal=document.createElement('div'); modal.id='confirmModal'; modal.style.cssText='position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,0.45);z-index:3200;'; modal.innerHTML=`<div style="background:var(--chat-bg,#1e293b);border:1px solid var(--border-color,#334155);padding:18px 20px;border-radius:14px;max-width:420px;width:100%;font-size:0.85rem;"> <div id="confirmMessage" style="margin-bottom:16px;line-height:1.4;"></div> <div style="display:flex;gap:10px;justify-content:flex-end;"> <button id="confirmCancelBtn" class="lps2-btn" style="background:var(--inline-code-bg,#334155);">Cancel</button> <button id="confirmOkBtn" class="lps2-btn" style="background:#dc2626;color:#fff;">Delete</button> </div></div>`; document.body.appendChild(modal);} return modal; }
  function confirmAction(message,{confirmLabel='Delete',destructive=true}={}){ return new Promise(resolve=>{ const modal=ensureConfirm(); const msg=modal.querySelector('#confirmMessage'); const ok=modal.querySelector('#confirmOkBtn'); const cancel=modal.querySelector('#confirmCancelBtn'); msg.textContent=message; ok.textContent=confirmLabel; ok.style.background=destructive?'#dc2626':'var(--btn-gradient-start,#2563eb)'; modal.style.display='flex'; let done=false; function cleanup(v){ if(done) return; done=true; modal.style.display='none'; ok.removeEventListener('click',onOk); cancel.removeEventListener('click',onCancel); document.removeEventListener('keydown',onKey); resolve(v);} function onOk(){cleanup(true);} function onCancel(){cleanup(false);} function onKey(e){ if(e.key==='Escape')cleanup(false); if(e.key==='Enter')cleanup(true);} ok.addEventListener('click',onOk); cancel.addEventListener('click',onCancel); document.addEventListener('keydown',onKey); }); }

  // Theme management
  function getTheme() { 
    try { return localStorage.getItem('lps2Theme') || 'light'; } catch(_){ return 'light'; } 
  }
  
  function setTheme(mode) { 
    try { localStorage.setItem('lps2Theme', mode); } catch(_){} 
    return mode;
  }
  
  function applyTheme(mode, elements = {}) {
    const themeToggle = elements.themeToggle || document.getElementById('themeToggle');
    if (!themeToggle) return;
    
    if (mode === 'dark') {
      document.body.classList.add('dark-mode');
      themeToggle.textContent = '☀️ Light';
    } else {
      document.body.classList.remove('dark-mode');
      themeToggle.textContent = '🌙 Dark';
    }
  }

  function initTheme(elements = {}) {
    const themeToggle = elements.themeToggle || document.getElementById('themeToggle');
    if (!themeToggle) return;
    
    // Apply stored theme on load
    const storedTheme = getTheme();
    applyTheme(storedTheme, elements);
    
    // Set up toggle listener
    themeToggle.addEventListener('click', () => {
      const current = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      setTheme(next);
      applyTheme(next, elements);
    });
  }

  // Export
  function persistNav(section){ try { localStorage.setItem('lps2_last_nav', section); } catch(_){} }
  function getLastNav(){ try { return localStorage.getItem('lps2_last_nav'); } catch(_){ return null; } }
  function buildNav({current='chat', isAdmin=false}={}){
    // Returns HTML string for future server-side templating adoption
    const links=[
      {href:'/', key:'chat', label:'💬 Chat'},
      ...(isAdmin? [{href:'/admin', key:'admin', label:'⚙️ Admin'}]:[])
    ];
    const parts=links.map(l=>`<a href="${l.href}" class="nav-link${l.key===current?' active':''}" data-nav="${l.key}" ${l.key===current?'aria-current="page"':''}>${l.label}</a>`);
    parts.push('<button id="logoutBtn" class="nav-link logout-btn" type="button">Logout</button>');
    return `<nav class="top-nav" aria-label="Primary"><div class="nav-left">${parts.join('')}</div></nav>`;
  }
  global.LPS2Common={ 
    state, 
    refreshAuth, 
    authHeaders, 
    fetchWithCsrf, 
    showToast, 
    confirmAction, 
    persistNav, 
    getLastNav, 
    buildNav,
    theme: {
      get: getTheme,
      set: setTheme,
      apply: applyTheme,
      init: initTheme
    }
  };
})(window);
