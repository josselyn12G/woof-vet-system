// Historia clínica: filtra la línea de tiempo por tipo (Todas / Consultas / Vacunas / Recetas) y por texto.
// Sin JS se ve todo; esto solo esconde filas. Cada mes recalcula su cuenta y se oculta si queda vacío.
(function () {
  const historial = document.querySelector('[data-historial]');
  if (!historial) return;

  const botones = historial.querySelectorAll('[data-filtro]');
  const busqueda = historial.querySelector('[data-busqueda]');
  const abrirBusqueda = historial.querySelector('[data-abrir-busqueda]');
  const sinResultados = historial.querySelector('[data-sin-resultados]');
  let tipo = 'todos';

  const normalizar = (texto) => texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  function aplicar() {
    const buscado = normalizar(busqueda ? busqueda.value.trim() : '');
    let visibles = 0;
    historial.querySelectorAll('[data-mes]').forEach((mes) => {
      let enElMes = 0;
      mes.querySelectorAll('[data-tipo]').forEach((registro) => {
        const pasa = (tipo === 'todos' || registro.dataset.tipo === tipo)
          && (!buscado || normalizar(registro.textContent).includes(buscado));
        registro.hidden = !pasa;
        if (pasa) enElMes += 1;
      });
      mes.hidden = enElMes === 0;
      const cuenta = mes.querySelector('[data-cuenta]');
      if (cuenta) cuenta.textContent = `${enElMes} registro${enElMes === 1 ? '' : 's'}`;
      visibles += enElMes;
    });
    if (sinResultados) sinResultados.hidden = visibles > 0;
  }

  botones.forEach((boton) => {
    boton.addEventListener('click', () => {
      tipo = boton.dataset.filtro;
      botones.forEach((otro) => {
        const activo = otro === boton;
        otro.classList.toggle('es-activo', activo);
        otro.setAttribute('aria-pressed', String(activo));
      });
      aplicar();
    });
  });

  if (abrirBusqueda && busqueda) {
    abrirBusqueda.addEventListener('click', () => {
      busqueda.hidden = !busqueda.hidden;
      abrirBusqueda.setAttribute('aria-expanded', String(!busqueda.hidden));
      if (busqueda.hidden) { busqueda.value = ''; aplicar(); } else { busqueda.focus(); }
    });
    busqueda.addEventListener('input', aplicar);
    busqueda.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape') abrirBusqueda.click();
    });
  }
})();
