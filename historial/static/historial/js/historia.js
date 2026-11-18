// Historia clínica: filtra la línea de tiempo por tipo (Todas / Consultas / Vacunas / Recetas), por mes y por texto.
// Sin JS se ve todo; esto solo esconde filas. Cada mes recalcula su cuenta y se oculta si queda vacío.
(function () {
  const historial = document.querySelector('[data-historial]');
  if (!historial) return;

  const botones = historial.querySelectorAll('[data-filtro]');
  const busqueda = historial.querySelector('[data-busqueda]');
  const abrirBusqueda = historial.querySelector('[data-abrir-busqueda]');
  const sinResultados = historial.querySelector('[data-sin-resultados]');
  const filtroMes = historial.querySelector('[data-filtro-mes]');
  const selectMes = filtroMes ? filtroMes.querySelector('select') : null;
  let tipo = 'todos';
  if (filtroMes) filtroMes.hidden = false;

  const normalizar = (texto) => texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  function aplicar() {
    const buscado = normalizar(busqueda ? busqueda.value.trim() : '');
    let visibles = 0;
    const mesElegido = selectMes ? selectMes.value : '';
    historial.querySelectorAll('[data-mes]').forEach((mes) => {
      let enElMes = 0;
      if (mesElegido && mes.dataset.mesValor !== mesElegido) {
        mes.hidden = true;
        return;
      }
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

  if (selectMes) selectMes.addEventListener('change', aplicar);

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

// Historia como reporte: pestañas (Resumen · Vacunas · Peso · Historial) y el paso de una mascota a otra.
// La pestaña elegida viaja en ?vista= para que al cambiar de mascota se quede en la misma.
(function () {
  const reporte = document.querySelector('[data-reporte]');
  if (!reporte) return;
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const marco = reporte.querySelector('[data-reporte-marco]');

  // ---------- Pestañas ----------
  const lista = reporte.querySelector('[data-pestanas]');
  const pestanas = [...reporte.querySelectorAll('[data-vista]')];
  const paneles = [...reporte.querySelectorAll('[data-panel]')];
  const VISTAS = pestanas.map((p) => p.dataset.vista);
  let vista = new URLSearchParams(window.location.search).get('vista');
  if (!VISTAS.includes(vista)) vista = 'resumen';

  function elegir(nueva, conFoco) {
    vista = nueva;
    pestanas.forEach((p) => {
      const activa = p.dataset.vista === nueva;
      p.setAttribute('aria-selected', String(activa));
      p.tabIndex = activa ? 0 : -1;
      p.classList.toggle('es-activa', activa);
      if (activa && conFoco) p.focus();
    });
    paneles.forEach((panel) => { panel.hidden = panel.dataset.panel !== nueva; });
    const url = new URL(window.location.href);
    url.searchParams.set('vista', nueva);
    url.hash = '';
    history.replaceState(null, '', url);
  }

  if (lista) {
    lista.hidden = false;
    reporte.classList.add('con-pestanas');
    elegir(vista, false);
    pestanas.forEach((p, i) => {
      p.addEventListener('click', () => elegir(p.dataset.vista, false));
      p.addEventListener('keydown', (evento) => {
        const mover = { ArrowRight: 1, ArrowLeft: -1 }[evento.key];
        if (mover) {
          evento.preventDefault();
          evento.stopPropagation();
          elegir(pestanas[(i + mover + pestanas.length) % pestanas.length].dataset.vista, true);
        } else if (evento.key === 'Home' || evento.key === 'End') {
          evento.preventDefault();
          elegir(pestanas[evento.key === 'Home' ? 0 : pestanas.length - 1].dataset.vista, true);
        }
      });
    });
    reporte.querySelectorAll('[data-ir-vista]').forEach((enlace) => {
      enlace.addEventListener('click', (evento) => {
        evento.preventDefault();
        elegir(enlace.dataset.irVista, false);
      });
    });
  }

  // ---------- De un reporte a otro ----------
  const anterior = reporte.querySelector('[data-ir="anterior"]');
  const siguiente = reporte.querySelector('[data-ir="siguiente"]');

  function ir(enlace, direccion) {
    if (!enlace) return;
    const url = new URL(enlace.href);
    url.searchParams.set('vista', vista);
    // Mientras llega el reporte nuevo, el cargando tapa la pantalla (cargando.js)
    if (window.WoofCargando) window.WoofCargando.mostrar(enlace.dataset.nombre ? `Cargando a ${enlace.dataset.nombre}` : 'Cargando');
    if (sinMovimiento) { window.location.href = url; return; }
    try { sessionStorage.setItem('hc-entrada', direccion); } catch (e) { /* sin almacenamiento: sin animación de entrada */ }
    marco.classList.add(`es-saliendo-${direccion}`);
    window.setTimeout(() => { window.location.href = url; }, 200);
  }

  [anterior, siguiente].forEach((enlace) => {
    if (!enlace) return;
    enlace.addEventListener('click', (evento) => {
      evento.preventDefault();
      ir(enlace, enlace === siguiente ? 'siguiente' : 'anterior');
    });
  });
  reporte.querySelectorAll('.hc-foto__punto:not(.es-activo)').forEach((punto) => {
    punto.addEventListener('click', (evento) => { evento.preventDefault(); ir(punto, 'siguiente'); });
  });

  // Deslizar la foto con el dedo (o arrastrar con el mouse)
  const foto = reporte.querySelector('[data-deslizar]');
  if (foto && siguiente) {
    let desde = null;
    foto.addEventListener('pointerdown', (evento) => {
      if (evento.target.closest('a')) return;
      desde = { x: evento.clientX, y: evento.clientY };
    });
    foto.addEventListener('pointerup', (evento) => {
      if (!desde) return;
      const dx = evento.clientX - desde.x;
      const dy = evento.clientY - desde.y;
      desde = null;
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) ir(dx < 0 ? siguiente : anterior, dx < 0 ? 'siguiente' : 'anterior');
    });
    foto.addEventListener('pointercancel', () => { desde = null; });
  }

  // Flechas del teclado (fuera de campos de texto y de las pestañas, que usan las suyas)
  document.addEventListener('keydown', (evento) => {
    if (!siguiente || evento.defaultPrevented || evento.altKey || evento.metaKey || evento.ctrlKey) return;
    if (evento.target.closest('input, textarea, select, [role="tab"], dialog')) return;
    if (evento.key === 'ArrowRight') ir(siguiente, 'siguiente');
    if (evento.key === 'ArrowLeft') ir(anterior, 'anterior');
  });

  // Entrada: el reporte nuevo llega desde el lado hacia donde se fue
  let entrada = null;
  try { entrada = sessionStorage.getItem('hc-entrada'); sessionStorage.removeItem('hc-entrada'); } catch (e) { /* nada */ }
  if (entrada && !sinMovimiento) {
    marco.classList.add(`es-entrando-${entrada}`);
    marco.addEventListener('animationend', () => marco.classList.remove(`es-entrando-${entrada}`), { once: true });
  }
  // Al volver con "atrás" desde la caché, el marco no debe quedar a medio salir
  window.addEventListener('pageshow', () => marco.classList.remove('es-saliendo-siguiente', 'es-saliendo-anterior'));
})();
