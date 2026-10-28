// Comportamiento común del panel:
// 1. Botón del sidebar: en la computadora lo abre y lo cierra (y lo recuerda); en el celular lo muestra encima.
// 2. ⌘K / Ctrl+K enfoca el buscador de la barra superior.
// 3. Las cifras con data-contar cuentan desde 0 hasta su valor real, una vez, al entrar.
(function () {
  const raiz = document.documentElement;
  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esCelular = () => window.matchMedia('(max-width: 991.98px)').matches;

  // ---------- 1. Sidebar ----------
  const panel = document.querySelector('[data-panel]');
  const abrir = panel && panel.querySelector('[data-panel-abrir]');
  const velo = panel && panel.querySelector('[data-panel-cerrar]');

  if (abrir && velo) {
    const guardar = (valor) => { try { localStorage.setItem('woof-menu', valor); } catch (e) { /* sin almacenamiento */ } };

    function mostrarEnCelular(abierto) {
      panel.classList.toggle('menu-abierto', abierto);
      abrir.setAttribute('aria-expanded', String(abierto));
      velo.hidden = !abierto;
    }

    abrir.setAttribute('aria-expanded', String(esCelular() ? false : !raiz.classList.contains('menu-compacto')));

    abrir.addEventListener('click', () => {
      if (esCelular()) {
        mostrarEnCelular(!panel.classList.contains('menu-abierto'));
        return;
      }
      const compacto = raiz.classList.toggle('menu-compacto');
      abrir.setAttribute('aria-expanded', String(!compacto));
      guardar(compacto ? 'compacto' : 'abierto');
    });
    velo.addEventListener('click', () => mostrarEnCelular(false));
    document.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape' && panel.classList.contains('menu-abierto')) {
        mostrarEnCelular(false);
        abrir.focus();
      }
    });
    // La transición del ancho se activa después de la primera pintura (si no, "se abre" al cargar)
    requestAnimationFrame(() => raiz.classList.add('menu-listo'));
  }

  // ---------- 2. ⌘K ----------
  const buscador = document.querySelector('[data-buscar-atajo]');
  if (buscador) {
    document.addEventListener('keydown', (evento) => {
      if ((evento.metaKey || evento.ctrlKey) && evento.key.toLowerCase() === 'k') {
        evento.preventDefault();
        buscador.focus();
      }
    });
  }

  // ---------- 3. Cifras que cuentan ----------
  const formato = (valor, decimales) =>
    valor.toLocaleString('es-EC', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });

  document.querySelectorAll('[data-contar]').forEach((elemento) => {
    const final = Number(elemento.dataset.contar) || 0;
    const decimales = Number(elemento.dataset.decimales) || 0;
    elemento.textContent = formato(final, decimales);
    if (reducir || final === 0) return;   // un 0 no tiene nada que contar

    const duracion = 900;
    const inicio = performance.now();
    const salida = (t) => 1 - Math.pow(1 - t, 3);   // rápido al principio, se frena al llegar
    elemento.textContent = formato(0, decimales);
    function paso(ahora) {
      const t = Math.min((ahora - inicio) / duracion, 1);
      elemento.textContent = formato(final * salida(t), decimales);
      if (t < 1) requestAnimationFrame(paso);
    }
    requestAnimationFrame(paso);
  });
})();
