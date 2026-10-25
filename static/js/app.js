/* Comportamiento mínimo del lado del cliente (documento 15.3: "validaciones del lado del cliente").
   La página funciona sin JavaScript: toda la lógica y las reglas están en Django. */
(() => {
  'use strict';

  // Toast del prototipo: se oculta solo después de unos segundos.
  const toast = document.getElementById('toast');
  if (toast && toast.classList.contains('show')) {
    setTimeout(() => { toast.className = 'toast'; }, 3600);
  }

  // Los <select data-autosubmit> aplican el filtro al cambiar (sin botón).
  document.querySelectorAll('select[data-autosubmit]').forEach((s) => {
    s.addEventListener('change', () => s.form && s.form.submit());
  });

  // Evita el doble envío (por ejemplo, doble clic en "Confirmar voto").
  document.addEventListener('submit', (e) => {
    const f = e.target;
    if ((f.method || '').toLowerCase() !== 'post') return;
    if (f.dataset.enviado) { e.preventDefault(); return; }
    f.dataset.enviado = '1';
    const b = f.querySelector('button[type="submit"][data-texto-enviando]');
    if (b) { b.disabled = true; b.textContent = b.dataset.textoEnviando; }
  });

  // Si el navegador restaura la página desde su caché (botón Atrás), se reactivan los formularios.
  window.addEventListener('pageshow', (e) => {
    if (!e.persisted) return;
    document.querySelectorAll('form[data-enviado]').forEach((f) => { delete f.dataset.enviado; });
    document.querySelectorAll('button[data-texto-enviando]').forEach((b) => { b.disabled = false; });
  });

  // Foco: campo en edición, o la contraseña si el correo ya viene escrito, o el título.
  const auto = document.querySelector('[data-autofocus]');
  const correo = document.querySelector('[data-enfocar-siguiente]');
  if (auto) { auto.focus(); auto.select && auto.select(); }
  else if (correo) { const c = document.getElementById('l-clave'); if (c) c.focus(); }
  else { const h = document.querySelector('.screen h2[tabindex]'); if (h) h.focus({ preventScroll: true }); }
})();
