// Corredor 3D de fotos: botón Pausar/Reproducir y ahorro de batería fuera de pantalla.
// La animación vive en CSS (corredor.css); aquí solo se pausa o se reanuda, sin reiniciar posiciones.
const corredor = document.getElementById('corredor');
const control = document.getElementById('corredor-control');

if (corredor && control) {
  const icono = control.querySelector('.bi');
  const texto = control.querySelector('.corredor__control-texto');

  control.addEventListener('click', () => {
    const pausado = corredor.classList.toggle('corredor--pausado');
    control.setAttribute('aria-pressed', String(pausado));
    icono.className = pausado ? 'bi bi-play-fill' : 'bi bi-pause-fill';
    texto.textContent = pausado ? 'Reproducir' : 'Pausar';
    control.setAttribute('aria-label', pausado ? 'Reproducir animación' : 'Pausar animación');
  });

  // Fuera de pantalla no tiene sentido animar 18 tarjetas: se pausa sola y sigue al volver.
  new IntersectionObserver(([entrada]) => {
    corredor.classList.toggle('corredor--fuera', !entrada.isIntersecting);
  }).observe(corredor);
}
