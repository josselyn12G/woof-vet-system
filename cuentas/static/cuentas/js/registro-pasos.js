// Registro por pasos: muestra un grupo de campos a la vez, sin cambiar el formulario de Django.
// Todos los campos siguen dentro del mismo <form>; al final se envían juntos y Django valida todo.
// Sin JavaScript, la clase "con-js" no existe y se ven todos los pasos a la vez (sigue funcionando).
const form = document.getElementById('form-registro');

if (form) {
  const pasos = [...form.querySelectorAll('[data-paso]')];
  const indicadores = [...document.querySelectorAll('[data-indicador]')];
  const botonAtras = form.querySelector('[data-accion="atras"]');
  const botonSiguiente = form.querySelector('[data-accion="siguiente"]');
  const botonEnviar = form.querySelector('[data-accion="enviar"]');
  const telefonoValido = /^\+\d{8,15}$/;   // mismo formato que validar_telefono en models.py
  let actual = 0;

  function mostrar(indice) {
    actual = indice;
    pasos.forEach((paso, i) => { paso.hidden = i !== actual; });
    indicadores.forEach((indicador, i) => {
      indicador.classList.toggle('es-actual', i === actual);
      indicador.classList.toggle('es-completo', i < actual);
      if (i === actual) indicador.setAttribute('aria-current', 'step');
      else indicador.removeAttribute('aria-current');
    });
    botonAtras.hidden = actual === 0;
    botonSiguiente.hidden = actual === pasos.length - 1;
    botonEnviar.hidden = actual !== pasos.length - 1;
    pasos[actual].querySelector('input')?.focus();
  }

  // Revisión rápida en el navegador antes de avanzar (Django vuelve a validar todo al enviar)
  function mensajeDeError(input) {
    if (!input.value.trim()) return 'Completa este campo.';
    if (input.type === 'email' && !input.checkValidity()) return 'Escribe un correo válido, por ejemplo ana@correo.com.';
    if (input.name === 'telefono' && !telefonoValido.test(input.value.trim())) {
      return 'Ingresa el número en formato internacional, por ejemplo +593987654321.';
    }
    return '';
  }

  function pasoValido(paso) {
    let valido = true;
    paso.querySelectorAll('.campo').forEach((campo) => {
      const input = campo.querySelector('input');
      campo.querySelector('.campo__error--js')?.remove();
      const mensaje = mensajeDeError(input);
      campo.classList.toggle('campo--con-error', Boolean(mensaje));
      if (mensaje) {
        valido = false;
        const p = document.createElement('p');
        p.className = 'campo__error campo__error--js';
        p.innerHTML = '<i class="bi bi-exclamation-circle" aria-hidden="true"></i>';
        p.append(mensaje);
        campo.append(p);
      }
    });
    return valido;
  }

  botonSiguiente.addEventListener('click', () => {
    if (pasoValido(pasos[actual])) mostrar(actual + 1);
  });
  botonAtras.addEventListener('click', () => mostrar(actual - 1));

  // Enter en los pasos 1 y 2 avanza en lugar de enviar el formulario incompleto
  form.addEventListener('keydown', (evento) => {
    if (evento.key === 'Enter' && actual < pasos.length - 1 && evento.target.tagName === 'INPUT') {
      evento.preventDefault();
      botonSiguiente.click();
    }
  });

  // Si Django devolvió errores, se abre el primer paso que tenga uno
  const pasoConError = pasos.findIndex((paso) => paso.querySelector('.campo--con-error'));
  mostrar(pasoConError >= 0 ? pasoConError : 0);
}
