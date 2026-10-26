// Mis citas: tres pop-ups.
// 1) Cancelar: antes de cancelar se confirma; "Sí, cancelar" envía el mismo formulario POST (con su CSRF).
// 2) Agendar: la reserva se abre aquí y se envía con fetch; con errores, el servidor devuelve la reserva otra vez.
// 3) Confirmación: al agendar se muestra el visto animado con los datos de la cita.
// Sin JavaScript todo funciona igual: los enlaces llevan a la página de agendar y los formularios se envían directo.
(function () {
  const dialogo = document.querySelector('[data-dialogo-cancelar]');
  const formularios = document.querySelectorAll('[data-cancelar-cita]');
  if (!dialogo || typeof dialogo.showModal !== 'function' || !formularios.length) return;

  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)');
  let pendiente = null;   // el formulario de la cita que se quiere cancelar

  formularios.forEach((formulario) => {
    formulario.addEventListener('submit', (evento) => {
      if (formulario.dataset.confirmado) return;   // ya se confirmó en el pop-up
      evento.preventDefault();
      pendiente = formulario;
      dialogo.querySelector('[data-cancelar-mascota]').textContent = formulario.dataset.mascota;
      dialogo.querySelector('[data-cancelar-detalle]').textContent = `${formulario.dataset.servicio} · ${formulario.dataset.cuando}`;
      dialogo.showModal();
      dialogo.querySelector('[data-mantener]').focus();   // el foco va a la opción que no borra nada
    });
  });

  function cerrar() {
    if (sinMovimiento.matches) {
      dialogo.close();
      return;
    }
    dialogo.classList.add('es-cerrando');
    window.setTimeout(() => {
      dialogo.classList.remove('es-cerrando');
      dialogo.close();
    }, 160);
  }

  dialogo.querySelector('[data-mantener]').addEventListener('click', cerrar);
  dialogo.addEventListener('cancel', (evento) => { evento.preventDefault(); cerrar(); });   // tecla Escape
  dialogo.addEventListener('click', (evento) => { if (evento.target === dialogo) cerrar(); });   // clic afuera

  dialogo.querySelector('[data-confirmar-cancelar]').addEventListener('click', (evento) => {
    evento.currentTarget.disabled = true;
    pendiente.dataset.confirmado = '1';
    pendiente.requestSubmit();
  });
})();

// ---------- Agendar en un pop-up y confirmación ----------
(function () {
  const agendar = document.querySelector('[data-dialogo-agendar]');
  const confirmacion = document.querySelector('[data-dialogo-confirmacion]');
  if (!agendar || !confirmacion || typeof agendar.showModal !== 'function') return;

  const cuerpo = agendar.querySelector('[data-agendar-cuerpo]');
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)');
  let recargar = false;   // al cerrar la confirmación se recarga la lista para ver la cita nueva

  function cerrar(dialogo, despues) {
    if (sinMovimiento.matches) {
      dialogo.close();
      if (despues) despues();
      return;
    }
    dialogo.classList.add('es-cerrando');
    window.setTimeout(() => {
      dialogo.classList.remove('es-cerrando');
      dialogo.close();
      if (despues) despues();
    }, 170);
  }

  // Abrir: el botón de la cabecera y el del bloque vacío (son enlaces: sin JavaScript, navegan)
  document.querySelectorAll('[data-abrir-agendar]').forEach((enlace) => {
    enlace.addEventListener('click', (evento) => {
      evento.preventDefault();
      abrirAgendar();
    });
  });
  // El foco empieza en el pop-up (no en la X): con el teclado, Tab lleva a la primera mascota
  function abrirAgendar() {
    agendar.showModal();
    agendar.focus();
  }
  agendar.querySelector('[data-cerrar-agendar]').addEventListener('click', () => cerrar(agendar));
  agendar.addEventListener('cancel', (evento) => { evento.preventDefault(); cerrar(agendar); });

  // Enviar con fetch: JSON = cita agendada; HTML = la reserva con sus errores
  cuerpo.addEventListener('submit', async (evento) => {
    const formulario = evento.target.closest('[data-agendar]');
    if (!formulario) return;
    evento.preventDefault();
    const boton = formulario.querySelector('button[type="submit"]');
    if (boton) boton.disabled = true;
    try {
      const respuesta = await fetch(formulario.action, {
        method: 'POST',
        body: new FormData(formulario),
        headers: { 'X-Requested-With': 'fetch' },
      });
      if ((respuesta.headers.get('Content-Type') || '').includes('application/json')) {
        const cita = await respuesta.json();
        cerrar(agendar, () => mostrarConfirmacion(cita));
        return;
      }
      cuerpo.innerHTML = await respuesta.text();
      const nuevo = cuerpo.querySelector('[data-agendar]');
      if (nuevo && window.iniciarAgendar) window.iniciarAgendar(nuevo);
      cuerpo.querySelector('[role="alert"], .formulario-panel__error')?.scrollIntoView({ block: 'center' });
    } catch (error) {
      formulario.submit();   // sin red para fetch: el envío normal sigue funcionando
    }
  });

  function mostrarConfirmacion(cita) {
    confirmacion.querySelector('[data-confirmacion-titulo]').textContent = cita.titulo;
    const texto = confirmacion.querySelector('[data-confirmacion-texto]');
    texto.textContent = `${cita.detalle}`;
    const cuando = document.createElement('strong');
    cuando.textContent = cita.cuando;
    texto.append(document.createElement('br'), cuando);
    recargar = true;
    // Se vuelve a crear el SVG para que el visto se dibuje de nuevo
    const visto = confirmacion.querySelector('.registro__visto');
    visto.replaceWith(visto.cloneNode(true));
    confirmacion.showModal();
  }

  function cerrarConfirmacion() {
    cerrar(confirmacion, () => {
      if (recargar) window.location.href = window.location.pathname + '?vista=proximas';
    });
  }
  confirmacion.querySelector('[data-cerrar-confirmacion]').addEventListener('click', cerrarConfirmacion);
  confirmacion.addEventListener('cancel', (evento) => { evento.preventDefault(); cerrarConfirmacion(); });

  // Al cargar: ?agendar (desde el inicio) abre la reserva; un mensaje de "cita agendada" abre la confirmación
  if ('abrirAlCargar' in confirmacion.dataset) confirmacion.showModal();
  else if ('abrirAlCargar' in agendar.dataset) abrirAgendar();
})();
