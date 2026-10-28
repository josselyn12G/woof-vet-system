// Panel del veterinario: la línea de "ahora" en la agenda de hoy se ubica en la hora actual y avanza cada minuto.
// (Las cifras que cuentan están en panel.js, para todo el panel.)
// Con "reducir movimiento" activado, la línea se ubica sin deslizarse.
(function () {
  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const linea = document.querySelector('[data-linea-tiempo]');
  if (!linea) return;

  const marca = linea.querySelector('[data-ahora]');
  const textoHora = linea.querySelector('[data-ahora-hora]');
  const desde = Number(linea.dataset.inicio);
  const hasta = Number(linea.dataset.fin);

  function ubicar() {
    const ahora = new Date();
    const horas = ahora.getHours() + ahora.getMinutes() / 60;
    // Fuera del horario de la agenda (antes de las 8 o después de las 18) no se muestra
    if (horas < desde || horas > hasta) {
      marca.hidden = true;
      return;
    }
    marca.hidden = false;
    marca.style.top = `${((horas - desde) / (hasta - desde)) * 100}%`;
    textoHora.textContent = ahora.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  ubicar();
  if (!reducir) requestAnimationFrame(() => linea.classList.add('esta-listo'));
  setInterval(ubicar, 60 * 1000);
})();
