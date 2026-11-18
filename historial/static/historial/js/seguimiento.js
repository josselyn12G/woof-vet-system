// Spring check: al marcar un día, anima la caja (relleno con resorte, visto y raya) y después envía el POST.
// Sin JS el formulario se envía igual; con "reducir movimiento" se envía de inmediato.
(function () {
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.querySelectorAll('form[data-spring-check]').forEach((formulario) => {
    const boton = formulario.querySelector('.spring-check');
    if (!boton) return;

    formulario.addEventListener('submit', (evento) => {
      if (sinMovimiento || formulario.dataset.enviando) return;
      evento.preventDefault();
      formulario.dataset.enviando = '1';
      const marcado = !boton.classList.contains('es-hecho');
      boton.classList.add('es-animando');
      boton.classList.toggle('es-hecho', marcado);
      boton.setAttribute('aria-checked', String(marcado));
      const estado = boton.querySelector('[data-estado]');
      if (estado) estado.textContent = marcado ? 'Dosis dada' : 'Sin marcar';
      // Deja ver el resorte y la raya antes de recargar
      window.setTimeout(() => formulario.submit(), 420);
    });
  });
})();
