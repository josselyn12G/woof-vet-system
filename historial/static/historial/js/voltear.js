// Tarjetas de Mis recetas que se voltean: tocar el frente muestra las indicaciones; el botón de atrás vuelve.
// Con el mouse la tarjeta se inclina hacia el cursor. La cara que no se ve queda "inert" (ni foco ni lector).
(function () {
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const INCLINACION = 7;   // grados como máximo

  document.querySelectorAll('[data-flip]').forEach((tarjeta) => {
    const frente = tarjeta.querySelector('.rx-flip__cara--frente');
    const atras = tarjeta.querySelector('.rx-flip__cara--atras');
    const inclinacion = tarjeta.querySelector('.rx-flip__inclinacion');

    function mostrar(volteada, conFoco) {
      tarjeta.classList.toggle('es-volteada', volteada);
      frente.setAttribute('aria-expanded', String(volteada));
      frente.inert = volteada;
      atras.inert = !volteada;
      if (conFoco) (volteada ? atras.querySelector('a, button') : frente).focus({ preventScroll: true });
    }
    mostrar(false, false);

    tarjeta.querySelectorAll('[data-girar]').forEach((boton) => {
      // detail 0 = teclado: el foco pasa a la otra cara
      boton.addEventListener('click', (evento) => mostrar(!tarjeta.classList.contains('es-volteada'), evento.detail === 0));
    });

    if (sinMovimiento) return;
    tarjeta.addEventListener('pointermove', (evento) => {
      if (evento.pointerType === 'touch') return;
      const caja = tarjeta.getBoundingClientRect();
      const x = (evento.clientX - caja.left) / caja.width - 0.5;
      const y = (evento.clientY - caja.top) / caja.height - 0.5;
      inclinacion.style.setProperty('--rx-tx', `${(-y * 2 * INCLINACION).toFixed(2)}deg`);
      inclinacion.style.setProperty('--rx-ty', `${(x * 2 * INCLINACION).toFixed(2)}deg`);
      inclinacion.style.setProperty('--rx-escala', '1.02');
    });
    tarjeta.addEventListener('pointerleave', () => {
      ['--rx-tx', '--rx-ty', '--rx-escala'].forEach((v) => inclinacion.style.removeProperty(v));
    });
  });
})();
