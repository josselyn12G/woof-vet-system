/*
 * Reprogramar una cita: el mismo calendario de agendar, pero sin elegir servicio ni veterinario
 * (se mantienen). Pide al servidor los días con horas libres del mes y las horas de un día;
 * al tocar una hora llena los campos ocultos fecha y hora. El servidor vuelve a validar todo.
 */
(function () {
  const formulario = document.querySelector('[data-reprogramar]');
  if (!formulario) return;

  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
    'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

  const cuadricula = formulario.querySelector('[data-dias]');
  const textoMes = formulario.querySelector('[data-mes-texto]');
  const botonAnterior = formulario.querySelector('[data-mes-anterior]');
  const botonSiguiente = formulario.querySelector('[data-mes-siguiente]');
  const campoFecha = formulario.querySelector('[data-fecha]');
  const campoHora = formulario.querySelector('[data-hora]');
  const textoDia = formulario.querySelector('[data-dia-texto]');
  const horas = formulario.querySelector('[data-horas]');
  const confirmar = formulario.querySelector('[data-confirmar]');

  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const iso = (dia) => `${dia.getFullYear()}-${String(dia.getMonth() + 1).padStart(2, '0')}-${String(dia.getDate()).padStart(2, '0')}`;

  // Se abre en el mes de la cita (o en el del día elegido si el formulario volvió con errores)
  let fecha = campoFecha.value;
  const [anioInicial, mesInicial] = (fecha || formulario.dataset.mesInicial).split('-').map(Number);
  let mes = new Date(anioInicial, mesInicial - 1, 1);
  if (mes < new Date(hoy.getFullYear(), hoy.getMonth(), 1)) mes = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  let disponibles = new Set();

  // Solo cuenta la última respuesta: si el cliente cambia rápido de mes o de día, las viejas se ignoran
  let ultimoPedido = 0;
  async function pedirJSON(url, parametros) {
    const numero = ++ultimoPedido;
    const respuesta = await fetch(`${url}?${new URLSearchParams(parametros)}`, { headers: { Accept: 'application/json' } });
    if (!respuesta.ok) throw new Error(respuesta.status);
    const datos = await respuesta.json();
    return numero === ultimoPedido ? datos : null;
  }

  async function cargarDias() {
    cuadricula.classList.add('esta-cargando');
    const datos = await pedirJSON(formulario.dataset.diasUrl, {
      mes: `${mes.getFullYear()}-${String(mes.getMonth() + 1).padStart(2, '0')}`,
    }).catch(() => ({ dias: [] }));
    cuadricula.classList.remove('esta-cargando');
    if (!datos) return;
    disponibles = new Set(datos.dias);
    dibujarMes();
    cargarHoras();
  }

  function dibujarMes() {
    textoMes.textContent = `${MESES[mes.getMonth()]} ${mes.getFullYear()}`;
    botonAnterior.disabled = mes <= new Date(hoy.getFullYear(), hoy.getMonth(), 1);
    cuadricula.innerHTML = '';
    const vacios = (mes.getDay() + 6) % 7;      // la semana empieza el lunes
    for (let i = 0; i < vacios; i += 1) cuadricula.appendChild(document.createElement('span'));

    const total = new Date(mes.getFullYear(), mes.getMonth() + 1, 0).getDate();
    for (let numero = 1; numero <= total; numero += 1) {
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
    campoHora.value = '';
    dibujarMes();
    cargarHoras();
  }

  function aviso(texto) {
    horas.innerHTML = '';
    const p = document.createElement('p');
    p.className = 'horas__aviso';
    p.textContent = texto;
    horas.appendChild(p);
    confirmar.hidden = true;
  }

  async function cargarHoras() {
    if (!fecha || fecha.slice(0, 7) !== iso(mes).slice(0, 7)) {
      textoDia.textContent = 'Elige un día';
      aviso(disponibles.size ? 'Los días resaltados tienen horas libres.' : 'No hay horas libres este mes. Prueba el mes siguiente.');
      return;
    }
    const dia = new Date(`${fecha}T00:00`);
    textoDia.textContent = `${DIAS[dia.getDay()]} ${dia.getDate()} de ${MESES[dia.getMonth()]}`;
    horas.classList.add('esta-cargando');
    const datos = await pedirJSON(formulario.dataset.horasUrl, { fecha }).catch(() => ({ horas: [] }));
    horas.classList.remove('esta-cargando');
    if (!datos) return;
    if (!datos.horas.length) {
      aviso('Ese día ya no tiene horas libres. Elige otro.');
      return;
    }

    horas.innerHTML = '';
    const lista = document.createElement('div');
    lista.className = 'turnos-vet__horas';
    datos.horas.forEach((hora) => {
      const etiqueta = document.createElement('label');
      etiqueta.className = 'horas__opcion';
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'turno';                      // no es un campo del formulario: llena el oculto "hora"
      radio.value = hora;
      radio.setAttribute('aria-label', `A las ${hora}`);
      radio.checked = hora === campoHora.value;
      radio.addEventListener('change', () => {
        campoHora.value = hora;
        confirmar.hidden = false;
      });
      const texto = document.createElement('span');
      texto.innerHTML = '<i class="bi bi-arrow-right" aria-hidden="true"></i>';
      texto.append(hora);
      etiqueta.append(radio, texto);
      lista.appendChild(etiqueta);
    });
    horas.appendChild(lista);
    confirmar.hidden = !campoHora.value;
  }

  botonAnterior.addEventListener('click', () => {
    mes = new Date(mes.getFullYear(), mes.getMonth() - 1, 1);
    cargarDias();
  });
  botonSiguiente.addEventListener('click', () => {
    mes = new Date(mes.getFullYear(), mes.getMonth() + 1, 1);
    cargarDias();
  });

  cargarDias();
}());
