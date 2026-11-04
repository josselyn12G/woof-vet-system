// Formulario del bloque de Mi horario (veterinario):
// 1. Cada input de hora (data-selector-hora) se cambia por un botón que abre una grilla de horas y minutos.
//    El input sigue en el formulario (oculto): es el que se envía, así que sin JavaScript todo funciona igual.
// 2. Los días de la semana (data-dia) y los turnos frecuentes (data-desde / data-hasta) llenan los campos de un toque.
// 3. Debajo se ve cuánto dura el bloque, o el aviso si "Hasta" no es después de "Desde".
// 4. El "+" de cada día de la grilla elige ese día en el formulario sin recargar la página.
(function () {
  const HORAS = Array.from({ length: 17 }, (_, i) => i + 6);   // de 06 a 22
  const MINUTOS = [0, 15, 30, 45];
  const dos = (numero) => String(numero).padStart(2, '0');

  function leer(texto) {
    const partes = /^(\d{1,2}):(\d{2})/.exec(texto || '');
    return partes ? { hora: Number(partes[1]), minuto: Number(partes[2]) } : null;
  }

  function cambiar(input, valor) {
    input.value = valor;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  let abierto = null;   // el selector con la grilla abierta (solo uno a la vez)

  function cerrarAbierto(devolverFoco) {
    if (!abierto) return;
    abierto.panel.hidden = true;
    abierto.boton.setAttribute('aria-expanded', 'false');
    if (devolverFoco) abierto.boton.focus();
    abierto = null;
  }

  function crearSelector(input) {
    const envoltorio = document.createElement('div');
    envoltorio.className = 'selector-hora';
    input.parentNode.insertBefore(envoltorio, input);
    envoltorio.appendChild(input);

    // La etiqueta (for="id_hora_inicio") pasa a apuntar al botón; el input oculto se queda con otro id
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'selector-hora__boton control-panel';
    boton.id = input.id;
    input.id = `${input.id}-valor`;
    input.hidden = true;
    boton.setAttribute('aria-haspopup', 'dialog');
    boton.setAttribute('aria-expanded', 'false');
    boton.innerHTML = '<i class="bi bi-clock" aria-hidden="true"></i><span class="selector-hora__valor"></span><i class="bi bi-chevron-down selector-hora__flecha" aria-hidden="true"></i>';
    envoltorio.appendChild(boton);

    const panel = document.createElement('div');
    panel.className = 'selector-hora__panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Elegir la hora');
    panel.hidden = true;
    panel.innerHTML = `
      <p class="selector-hora__titulo">Hora</p>
      <div class="selector-hora__horas">${HORAS.map((h) => `<button type="button" data-hora="${h}">${dos(h)}</button>`).join('')}</div>
      <p class="selector-hora__titulo">Minutos</p>
      <div class="selector-hora__minutos">${MINUTOS.map((m) => `<button type="button" data-minuto="${m}">:${dos(m)}</button>`).join('')}</div>`;
    envoltorio.appendChild(panel);

    const texto = boton.querySelector('.selector-hora__valor');

    function pintar() {
      const valor = leer(input.value);
      texto.textContent = valor ? `${dos(valor.hora)}:${dos(valor.minuto)}` : '--:--';
      boton.classList.toggle('es-vacio', !valor);
      panel.querySelectorAll('[data-hora]').forEach((opcion) => {
        opcion.setAttribute('aria-pressed', String(Boolean(valor) && Number(opcion.dataset.hora) === valor.hora));
      });
      panel.querySelectorAll('[data-minuto]').forEach((opcion) => {
        opcion.setAttribute('aria-pressed', String(Boolean(valor) && Number(opcion.dataset.minuto) === valor.minuto));
      });
    }

    boton.addEventListener('click', () => {
      const yaEstaba = abierto && abierto.panel === panel;
      cerrarAbierto(false);
      if (yaEstaba) return;
      panel.hidden = false;
      boton.setAttribute('aria-expanded', 'true');
      abierto = { panel, boton };
      const elegido = panel.querySelector('[data-hora][aria-pressed="true"]') || panel.querySelector('[data-hora="8"]');
      elegido.focus();
    });

    panel.addEventListener('click', (evento) => {
      const opcion = evento.target.closest('button');
      if (!opcion) return;
      const valor = leer(input.value) || { hora: 8, minuto: 0 };
      if (opcion.dataset.hora) {
        // Al elegir la hora se conservan los minutos; la grilla sigue abierta para afinarlos
        cambiar(input, `${dos(opcion.dataset.hora)}:${dos(valor.minuto)}`);
        panel.querySelector('[data-minuto][aria-pressed="true"]')?.focus();
      } else if (opcion.dataset.minuto) {
        cambiar(input, `${dos(valor.hora)}:${dos(opcion.dataset.minuto)}`);
        cerrarAbierto(true);
      }
    });

    input.addEventListener('change', pintar);
    pintar();
  }

  document.addEventListener('click', (evento) => {
    if (abierto && !evento.target.closest('.selector-hora')) cerrarAbierto(false);
  });
  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape' && abierto) cerrarAbierto(true);
  });

  document.querySelectorAll('[data-selector-hora]').forEach(crearSelector);

  // ---------- Días, turnos frecuentes y duración (por formulario) ----------
  document.querySelectorAll('form').forEach((formulario) => {
    const desde = formulario.querySelector('[name="hora_inicio"]');
    const hasta = formulario.querySelector('[name="hora_fin"]');
    const fecha = formulario.querySelector('[data-fecha-bloque]');
    if (!desde || !hasta) return;

    const dias = formulario.querySelector('[data-dias-rapidos]');
    const turnos = formulario.querySelector('[data-turnos-rapidos]');
    const resumen = formulario.querySelector('[data-resumen-bloque]');
    if (dias) dias.hidden = false;
    if (turnos) turnos.hidden = false;

    function marcarDia() {
      if (!dias) return;
      dias.querySelectorAll('[data-dia]').forEach((boton) => {
        boton.setAttribute('aria-pressed', String(boton.dataset.dia === fecha.value));
      });
    }

    function actualizar() {
      const inicio = leer(desde.value);
      const fin = leer(hasta.value);
      if (turnos) {
        turnos.querySelectorAll('[data-desde]').forEach((boton) => {
          boton.setAttribute('aria-pressed', String(boton.dataset.desde === desde.value && boton.dataset.hasta === hasta.value));
        });
      }
      if (!resumen) return;
      if (!inicio || !fin) {
        resumen.hidden = true;
        return;
      }
      const minutos = (fin.hora * 60 + fin.minuto) - (inicio.hora * 60 + inicio.minuto);
      resumen.hidden = false;
      resumen.classList.toggle('es-error', minutos <= 0);
      if (minutos <= 0) {
        resumen.innerHTML = '<i class="bi bi-exclamation-circle" aria-hidden="true"></i>«Hasta» debe ser después de «Desde».';
        return;
      }
      const horas = Math.floor(minutos / 60);
      const resto = minutos % 60;
      const duracion = [horas ? `${horas} h` : '', resto ? `${resto} min` : ''].filter(Boolean).join(' ');
      resumen.innerHTML = `<i class="bi bi-hourglass-split" aria-hidden="true"></i>Bloque de <strong>${duracion}</strong>`;
    }

    if (dias && fecha) {
      dias.addEventListener('click', (evento) => {
        const boton = evento.target.closest('[data-dia]');
        if (!boton || boton.disabled) return;
        fecha.value = boton.dataset.dia;
        marcarDia();
      });
      fecha.addEventListener('change', marcarDia);
      marcarDia();
    }

    if (turnos) {
      turnos.addEventListener('click', (evento) => {
        const boton = evento.target.closest('[data-desde]');
        if (!boton) return;
        cambiar(desde, boton.dataset.desde);
        cambiar(hasta, boton.dataset.hasta);
      });
    }

    desde.addEventListener('change', actualizar);
    hasta.addEventListener('change', actualizar);
    actualizar();

    // El "+" de un día de la grilla: elige ese día aquí mismo, sin recargar
    if (fecha && formulario.hasAttribute('data-formulario-bloque')) {
      document.querySelectorAll('[data-agregar-dia]').forEach((enlace) => {
        enlace.addEventListener('click', (evento) => {
          evento.preventDefault();
          fecha.value = enlace.dataset.agregarDia;
          fecha.dispatchEvent(new Event('change', { bubbles: true }));
          const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          formulario.closest('section').scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'start' });
          formulario.querySelector('.selector-hora__boton, [name="hora_inicio"]').focus({ preventScroll: true });
        });
      });
    }
  });
})();
