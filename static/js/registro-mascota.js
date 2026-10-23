// Registrar una mascota en un pop-up, sin salir de "Mis mascotas".
// Trae el formulario de mascotas:crear y lo envía con fetch: el servidor valida igual que siempre
// (si hay errores, devuelve el formulario con sus mensajes y se vuelve a mostrar aquí).
// Sin JavaScript, o si algo falla, los enlaces abren la página del formulario como antes.
(function () {
  const dialogo = document.querySelector('[data-registro]');
  if (!dialogo || typeof dialogo.showModal !== 'function') return;

  const cuerpo = dialogo.querySelector('[data-registro-cuerpo]');
  const listo = dialogo.querySelector('[data-registro-listo]');
  const nombreListo = dialogo.querySelector('[data-registro-nombre]');
  const scriptVistaPrevia = document.currentScript.dataset.vistaPrevia;
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)');
  let urlCrear = null;

  // ---------- Abrir y cerrar ----------
  function abrir(url) {
    urlCrear = url;
    listo.hidden = true;
    dialogo.classList.remove('es-listo');
    cuerpo.innerHTML = '<div class="registro__cargando" role="status"><span class="visually-hidden">Cargando el formulario</span></div>';
    dialogo.showModal();
    traerFormulario(url);
  }

  function cerrar() {
    if (!dialogo.open || dialogo.classList.contains('es-cerrando')) return;
    if (sinMovimiento.matches) {
      dialogo.close();
      return;
    }
    // La salida es más corta que la entrada: cerrar debe sentirse inmediato
    dialogo.classList.add('es-cerrando');
    dialogo.addEventListener('animationend', function alTerminar(evento) {
      if (evento.target !== dialogo) return;
      dialogo.removeEventListener('animationend', alTerminar);
      dialogo.classList.remove('es-cerrando');
      dialogo.close();
    });
  }

  document.querySelectorAll('[data-abrir-registro]').forEach(function (enlace) {
    enlace.addEventListener('click', function (evento) {
      evento.preventDefault();
      abrir(enlace.href);
    });
  });

  dialogo.addEventListener('cancel', function (evento) { // tecla Escape
    evento.preventDefault();
    cerrar();
  });
  dialogo.addEventListener('click', function (evento) {
    // Clic en el velo (fuera de la tarjeta) o en un botón de cerrar
    if (evento.target === dialogo || evento.target.closest('[data-cerrar-registro]')) cerrar();
  });

  // ---------- Formulario ----------
  function traerFormulario(url) {
    fetch(url, { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (respuesta) {
        if (!respuesta.ok) throw new Error(respuesta.status);
        return respuesta.text();
      })
      .then(mostrarFormulario)
      .catch(function () { window.location.href = url; });
  }

  function mostrarFormulario(html) {
    const pagina = new DOMParser().parseFromString(html, 'text/html');
    const formulario = pagina.querySelector('.formulario-mascota');
    if (!formulario) {
      window.location.href = urlCrear;
      return;
    }

    formulario.querySelector('.formulario-mascota__titulo').id = 'registro-titulo';
    // "Cancelar" deja de ser un enlace a otra página: ahora cierra el pop-up
    const cancelar = formulario.querySelector('.formulario-mascota__acciones a');
    if (cancelar) {
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = cancelar.className;
      boton.textContent = cancelar.textContent;
      boton.dataset.cerrarRegistro = '';
      cancelar.replaceWith(boton);
    }

    cuerpo.replaceChildren(formulario);
    cargarVistaPrevia();

    const form = formulario.querySelector('form');
    form.addEventListener('submit', enviar);

    // Con errores, el foco va al primer campo marcado; si no, al nombre
    const primero = form.querySelector('.is-invalid') || form.querySelector('input[name="nombre"]');
    if (primero) primero.focus();
  }

  // vista-previa-foto.js (de Adrián) busca el campo de la foto al cargarse: se vuelve a cargar con cada formulario nuevo
  function cargarVistaPrevia() {
    if (!scriptVistaPrevia) return;
    const script = document.createElement('script');
    script.src = scriptVistaPrevia;
    cuerpo.appendChild(script);
  }

  function enviar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const boton = form.querySelector('button[type="submit"]');
    boton.disabled = true;
    boton.classList.add('esta-guardando');
    const nombre = (form.querySelector('input[name="nombre"]') || {}).value || 'Tu mascota';

    fetch(urlCrear, {
      method: 'POST',
      body: new FormData(form), // incluye la foto y el token CSRF
      headers: { 'X-Requested-With': 'fetch' },
    })
      .then(function (respuesta) {
        // Guardado: Django redirige a la ficha. Con errores responde 200 con el formulario otra vez
        if (respuesta.redirected && respuesta.url.split('?')[0] !== urlCrear.split('?')[0]) {
          celebrar(nombre.trim());
          return null;
        }
        return respuesta.text().then(mostrarFormulario);
      })
      .catch(function () {
        boton.disabled = false;
        boton.classList.remove('esta-guardando');
        form.submit(); // sin fetch, el envío normal sigue funcionando
      });
  }

  // ---------- Al guardar: el visto se dibuja y se recarga la lista con la nueva tarjeta ----------
  function celebrar(nombre) {
    nombreListo.textContent = nombre + ' se registró';
    listo.hidden = false;
    dialogo.classList.add('es-listo');
    window.setTimeout(function () {
      window.location.reload();
    }, sinMovimiento.matches ? 600 : 1500);
  }
})();
