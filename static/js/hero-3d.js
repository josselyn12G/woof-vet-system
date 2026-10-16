// Animación 3D de la portada: huellas de perro flotando delante del círculo naranja.
// Si el navegador no tiene WebGL, la portada se ve igual, solo con el círculo (sin huellas).
import * as THREE from 'three';

const escena3d = document.getElementById('escena-3d');
const canvas = escena3d?.querySelector('canvas');
const reducirMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (canvas) {
  try {
    iniciar();
  } catch (error) {
    canvas.remove(); // sin WebGL: queda el círculo de CSS
  }
}

function crearHuella(material) {
  // Una huella = una almohadilla grande + cuatro dedos (esferas aplastadas).
  const huella = new THREE.Group();
  const esfera = new THREE.SphereGeometry(1, 32, 24);

  const almohadilla = new THREE.Mesh(esfera, material);
  almohadilla.scale.set(1, 0.82, 0.38);
  almohadilla.position.y = -0.35;
  huella.add(almohadilla);

  const dedos = [[-0.95, 0.55, 0.32], [-0.36, 1.05, 0.34], [0.36, 1.05, 0.34], [0.95, 0.55, 0.32]];
  for (const [x, y, tamano] of dedos) {
    const dedo = new THREE.Mesh(esfera, material);
    dedo.scale.set(tamano, tamano * 1.2, tamano * 0.6);
    dedo.position.set(x, y, 0);
    huella.add(dedo);
  }
  return huella;
}

function iniciar() {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // más de 2 no se nota y cuesta mucho

  const escena = new THREE.Scene();
  const camara = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  camara.position.set(0, 0, 16);

  // Luz: una suave general y una cálida desde arriba a la derecha para dar volumen.
  escena.add(new THREE.AmbientLight(0xffffff, 1.4));
  const luz = new THREE.DirectionalLight(0xfff1dc, 2.4);
  luz.position.set(5, 6, 8);
  escena.add(luz);

  // Colores de la marca Woof.
  const materiales = [
    new THREE.MeshStandardMaterial({ color: 0xfff7ec, roughness: 0.45 }), // crema
    new THREE.MeshStandardMaterial({ color: 0x573f33, roughness: 0.5 }),  // marrón del logo
    new THREE.MeshStandardMaterial({ color: 0xb45309, roughness: 0.5 }),  // naranja oscuro
  ];

  // Solo dos huellas, a la izquierda: la derecha ya tiene la huella dibujada y el círculo con el mensaje.
  const config = [
    { x: -4.6, y: 3.6, z: 0.5, escala: 0.55, material: 1 },
    { x: -5.0, y: -2.4, z: 0.6, escala: 0.45, material: 2 },
  ];


  const huellas = config.map((c, i) => {
    const huella = crearHuella(materiales[c.material]);
    huella.position.set(c.x, c.y, c.z);
    huella.scale.setScalar(c.escala);
    huella.rotation.set(0.3, -0.4 + i * 0.25, -0.5 + i * 0.4);
    huella.userData = { baseY: c.y, fase: i * 1.3, giro: 0.15 + (i % 3) * 0.08 };
    escena.add(huella);
    return huella;
  });

  // El tamaño del canvas sigue al de su contenedor (también al girar el celular).
  function ajustarTamano() {
    const { width, height } = escena3d.getBoundingClientRect();
    renderer.setSize(width, height, false);
    camara.aspect = width / height;
    camara.updateProjectionMatrix();
  }
  new ResizeObserver(ajustarTamano).observe(escena3d);
  ajustarTamano();

  // Paralaje: la cámara se mueve un poco siguiendo el mouse.
  const mouse = { x: 0, y: 0 };
  window.addEventListener('pointermove', (evento) => {
    mouse.x = (evento.clientX / window.innerWidth - 0.5) * 2;
    mouse.y = (evento.clientY / window.innerHeight - 0.5) * 2;
  });

  const reloj = new THREE.Clock();
  function dibujar() {
    const t = reloj.getElapsedTime();
    for (const huella of huellas) {
      const { baseY, fase, giro } = huella.userData;
      huella.position.y = baseY + Math.sin(t * 0.8 + fase) * 0.18; // flota arriba y abajo
      huella.rotation.y += giro * 0.01;
      huella.rotation.x = 0.3 + Math.sin(t * 0.5 + fase) * 0.15;
    }
    camara.position.x += (mouse.x * 0.6 - camara.position.x) * 0.04;
    camara.position.y += (-mouse.y * 0.4 - camara.position.y) * 0.04;
    camara.lookAt(0, 0, 0);
    renderer.render(escena, camara);
  }

  // Accesibilidad: con "reducir movimiento" activado se dibuja una sola vez, sin animación.
  if (reducirMovimiento) {
    dibujar();
    return;
  }

  // Ahorro de batería: solo anima mientras la portada está visible en pantalla.
  let visible = true;
  new IntersectionObserver(([entrada]) => { visible = entrada.isIntersecting; }).observe(escena3d);
  renderer.setAnimationLoop(() => {
    if (visible && !document.hidden) dibujar();
  });
}
