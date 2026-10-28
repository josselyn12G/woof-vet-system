// Agendar una cita, como un calendario de reservas:
// 1) al elegir el servicio se piden los días del mes con turnos libres (DiasDisponiblesView),
// 2) al tocar un día se piden sus horas libres agrupadas por veterinario (TurnosDelDiaView),
// 3) al elegir una hora se llenan los campos ocultos "veterinario" y "hora".
// El servidor vuelve a validar todo al guardar: esto solo ayuda a elegir.
(function () {
  // iniciar() prepara una reserva; se expone en window para que el pop-up de Mis citas la vuelva a iniciar
  // cuando el servidor devuelve el formulario con errores
  function iniciar(formulario) {
    const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

    const servicio = formulario.querySelector('[data-servicio]');
    const detalleServicio = formulario.querySelector('[data-servicio-detalle]');
    const campoFecha = formulario.querySelector('[data-fecha]');
    const campoVeterinario = formulario.querySelector('[data-veterinario]');
    const campoHora = formulario.querySelector('[data-hora]');
    const textoMes = formulario.querySelector('[data-mes-texto]');
    const cuadricula = formulario.querySelector('[data-dias]');
    const botonAnterior = formulario.querySelector('[data-mes-anterior]');
    const textoDia = formulario.querySelector('[data-dia-texto]');
    const horas = formulario.querySelector('[data-horas]');      // contenedor de las horas por doctor
    const confirmar = formulario.querySelector('[data-confirmar]');

    const hoy = new Date();
    hoy.setHours(0, 0, 0, 0);
    let fecha = campoFecha.value;                  // "2026-11-03" o ""
    let mes = fecha ? new Date(`${fecha}T00:00`) : new Date(hoy);
    mes.setDate(1);
    let disponibles = new Set();
    let pedido = 0;                                // si llegan dos respuestas, solo cuenta la última

    const servicioElegido = () => servicio.value;
    const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

    async function pedirJSON(url, parametros) {
      const numero = ++pedido;
      const respuesta = await fetch(`${url}?${new URLSearchParams(parametros)}`, { headers: { 'X-Requested-With': 'fetch' } });
      const datos = await respuesta.json();
      return numero === pedido ? datos : null;    // null: llegó una respuesta más nueva
    }

    // ---------- Servicio (desplegable): debajo se ve qué incluye, su duración y su precio ----------
    function mostrarDetalle() {
      const opcion = servicio.selectedOptions[0];
      detalleServicio.hidden = !servicio.value;
      if (!servicio.value) return;
      const descripcion = detalleServicio.querySelector('[data-servicio-descripcion]');
      descripcion.textContent = opcion.dataset.descripcion;
      descripcion.hidden = !opcion.dataset.descripcion;     // sin descripción, solo duración y precio
      detalleServicio.querySelector('[data-servicio-duracion]').textContent = `${opcion.dataset.duracion} min`;
      detalleServicio.querySelector('[data-servicio-precio]').textContent = `$${opcion.dataset.precio.replace('.', ',')}`;
    }

    // ---------- Calendario: días del mes con turnos libres para el servicio ----------
    async function cargarDias() {
      disponibles = new Set();
      if (servicioElegido()) {
        cuadricula.classList.add('esta-cargando');
        const datos = await pedirJSON(formulario.dataset.diasUrl, {
          servicio: servicioElegido(),
          mes: `${mes.getFullYear()}-${String(mes.getMonth() + 1).padStart(2, '0')}`,
        }).catch(() => ({ dias: [] }));
        cuadricula.classList.remove('esta-cargando');
        if (!datos) return;                        // llegó una respuesta más nueva: esta se ignora
        disponibles = new Set(datos.dias);
      }
      dibujarMes();
      // Si el día elegido ya no tiene horas (o cambió el servicio), se suelta
      if (fecha && !disponibles.has(fecha) && fecha.slice(0, 7) === iso(mes).slice(0, 7)) elegirDia('');
      else cargarTurnos();
    }

    function dibujarMes() {
      textoMes.textContent = `${MESES[mes.getMonth()]} ${mes.getFullYear()}`;
      botonAnterior.disabled = mes <= new Date(hoy.getFullYear(), hoy.getMonth(), 1);
      cuadricula.innerHTML = '';
      const vacios = (mes.getDay() + 6) % 7;      // la semana empieza el lunes
      for (let i = 0; i < vacios; i += 1) cuadricula.appendChild(document.createElement('span'));

      const dias = new Date(mes.getFullYear(), mes.getMonth() + 1, 0).getDate();
      for (let numero = 1; numero <= dias; numero += 1) {
        const dia = new Date(mes.getFullYear(), mes.getMonth(), numero);
        const clave = iso(dia);
        const libre = disponibles.has(clave);
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'calendario__dia';
        boton.textContent = numero;
        boton.disabled = !libre;
        boton.classList.toggle('es-libre', libre);
        boton.classList.toggle('es-elegido', clave === fecha);
        boton.classList.toggle('es-hoy', dia.getTime() === hoy.getTime());
        boton.setAttribute('aria-label', `${DIAS[dia.getDay()]} ${numero} de ${MESES[dia.getMonth()]}${libre ? ', con horas libres' : ''}`);
        if (clave === fecha) boton.setAttribute('aria-pressed', 'true');
        boton.addEventListener('click', () => elegirDia(clave));
        cuadricula.appendChild(boton);
      }
    }

    function elegirDia(clave) {
      fecha = clave;
      campoFecha.value = clave;
      dibujarMes();
      cargarTurnos();
    }

    // ---------- Turnos del día: horas agrupadas por veterinario ----------
    function aviso(texto) {
      horas.innerHTML = '';
      const p = document.createElement('p');
      p.className = 'horas__aviso';
      p.textContent = texto;
      horas.appendChild(p);
      confirmar.hidden = true;
    }

    async function cargarTurnos() {
      if (!servicioElegido()) {
        textoDia.textContent = 'Elige un día';
        aviso('Elige un servicio para ver los días con horas libres.');
        return;
      }
      if (!fecha) {
        textoDia.textContent = 'Elige un día';
        aviso(disponibles.size ? 'Los días resaltados tienen horas libres.' : 'No hay horas libres este mes. Prueba el mes siguiente.');
        return;
      }
      const dia = new Date(`${fecha}T00:00`);
      textoDia.textContent = `${DIAS[dia.getDay()]} ${dia.getDate()} de ${MESES[dia.getMonth()]}`;
      horas.classList.add('esta-cargando');
      const datos = await pedirJSON(formulario.dataset.turnosUrl, { servicio: servicioElegido(), fecha })
        .catch(() => ({ turnos: null }));
      horas.classList.remove('esta-cargando');
      if (!datos) return;
      if (datos.turnos === null) {
        aviso('No se pudieron cargar las horas. Revisa tu conexión e inténtalo de nuevo.');
        return;
      }
      mostrarTurnos(datos.turnos);
    }

    function mostrarTurnos(turnos) {
      if (!turnos.length) {
        aviso('Ya no quedan horas libres ese día.');
        return;
      }
      horas.innerHTML = '';
      let sigueElegido = false;
      turnos.forEach((grupo) => {
        const fila = filaDeDoctor(grupo);
        if (fila.querySelector('input:checked')) sigueElegido = true;
        horas.appendChild(fila);
      });
      confirmar.hidden = !sigueElegido;
      if (!sigueElegido) {
        campoVeterinario.value = '';
        campoHora.value = '';
      }
    }

    // Una fila por doctor: sus iniciales y nombre, y sus horas como botones con circulito
    function filaDeDoctor(grupo) {
      const bloque = document.createElement('div');
      bloque.className = 'turnos-vet';
      const nombre = document.createElement('p');
      nombre.className = 'turnos-vet__nombre';
      const inicial = document.createElement('span');
      inicial.className = 'inicial';
      inicial.setAttribute('aria-hidden', 'true');
      inicial.textContent = grupo.nombre.split(' ').slice(0, 2).map((parte) => parte[0]).join('').toUpperCase();
      nombre.append(inicial, grupo.nombre);

      const lista = document.createElement('div');
      lista.className = 'turnos-vet__horas';
      grupo.horas.forEach((hora) => {
        const etiqueta = document.createElement('label');
        etiqueta.className = 'horas__opcion';
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'turno';                      // no es un campo del formulario: llena los ocultos
        radio.value = `${grupo.veterinario}|${hora}`;
        radio.setAttribute('aria-label', `${hora} con ${grupo.nombre}`);
        radio.checked = String(grupo.veterinario) === campoVeterinario.value && hora === campoHora.value;
        radio.addEventListener('change', () => {
          campoVeterinario.value = grupo.veterinario;
          campoHora.value = hora;
          confirmar.hidden = false;
        });
        // La elegida se rellena y cambia el circulito por una flecha (citas.css)
        const texto = document.createElement('span');
        texto.innerHTML = '<i class="bi bi-arrow-right" aria-hidden="true"></i>';
        texto.append(hora);
        etiqueta.append(radio, texto);
        lista.appendChild(etiqueta);
      });
      bloque.append(nombre, lista);
      return bloque;
    }

    // ---------- Mascota: "Cita para Jasper" bajo las fotos ----------
    const citaPara = formulario.querySelector('[data-cita-para]');
    const mascotas = [...formulario.querySelectorAll('[data-mascota]')];
    function mostrarMascota() {
      const elegida = mascotas.find((radio) => radio.checked);
      citaPara.hidden = !elegida;
      if (elegida) citaPara.querySelector('strong').textContent = elegida.dataset.mascota;
    }
    mascotas.forEach((radio) => radio.addEventListener('change', mostrarMascota));

    // ---------- Eventos ----------
    servicio.addEventListener('change', () => { mostrarDetalle(); cargarDias(); });
    botonAnterior.addEventListener('click', () => { mes = new Date(mes.getFullYear(), mes.getMonth() - 1, 1); cargarDias(); });
    formulario.querySelector('[data-mes-siguiente]').addEventListener('click', () => { mes = new Date(mes.getFullYear(), mes.getMonth() + 1, 1); cargarDias(); });

    // Al abrir (o si el formulario volvió con errores) se aplica lo que ya estaba elegido
    mostrarMascota();
    mostrarDetalle();
    cargarDias();
  }

  window.iniciarAgendar = iniciar;
  document.querySelectorAll('[data-agendar]').forEach(iniciar);
})();
