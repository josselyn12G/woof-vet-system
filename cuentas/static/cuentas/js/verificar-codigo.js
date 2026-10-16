// Código de verificación en 6 cuadros (uno por dígito).
// El formulario envía un solo campo, "codigo": este script lo oculta, dibuja los cuadros
// y cada vez que cambian junta los dígitos en ese campo. Sin JavaScript, el campo normal sigue funcionando.
document.querySelectorAll('[data-otp]').forEach((contenedor) => {
  const real = contenedor.querySelector('.otp__real');
  const formulario = contenedor.closest('form');
  const largo = Number(real.maxLength) || 6;

  // El campo real pasa a ser oculto (sin "required", porque el navegador no puede enfocar un campo oculto)
  real.type = 'hidden';
  real.value = '';

  const grupo = document.createElement('div');
  grupo.className = 'otp__cajas';
  grupo.setAttribute('role', 'group');
  grupo.setAttribute('aria-label', 'Código de verificación');

  const cajas = Array.from({ length: largo }, (_, i) => {
    const caja = document.createElement('input');
    caja.className = 'otp__caja';
    caja.type = 'text';
    caja.inputMode = 'numeric';
    caja.autocomplete = i === 0 ? 'one-time-code' : 'off';   // el celular sugiere el código del correo en el primero
    caja.setAttribute('aria-label', `Dígito ${i + 1} de ${largo}`);
    grupo.appendChild(caja);
    return caja;
  });

  contenedor.appendChild(grupo);
  cajas[0].focus();

  const actualizar = () => {
    real.value = cajas.map((caja) => caja.value).join('');
    cajas.forEach((caja) => caja.classList.toggle('otp__caja--llena', caja.value !== ''));
    contenedor.classList.remove('otp--error');                 // al corregir, se quita el rojo
  };

  // Reparte varios dígitos desde una caja (al pegar o con el autocompletado del celular)
  const repartir = (desde, texto) => {
    const digitos = texto.replace(/\D/g, '').slice(0, largo - desde).split('');
    digitos.forEach((digito, j) => { cajas[desde + j].value = digito; });
    actualizar();
    const siguiente = cajas[desde + digitos.length];
    (siguiente || formulario.querySelector('[type="submit"]')).focus();
  };

  cajas.forEach((caja, i) => {
    caja.addEventListener('input', () => {
      if (caja.value.length > 1) {
        repartir(i, caja.value);
        return;
      }
      caja.value = caja.value.replace(/\D/g, '');            // solo números
      actualizar();
      if (caja.value) {
        (cajas[i + 1] || formulario.querySelector('[type="submit"]')).focus();
      }
    });

    caja.addEventListener('paste', (evento) => {
      evento.preventDefault();
      repartir(i, evento.clipboardData.getData('text'));
    });

    caja.addEventListener('keydown', (evento) => {
      if (evento.key === 'Backspace' && !caja.value && i > 0) {
        cajas[i - 1].value = '';                                 // borrar en una caja vacía borra la anterior
        cajas[i - 1].focus();
        actualizar();
        evento.preventDefault();
      } else if (evento.key === 'ArrowLeft' && i > 0) {
        cajas[i - 1].focus();
      } else if (evento.key === 'ArrowRight' && i < largo - 1) {
        cajas[i + 1].focus();
      }
    });

    caja.addEventListener('focus', () => caja.select());
  });

  // Si falta algún dígito, no se envía: se marca y se enfoca el primer cuadro vacío
  formulario.addEventListener('submit', (evento) => {
    const vacia = cajas.find((caja) => !caja.value);
    if (vacia) {
      evento.preventDefault();
      contenedor.classList.remove('otp--error');
      void contenedor.offsetWidth;                               // reinicia la animación de "sacudir"
      contenedor.classList.add('otp--error');
      vacia.focus();
    }
  });
});
