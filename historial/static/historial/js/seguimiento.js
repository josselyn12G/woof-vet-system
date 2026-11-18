// Tratamiento: cada medicamento abre su pop-up (<dialog>) con los días para tachar.
// Dentro del pop-up cada check solo cambia en pantalla (resorte, visto y raya) y la cuenta "N de M días";
// al cerrarlo se guarda todo en un solo POST (GuardarDiasView) y la página se actualiza.
// Si se sale de la página con cambios sin guardar, salen igual con sendBeacon.
// Sin JS: cada día es su propio formulario (MarcarDiaView) y funciona igual.
(function () {
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const dialogo = (id) => document.querySelector(`[data-dialogo-receta="${id}"]`);

  // ---------- Pop-ups ----------
  function cerrar(d) {
    if (!d || !d.open) return;
    if (sinMovimiento) { d.close(); return; }
    d.classList.add('es-cerrando');
    d.addEventListener('animationend', () => { d.classList.remove('es-cerrando'); d.close(); }, { once: true });
  }

  document.querySelectorAll('[data-abrir-receta]').forEach((boton) => {
    boton.addEventListener('click', () => {
      const d = dialogo(boton.dataset.abrirReceta);
      if (d && !d.open) d.showModal();
    });
  });

  // ---------- Guardar al cerrar ----------
  // Los días marcados del pop-up (y el CSRF de sus formularios) listos para enviar
  function datos(d) {
    const cuerpo = new FormData();
    const token = d.querySelector('input[name="csrfmiddlewaretoken"]');
    if (token) cuerpo.append('csrfmiddlewaretoken', token.value);
    d.querySelectorAll('form[data-spring-check]').forEach((formulario) => {
      if (formulario.querySelector('.spring-check.es-hecho')) cuerpo.append('dia', formulario.querySelector('input[name="dia"]').value);
    });
    return cuerpo;
  }

  async function guardar(d) {
    if (!d.dataset.cambios) return;
    delete d.dataset.cambios;
    const envio = fetch(d.dataset.guardarUrl, { method: 'POST', body: datos(d), headers: { 'X-Requested-With': 'fetch' } });
    try {
      const respuesta = await (window.WoofCargando ? window.WoofCargando.durante('Guardando las dosis', envio) : envio);
      const resultado = await respuesta.json();
      if (!respuesta.ok) throw new Error(resultado.error || 'No se pudo guardar');
      // La página vuelve a pedirse para que las barras, "Toca hoy" y el avance queden al día
      if (window.WoofCargando) window.WoofCargando.mostrar('Actualizando');
      window.location.reload();
    } catch (error) {
      if (window.WoofCargando) window.WoofCargando.terminar('error', error.message || 'No se pudo guardar');
      d.dataset.cambios = '1';   // se reintenta al volver a cerrar
    }
  }

  document.querySelectorAll('[data-dialogo-receta]').forEach((d) => {
    d.querySelectorAll('[data-cerrar-dialogo]').forEach((x) => x.addEventListener('click', () => cerrar(d)));
    d.addEventListener('cancel', (evento) => { evento.preventDefault(); cerrar(d); });   // Escape
    d.addEventListener('click', (evento) => { if (evento.target === d) cerrar(d); });    // fuera del cuadro
    d.addEventListener('close', () => {
      if (window.location.hash) history.replaceState(null, '', window.location.pathname + window.location.search);
      guardar(d);
    });
  });

  // Salir de la página con cambios: se mandan igual (sendBeacon no espera la respuesta)
  window.addEventListener('pagehide', () => {
    document.querySelectorAll('[data-dialogo-receta][data-cambios]').forEach((d) => {
      if (navigator.sendBeacon) navigator.sendBeacon(d.dataset.guardarUrl, datos(d));
    });
  });

  const desdeElPost = window.location.hash.match(/^#receta-(\d+)$/);
  if (desdeElPost) {
    const d = dialogo(desdeElPost[1]);
    if (d) d.showModal();
  }

  // ---------- Spring check: solo en pantalla hasta cerrar ----------
  function contar(d) {
    const cuenta = d.querySelector('[data-cuenta-dias]');
    if (!cuenta) return;
    const total = Number(d.dataset.totalDias) || 0;
    const hechos = d.querySelectorAll('.spring-check.es-hecho').length;
    cuenta.textContent = `${hechos} de ${total} días · ${total ? Math.round((hechos * 100) / total) : 0}%`;
  }

  document.querySelectorAll('form[data-spring-check]').forEach((formulario) => {
    const boton = formulario.querySelector('.spring-check');
    const d = formulario.closest('[data-dialogo-receta]');
    if (!boton || !d) return;
    const estado = boton.querySelector('[data-estado]');
    if (estado) estado.dataset.original = boton.classList.contains('es-hecho') ? 'Sin marcar' : estado.textContent;

    formulario.addEventListener('submit', (evento) => {
      evento.preventDefault();   // nada se envía todavía: se guarda al cerrar el pop-up
      const marcado = !boton.classList.contains('es-hecho');
      boton.classList.toggle('es-animando', !sinMovimiento);
      boton.classList.toggle('es-hecho', marcado);
      boton.setAttribute('aria-checked', String(marcado));
      if (estado) estado.textContent = marcado ? 'Dosis dada' : estado.dataset.original;
      d.dataset.cambios = '1';
      contar(d);
    });
  });
})();
