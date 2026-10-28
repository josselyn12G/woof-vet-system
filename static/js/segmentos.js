// Selector de período: coloca la píldora detrás de la opción activa y, al elegir otra, la desliza hasta ella
// antes de cambiar de página. Sin JavaScript, las opciones siguen siendo enlaces normales (?periodo=).
(function () {
  const grupo = document.querySelector('[data-segmentos]');
  if (!grupo) return;

  const pildora = grupo.querySelector('.segmentos__pildora');
  const opciones = [...grupo.querySelectorAll('.segmentos__opcion')];
  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ubicar(opcion) {
    pildora.style.width = `${opcion.offsetWidth}px`;
    pildora.style.transform = `translateX(${opcion.offsetLeft}px)`;
  }

  const activa = grupo.querySelector('.es-activo') || opciones[0];
  ubicar(activa);
  // La primera ubicación es instantánea; recién después se activa la transición
  requestAnimationFrame(() => grupo.classList.add('esta-listo'));

  opciones.forEach((opcion) => {
    opcion.addEventListener('click', (evento) => {
      if (opcion === activa || reducir || evento.metaKey || evento.ctrlKey) return;
      evento.preventDefault();
      activa.classList.remove('es-activo');
      opcion.classList.add('es-activo');
      ubicar(opcion);
      // Navega cuando la píldora termina de deslizarse (200 ms)
      setTimeout(() => { window.location.href = opcion.href; }, 200);
    });
  });

  window.addEventListener('resize', () => ubicar(grupo.querySelector('.es-activo') || activa));
})();
