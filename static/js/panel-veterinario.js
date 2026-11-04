// Panel del veterinario (Mi semana): la línea de "ahora" se ubica en la columna de hoy, a la hora actual,
// y avanza cada minuto. El detalle de cada cita no necesita JavaScript: es un pop-up nativo (atributo popover).
// (Las cifras que cuentan están en panel.js, para todo el panel.)
(function () {
  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const semana = document.querySelector('[data-semana-vet]');
  const marca = semana && semana.querySelector('[data-ahora]');
  if (marca) {
    const desde = Number(semana.dataset.inicio);
    const hasta = Number(semana.dataset.fin);

    function ubicar() {
      const ahora = new Date();
      const horas = ahora.getHours() + ahora.getMinutes() / 60;
      // Fuera de las horas que muestra la grilla no se dibuja
      marca.hidden = horas < desde || horas > hasta;
      if (!marca.hidden) marca.style.top = `${((horas - desde) / (hasta - desde)) * 100}%`;
    }

    ubicar();
    if (!reducir) requestAnimationFrame(() => semana.classList.add('esta-listo'));
    setInterval(ubicar, 60 * 1000);
  }
})();
