// Botón del ojo: muestra u oculta la contraseña del campo indicado en data-ver-contrasena.
document.querySelectorAll('[data-ver-contrasena]').forEach((boton) => {
  const campo = document.getElementById(boton.dataset.verContrasena);
  const icono = boton.querySelector('.bi');
  if (!campo) return;

  boton.addEventListener('click', () => {
    const visible = campo.type === 'password';
    campo.type = visible ? 'text' : 'password';
    icono.className = visible ? 'bi bi-eye-slash' : 'bi bi-eye';
    boton.setAttribute('aria-pressed', String(visible));
    boton.setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña');
    campo.focus();
  });
});
