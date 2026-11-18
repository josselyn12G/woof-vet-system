// Tratamiento: cada medicamento abre su pop-up (<dialog>) con los días para tachar.
// Spring check: al marcar un día, anima la caja (relleno con resorte, visto y raya) y después envía el POST.
// Al volver del POST (…#receta-<id>) se reabre el pop-up de ese medicamento.
// Sin JS: los formularios funcionan igual; con "reducir movimiento" no se anima nada.
(function () {
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- Pop-ups ----------
  const dialogo = (id) => document.querySelector(`[data-dialogo-receta="${id}"]`);

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

  document.querySelectorAll('[data-dialogo-receta]').forEach((d) => {
    d.querySelectorAll('[data-cerrar-dialogo]').forEach((x) => x.addEventListener('click', () => cerrar(d)));
    d.addEventListener('cancel', (evento) => { evento.preventDefault(); cerrar(d); });   // Escape
    d.addEventListener('click', (evento) => { if (evento.target === d) cerrar(d); });    // fuera del cuadro
    d.addEventListener('close', () => {
      if (window.location.hash) history.replaceState(null, '', window.location.pathname + window.location.search);
    });
  });

  const desdeElPost = window.location.hash.match(/^#receta-(\d+)$/);
  if (desdeElPost) {
    const d = dialogo(desdeElPost[1]);
    if (d) d.showModal();
  }

  // ---------- Spring check ----------
  document.querySelectorAll('form[data-spring-check]').forEach((formulario) => {
    const boton = formulario.querySelector('.spring-check');
    if (!boton) return;

    formulario.addEventListener('submit', (evento) => {
      if (sinMovimiento || formulario.dataset.enviando) return;   // sin animación: cargando.js lo muestra solo
      evento.preventDefault();
      formulario.dataset.enviando = '1';
      const marcado = !boton.classList.contains('es-hecho');
      boton.classList.add('es-animando');
      boton.classList.toggle('es-hecho', marcado);
      boton.setAttribute('aria-checked', String(marcado));
      const estado = boton.querySelector('[data-estado]');
      if (estado) estado.textContent = marcado ? 'Dosis dada' : 'Sin marcar';
      // Deja ver el resorte y la raya antes de recargar; mientras, el cargando dice "Guardando"
      if (window.WoofCargando) window.WoofCargando.mostrar(marcado ? 'Guardando la dosis' : 'Quitando la marca');
      window.setTimeout(() => formulario.submit(), 420);
    });
  });
})();
