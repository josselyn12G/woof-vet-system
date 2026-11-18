// Cargando (estilo LatticeLoader): un <dialog> modal sobre toda la pantalla; mientras está abierto el navegador
// bloquea clics, teclado y foco en el resto (también sobre otro pop-up abierto). Escape no lo cierra.
// Se muestra solo al enviar cualquier formulario POST de la página
// (el texto sale de data-cargando="…" en el <form>, o "Guardando"). Para algo asíncrono propio:
//   WoofCargando.mostrar('Buscando turnos');  …  WoofCargando.terminar('listo' | 'error', 'Listo en');
// Un formulario con data-sin-cargando no lo muestra. Un enlace con data-cargando="…" también lo muestra.
(function () {
  // Órbita de 3 x 3: el orden en que se enciende cada punto (null = el centro, apagado)
  const ORBITA = [0, 1, 2, 7, null, 3, 6, 5, 4];
  const PASO = 108;   // ms entre un punto y el siguiente
  const MARCAS = { listo: [2, 3, 5, 7], error: [0, 2, 4, 6, 8] };

  let velo, caja, texto, tiempo, marca, reloj, inicio, cierre;

  function crear() {
    if (caja) return;
    velo = document.createElement('dialog');
    velo.className = 'cargando-velo';
    velo.setAttribute('aria-label', 'Guardando');
    velo.addEventListener('cancel', (evento) => evento.preventDefault());   // Escape no lo cierra
    caja = document.createElement('div');
    caja.className = 'cargando';
    caja.setAttribute('role', 'status');
    caja.setAttribute('aria-live', 'polite');
    caja.dataset.estado = 'trabajando';
    const celdas = (clase) => ORBITA.map((orden) => `<span class="cargando__celda${orden === null ? ' cargando__celda--hueco' : ''}"${orden === null || clase !== 'giro' ? '' : ` style="animation-delay:${orden * PASO}ms"`}></span>`).join('');
    caja.innerHTML = `
      <span class="cargando__rejilla" aria-hidden="true">
        <span class="cargando__capa cargando__giro">${celdas('giro')}</span>
        <span class="cargando__capa cargando__marca">${celdas('marca')}</span>
      </span>
      <span class="cargando__texto"></span>
      <span class="cargando__tiempo" aria-hidden="true">0.0s</span>`;
    texto = caja.querySelector('.cargando__texto');
    tiempo = caja.querySelector('.cargando__tiempo');
    marca = caja.querySelectorAll('.cargando__marca .cargando__celda');
    velo.appendChild(caja);
    document.body.appendChild(velo);
  }

  function pintar() {
    tiempo.textContent = `${((performance.now() - inicio) / 1000).toFixed(1)}s`;
  }

  function mostrar(verbo) {
    crear();
    clearTimeout(cierre);
    clearInterval(reloj);
    caja.dataset.estado = 'trabajando';
    texto.textContent = `${verbo || 'Guardando'}…`;
    inicio = performance.now();
    pintar();
    reloj = setInterval(pintar, 100);
    if (!velo.open) velo.showModal();
    requestAnimationFrame(() => velo.classList.add('es-visible'));
  }

  function ocultar() {
    if (!caja) return;
    clearInterval(reloj);
    velo.classList.remove('es-visible');
    if (velo.open) velo.close();
  }

  function terminar(estado = 'listo', verbo) {
    if (!caja) return;
    clearInterval(reloj);
    caja.dataset.estado = estado;
    marca.forEach((celda, i) => celda.classList.toggle('es-encendida', MARCAS[estado].includes(i)));
    texto.textContent = verbo || (estado === 'error' ? 'No se pudo guardar' : 'Listo en');
    if (estado !== 'listo' || verbo) tiempo.hidden = estado === 'error';
    cierre = setTimeout(ocultar, 1400);
  }

  // Para pedidos con fetch: aparece solo si tardan más de 150 ms (sin parpadeos en lo rápido) y, una vez a la
  // vista, se queda al menos 400 ms. Devuelve la misma promesa: await WoofCargando.durante('Buscando', fetch(...)).
  let pendientes = 0;
  let temporizador = null;
  let visibleDesde = 0;
  function durante(verbo, promesa) {
    pendientes += 1;
    if (pendientes === 1) {
      temporizador = setTimeout(() => { mostrar(verbo); visibleDesde = performance.now(); }, 150);
    } else if (visibleDesde) {
      texto.textContent = `${verbo || 'Cargando'}…`;
    }
    const fin = () => {
      pendientes -= 1;
      if (pendientes > 0) return;
      clearTimeout(temporizador);
      if (!visibleDesde) return;
      const falta = 400 - (performance.now() - visibleDesde);
      visibleDesde = 0;
      setTimeout(() => { if (!pendientes) ocultar(); }, Math.max(0, falta));
    };
    promesa.then(fin, fin);
    return promesa;
  }

  window.WoofCargando = { mostrar, ocultar, terminar, durante };

  // Cualquier formulario POST que de verdad se envía (si otro script lo detuvo, no se muestra)
  document.addEventListener('submit', (evento) => {
    const formulario = evento.target;
    if (evento.defaultPrevented || !(formulario instanceof HTMLFormElement)) return;
    if ((formulario.getAttribute('method') || '').toLowerCase() !== 'post' || 'sinCargando' in formulario.dataset) return;
    mostrar(formulario.dataset.cargando);
  });

  // Enlaces que cargan otra página lenta (por ejemplo, cambiar de mascota): <a data-cargando="Cargando a Lila">.
  // Solo con clic normal; con Ctrl, ⌘, Shift o el botón del medio se abre otra pestaña y no hace falta.
  document.addEventListener('click', (evento) => {
    const enlace = evento.target.closest('a[data-cargando]');
    if (!enlace || evento.defaultPrevented || evento.button !== 0) return;
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey || enlace.target === '_blank') return;
    mostrar(enlace.dataset.cargando);
  });

  // Al volver con "atrás" la página puede venir de la caché con el cargando a la vista
  window.addEventListener('pageshow', ocultar);
})();
