// Carnet de vacunación en 3D: un librito (Three.js, sin frameworks). Lo abre static/js/carnet.js.
// 1) Dibuja la portada, las páginas y el reverso en <canvas> con los datos de la mascota (atributos data-*).
// 2) Arma el librito: tapas rígidas con grosor y páginas que se doblan al pasarlas.
// 3) Se gira arrastrando; las páginas se pasan tocándolas, con las flechas o con los botones.
// 4) "Plano" muestra el carnet de frente y de reverso con el resumen de vacunas; "Descargar" baja todas las páginas.
// Sin WebGL, se abre directo en la vista plana.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// ---------- Medidas y colores ----------
const ANCHO = 1712;                     // texturas con la proporción de una tarjeta ID-1 (85,6 × 54 mm)
const ALTO = 1080;
const TARJETA_W = 3.2;                  // en unidades de la escena
const TARJETA_H = TARJETA_W * ALTO / ANCHO;
const RADIO = 0.17;
const GROSOR = 0.022;                   // de cada tapa
const BISEL = 0.008;
const MARGEN_HOJA = 0.06;               // las hojas son un poco más chicas que las tapas
const CAPA = 0.03;                      // separación entre tapas y hojas apiladas
const NOMBRES_PAGINAS = ['Portada', 'Datos y vacunas', 'Vacunas y próximas dosis'];

const COLOR = {
  crema: '#fffaf3',
  papel: '#fffdf8',
  durazno: '#fdebd3',
  naranja: '#ee9a35',
  naranjaTexto: '#b45309',
  marron: '#573f33',
  marronOscuro: '#3b2a22',
  gris: '#75655c',
  linea: 'rgba(87, 63, 51, 0.2)',
};
const TITULOS = "'Montserrat', system-ui, sans-serif";
const TEXTO = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

// =========================================================
// 0. Abrir el pop-up (lo llama carnet.js)
// =========================================================
export async function abrirCarnet(dialogo) {
  if (!dialogo.open) dialogo.showModal();
  dialogo.focus();                      // el foco empieza en el pop-up, sin anillo en ningún botón
  if (dialogo.carnet) {
    dialogo.carnet.alAbrir();
    return;
  }
  dialogo.carnet = { alAbrir() {} };   // evita prepararlo dos veces si se toca rápido

  const datos = dialogo.dataset;
  const escena = dialogo.querySelector('[data-carnet-escena]');
  const plano = dialogo.querySelector('[data-carnet-plano]');
  const paginador = dialogo.querySelector('[data-carnet-paginador]');
  const textoPagina = dialogo.querySelector('[data-pagina-texto]');
  const botonDescargar = dialogo.querySelector('[data-carnet-descargar]');
  const botonCaptura = dialogo.querySelector('[data-carnet-captura]');
  const modos = [...dialogo.querySelectorAll('[data-modo]')];

  // Cerrar: X o Escape (un clic en la escena es para girar, no cierra). La salida es más corta que la entrada
  const cerrar = () => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      dialogo.close();
      return;
    }
    dialogo.classList.add('es-cerrando');
    window.setTimeout(() => {
      dialogo.classList.remove('es-cerrando');
      dialogo.close();
    }, 180);
  };
  dialogo.querySelector('[data-cerrar-carnet]').addEventListener('click', cerrar);
  dialogo.addEventListener('cancel', (evento) => {
    evento.preventDefault();
    cerrar();
  });

  // Las fuentes y las imágenes deben estar listas antes de dibujar en los canvas
  const [foto, logo, logoBlanco] = await Promise.all([
    cargarImagen(datos.foto),
    cargarImagen(datos.logo),
    cargarImagen(datos.logoBlanco),
    document.fonts.load(`800 120px ${TITULOS}`),
    document.fonts.load(`700 60px ${TITULOS}`),
  ]);

  const caras = {
    portada: dibujarFrente(datos, foto, logo),
    datos: dibujarDatos(datos, logo),
    vacunas: dibujarVacunas(datos, 1),
    vacunasMas: dibujarVacunas(datos, 2),
    proximas: dibujarProximas(datos),
    reverso: dibujarReverso(datos, logoBlanco),
  };

  // Vista plana: el formato del carnet, de frente y de reverso
  const contenedorCaras = dialogo.querySelector('[data-carnet-caras]');
  [['portada', 'Frente del carnet'], ['reverso', 'Reverso del carnet']].forEach(([clave, alt]) => {
    const imagen = new Image();
    imagen.src = caras[clave].toDataURL('image/png');
    imagen.alt = `${alt} de ${datos.nombre}`;
    imagen.className = 'carnet-plano__cara';
    contenedorCaras.appendChild(imagen);
  });

  botonDescargar.disabled = false;
  botonDescargar.addEventListener('click', () => descargarPaginas(caras, datos.nombre));

  let vista = null;
  try {
    vista = crearLibro(escena, caras, (pagina) => {
      textoPagina.textContent = `${NOMBRES_PAGINAS[pagina]} · ${pagina + 1} de ${NOMBRES_PAGINAS.length}`;
    }, () => dialogo.open && !escena.hidden);
  } catch (error) {
    vista = null;
  }
  escena.querySelector('[data-carnet-cargando]')?.remove();

  function cambiarModo(modo) {
    const es3d = modo === '3d' && vista;
    modos.forEach((boton) => {
      const activo = boton.dataset.modo === (es3d ? '3d' : 'plano');
      boton.classList.toggle('es-activo', activo);
      boton.setAttribute('aria-pressed', String(activo));
    });
    escena.hidden = !es3d;
    plano.hidden = Boolean(es3d);
    paginador.style.visibility = es3d ? '' : 'hidden';   // conserva su lugar: las descargas no saltan
    botonCaptura.hidden = !es3d;
  }
  modos.forEach((boton) => boton.addEventListener('click', () => cambiarModo(boton.dataset.modo)));

  if (!vista) {
    // Sin WebGL: solo la vista plana
    modos.find((boton) => boton.dataset.modo === '3d').disabled = true;
    cambiarModo('plano');
    return;
  }

  dialogo.querySelector('[data-pagina-anterior]').addEventListener('click', () => vista.pasar(-1));
  dialogo.querySelector('[data-pagina-siguiente]').addEventListener('click', () => vista.pasar(1));
  botonCaptura.disabled = false;
  botonCaptura.addEventListener('click', () => descargar(vista.captura(), `carnet-3d-${nombreArchivo(datos.nombre)}.png`));

  dialogo.carnet = { alAbrir: vista.presentar };
  cambiarModo('3d');
  vista.presentar();
}

function cargarImagen(src) {
  if (!src) return Promise.resolve(null);
  return new Promise((resolver) => {
    const imagen = new Image();
    imagen.onload = () => resolver(imagen);
    imagen.onerror = () => resolver(null);   // sin foto o sin logo, el carnet se dibuja igual
    imagen.src = src;
  });
}

// =========================================================
// 1. Portada, reverso y páginas, dibujados en canvas
// =========================================================
function lienzo() {
  const canvas = document.createElement('canvas');
  canvas.width = ANCHO;
  canvas.height = ALTO;
  return [canvas, canvas.getContext('2d')];
}

function dibujarFrente(d, foto, logo) {
  const [canvas, ctx] = lienzo();

  // Fondo crema con un brillo durazno arriba a la derecha
  ctx.fillStyle = COLOR.crema;
  ctx.fillRect(0, 0, ANCHO, ALTO);
  const brillo = ctx.createRadialGradient(ANCHO * 0.95, 0, 0, ANCHO * 0.95, 0, ANCHO * 0.7);
  brillo.addColorStop(0, 'rgba(253, 235, 211, 0.95)');
  brillo.addColorStop(1, 'rgba(253, 235, 211, 0)');
  ctx.fillStyle = brillo;
  ctx.fillRect(0, 0, ANCHO, ALTO);

  // Foto a la izquierda, recortada para llenar el recuadro (como object-fit: cover)
  const caja = { x: 72, y: 72, w: 600, h: ALTO - 144, r: 52 };
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(caja.x, caja.y, caja.w, caja.h, caja.r);
  ctx.clip();
  if (foto) {
    const escala = Math.max(caja.w / foto.width, caja.h / foto.height);
    const w = foto.width * escala;
    const h = foto.height * escala;
    ctx.drawImage(foto, caja.x + (caja.w - w) / 2, caja.y + (caja.h - h) * 0.35, w, h);
  } else {
    const fondo = ctx.createLinearGradient(caja.x, caja.y, caja.x + caja.w, caja.y + caja.h);
    fondo.addColorStop(0, COLOR.durazno);
    fondo.addColorStop(1, '#fff3e2');
    ctx.fillStyle = fondo;
    ctx.fillRect(caja.x, caja.y, caja.w, caja.h);
    ctx.fillStyle = 'rgba(87, 63, 51, 0.45)';
    ctx.font = `800 360px ${TITULOS}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(d.nombre.charAt(0).toUpperCase(), caja.x + caja.w / 2, caja.y + caja.h / 2 + 20);
  }
  ctx.restore();

  // Píldora de vidrio con la especie, sobre la foto (como en las tarjetas del panel)
  ctx.font = `700 34px ${TEXTO}`;
  const anchoPildora = ctx.measureText(d.especie).width + 56;
  ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
  ctx.beginPath();
  ctx.roundRect(caja.x + 28, caja.y + 28, anchoPildora, 64, 32);
  ctx.fill();
  ctx.fillStyle = COLOR.marron;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(d.especie, caja.x + 56, caja.y + 61);

  // Columna derecha
  const x = 744;
  const derecha = ANCHO - 84;
  ctx.textBaseline = 'alphabetic';

  if (logo) {
    const alto = 78;
    const ancho = logo.width * alto / logo.height;
    ctx.drawImage(logo, derecha - ancho, 84, ancho, alto);
  }
  ctx.fillStyle = COLOR.naranjaTexto;
  ctx.font = `700 36px ${TEXTO}`;
  ctx.fillText('Carnet de salud', x, 140);

  // Nombre: grande, y se achica solo si no cabe
  ctx.fillStyle = COLOR.marron;
  let tamano = 150;
  do {
    ctx.font = `800 ${tamano}px ${TITULOS}`;
    tamano -= 6;
  } while (ctx.measureText(d.nombre).width > derecha - x && tamano > 60);
  ctx.letterSpacing = '-3px';
  ctx.fillText(d.nombre, x, 330);
  ctx.letterSpacing = '0px';

  ctx.fillStyle = COLOR.gris;
  ctx.font = `500 46px ${TEXTO}`;
  ctx.fillText(recortar(ctx, d.raza, derecha - x), x, 404);

  ctx.strokeStyle = 'rgba(87, 63, 51, 0.12)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(x, 468);
  ctx.lineTo(derecha, 468);
  ctx.stroke();

  // Datos en dos columnas: etiqueta chica arriba, valor grande abajo
  const campos = [['Edad', d.edad], ['Sexo', d.sexo], ['Peso', d.peso], ['Nacimiento', d.nacimiento]];
  const columna = (derecha - x) / 2;
  campos.forEach(([etiqueta, valor], i) => {
    const cx = x + (i % 2) * columna;
    const cy = 556 + Math.floor(i / 2) * 170;
    ctx.fillStyle = COLOR.gris;
    ctx.font = `600 32px ${TEXTO}`;
    ctx.fillText(etiqueta, cx, cy);
    // El valor se achica hasta caber ("Menos de un mes"); solo si aun así no cabe, se corta con "…"
    ctx.fillStyle = COLOR.marronOscuro;
    let tamanoValor = 52;
    do {
      ctx.font = `700 ${tamanoValor}px ${TITULOS}`;
      tamanoValor -= 2;
    } while (ctx.measureText(valor).width > columna - 30 && tamanoValor > 36);
    ctx.fillText(recortar(ctx, valor, columna - 30), cx, cy + 66);
  });

  // Pie: código y fecha de registro
  ctx.fillStyle = COLOR.gris;
  ctx.font = `600 32px ${TEXTO}`;
  ctx.fillText(`Nº ${d.codigo}`, x, ALTO - 104);
  ctx.textAlign = 'right';
  ctx.fillText(`En Woof desde ${d.registro}`, derecha, ALTO - 104);
  ctx.textAlign = 'left';

  // Rastro de huellas muy suave y una franja naranja al pie
  huellas(ctx, [[1500, 560, -0.5], [1590, 470, -0.35], [1530, 380, -0.5]], 26, 'rgba(238, 154, 53, 0.13)');
  ctx.fillStyle = COLOR.naranja;
  ctx.fillRect(0, ALTO - 30, ANCHO, 30);

  return canvas;
}

function dibujarReverso(d, logoBlanco) {
  const [canvas, ctx] = lienzo();

  ctx.fillStyle = COLOR.marron;
  ctx.fillRect(0, 0, ANCHO, ALTO);
  const luz = ctx.createRadialGradient(ANCHO * 0.15, ALTO * 0.1, 0, ANCHO * 0.15, ALTO * 0.1, ANCHO * 0.8);
  luz.addColorStop(0, 'rgba(255, 255, 255, 0.10)');
  luz.addColorStop(1, 'rgba(255, 255, 255, 0)');
  ctx.fillStyle = luz;
  ctx.fillRect(0, 0, ANCHO, ALTO);

  // Huella grande de marca de agua
  huellas(ctx, [[1380, 640, 0.35]], 210, 'rgba(255, 255, 255, 0.05)');

  const x = 96;
  if (logoBlanco) {
    const alto = 84;
    ctx.drawImage(logoBlanco, x, 88, logoBlanco.width * alto / logoBlanco.height, alto);
  }
  ctx.fillStyle = 'rgba(255, 250, 243, 0.75)';
  ctx.font = `600 36px ${TEXTO}`;
  ctx.textAlign = 'right';
  ctx.fillText('Carnet de vacunación', ANCHO - 96, 142);
  ctx.textAlign = 'left';

  ctx.fillStyle = COLOR.crema;
  ctx.font = `800 96px ${TITULOS}`;
  ctx.letterSpacing = '-2px';
  ctx.fillText(recortar(ctx, d.nombre, ANCHO - 2 * x), x, 340);
  ctx.letterSpacing = '0px';

  const vacunas = Number(d.vacunas || 0);
  const filas = [
    ['Tutor', d.tutor],
    ['Especie y raza', `${d.especie} · ${d.raza}`],
    ['Vacunas', vacunas ? `${vacunas} registrada${vacunas === 1 ? '' : 's'}` : 'Aún no hay vacunas registradas'],
  ];
  filas.forEach(([etiqueta, valor], i) => {
    const y = 470 + i * 150;
    ctx.fillStyle = 'rgba(255, 250, 243, 0.6)';
    ctx.font = `600 32px ${TEXTO}`;
    ctx.fillText(etiqueta, x, y);
    ctx.fillStyle = COLOR.crema;
    ctx.font = `700 50px ${TITULOS}`;
    ctx.fillText(recortar(ctx, valor, 1100), x, y + 64);
  });

  ctx.fillStyle = 'rgba(255, 250, 243, 0.6)';
  ctx.font = `600 30px ${TEXTO}`;
  ctx.fillText(`Nº ${d.codigo} · Las vacunas las registra el veterinario en cada visita.`, x, ALTO - 96);

  ctx.fillStyle = COLOR.naranja;
  ctx.fillRect(0, ALTO - 30, ANCHO, 30);
  return canvas;
}

// Corta el texto con "…" si no cabe en el ancho dado
function recortar(ctx, texto, ancho) {
  if (ctx.measureText(texto).width <= ancho) return texto;
  let corto = texto;
  while (corto.length > 1 && ctx.measureText(`${corto}…`).width > ancho) corto = corto.slice(0, -1);
  return `${corto.trimEnd()}…`;
}

// Huella: almohadilla y cuatro dedos (elipses), en [x, y, giro]
function huellas(ctx, lista, tamano, color) {
  ctx.fillStyle = color;
  lista.forEach(([x, y, giro]) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(giro);
    ctx.beginPath();
    ctx.ellipse(0, tamano * 0.35, tamano * 0.62, tamano * 0.5, 0, 0, Math.PI * 2);
    [[-0.62, -0.32], [-0.22, -0.68], [0.22, -0.68], [0.62, -0.32]].forEach(([dx, dy]) => {
      ctx.moveTo(dx * tamano + tamano * 0.2, dy * tamano);
      ctx.ellipse(dx * tamano, dy * tamano, tamano * 0.2, tamano * 0.26, dx * 0.4, 0, Math.PI * 2);
    });
    ctx.fill();
    ctx.restore();
  });
}

// ---------- Páginas interiores (papel con esquinas redondeadas y sombra junto al lomo) ----------
// lomo: 'izquierda' si la página va a la derecha del librito (el lomo le queda a la izquierda), o 'derecha'
function hoja(lomo) {
  const [canvas, ctx] = lienzo();
  ctx.beginPath();
  ctx.roundRect(0, 0, ANCHO, ALTO, 44);
  ctx.fillStyle = COLOR.papel;
  ctx.fill();
  const x0 = lomo === 'izquierda' ? 0 : ANCHO;
  const sombra = ctx.createLinearGradient(x0, 0, lomo === 'izquierda' ? 140 : ANCHO - 140, 0);
  sombra.addColorStop(0, 'rgba(87, 63, 51, 0.10)');
  sombra.addColorStop(1, 'rgba(87, 63, 51, 0)');
  ctx.fillStyle = sombra;
  ctx.fillRect(lomo === 'izquierda' ? 0 : ANCHO - 140, 0, 140, ALTO);
  return [canvas, ctx];
}

function numeroDePagina(ctx, numero, lomo) {
  ctx.fillStyle = COLOR.gris;
  ctx.font = `600 30px ${TEXTO}`;
  ctx.textAlign = lomo === 'izquierda' ? 'right' : 'left';
  ctx.fillText(String(numero), lomo === 'izquierda' ? ANCHO - 96 : 96, ALTO - 72);
  ctx.textAlign = 'left';
}

function tituloDePagina(ctx, titulo, x, y) {
  ctx.fillStyle = COLOR.marron;
  ctx.font = `800 68px ${TITULOS}`;
  ctx.letterSpacing = '-1.5px';
  ctx.fillText(titulo, x, y);
  ctx.letterSpacing = '0px';
}

// Valor que se achica hasta caber y, si aun así no cabe, se corta con "…"
function valorAjustado(ctx, valor, x, y, ancho, tamano = 48) {
  ctx.fillStyle = COLOR.marronOscuro;
  do {
    ctx.font = `700 ${tamano}px ${TITULOS}`;
    tamano -= 2;
  } while (ctx.measureText(valor).width > ancho && tamano > 34);
  ctx.fillText(recortar(ctx, valor, ancho), x, y);
}

// Página 1 (izquierda): los datos de la mascota y de su tutor
function dibujarDatos(d) {
  const [canvas, ctx] = hoja('derecha');
  const x = 110;
  tituloDePagina(ctx, `Datos de ${d.nombre}`, x, 180);
  ctx.fillStyle = COLOR.gris;
  ctx.font = `600 34px ${TEXTO}`;
  ctx.fillText(`Carnet de vacunación · Nº ${d.codigo}`, x, 240);

  const filas = [
    ['Tutor', d.tutor], ['Especie', d.especie],
    ['Raza', d.raza], ['Sexo', d.sexo],
    ['Nacimiento', d.nacimiento], ['Edad', d.edad],
    ['Peso', d.peso], ['En Woof desde', d.registro],
  ];
  const columna = (ANCHO - x - 200) / 2;
  filas.forEach(([etiqueta, valor], i) => {
    const cx = x + (i % 2) * columna;
    const cy = 350 + Math.floor(i / 2) * 150;
    ctx.fillStyle = COLOR.gris;
    ctx.font = `600 30px ${TEXTO}`;
    ctx.fillText(etiqueta, cx, cy);
    valorAjustado(ctx, valor, cx, cy + 60, columna - 40);
  });
  numeroDePagina(ctx, 1, 'derecha');
  return canvas;
}

// Páginas 2 y 3: registro de vacunas, con renglones listos para que el veterinario los llene
function dibujarVacunas(d, parte) {
  const lomo = parte === 1 ? 'izquierda' : 'derecha';
  const [canvas, ctx] = hoja(lomo);
  const x = 110;
  const derecha = ANCHO - 110;
  tituloDePagina(ctx, parte === 1 ? 'Vacunas aplicadas' : 'Vacunas aplicadas (cont.)', x, 180);

  const columnas = [['Fecha', 0], ['Vacuna', 0.17], ['Lote', 0.47], ['Próxima dosis', 0.62], ['Veterinario', 0.82]];
  const anchoTabla = derecha - x;
  ctx.fillStyle = COLOR.gris;
  ctx.font = `700 30px ${TEXTO}`;
  columnas.forEach(([nombre, desde]) => ctx.fillText(nombre, x + desde * anchoTabla, 290));

  ctx.strokeStyle = 'rgba(87, 63, 51, 0.28)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(x, 316);
  ctx.lineTo(derecha, 316);
  ctx.stroke();

  ctx.strokeStyle = COLOR.linea;
  ctx.lineWidth = 4;                    // grueso: la textura se ve reducida en pantalla
  for (let fila = 1; fila <= 6; fila += 1) {
    const y = 316 + fila * 108;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(derecha, y);
    ctx.stroke();
  }

  // Sin vacunas: lo dice en el primer renglón (no se inventan registros)
  if (parte === 1 && !Number(d.vacunas)) {
    ctx.fillStyle = COLOR.marron;
    ctx.font = `700 36px ${TEXTO}`;
    ctx.fillText('Aún no hay vacunas registradas.', x, 380);
    ctx.fillStyle = COLOR.gris;
    ctx.font = `500 30px ${TEXTO}`;
    ctx.fillText(`El veterinario anotará aquí cada vacuna que reciba ${d.nombre}.`, x, 470);
  }
  numeroDePagina(ctx, parte + 1, lomo);
  return canvas;
}

// Página 4 (derecha, sobre la contratapa): próximas dosis
function dibujarProximas(d) {
  const [canvas, ctx] = hoja('izquierda');
  const x = 110;
  const derecha = ANCHO - 110;
  tituloDePagina(ctx, 'Próximas dosis', x, 180);
  ctx.fillStyle = COLOR.gris;
  ctx.font = `500 32px ${TEXTO}`;
  ctx.fillText(`Tu veterinario anotará aquí cuándo le toca a ${d.nombre} su siguiente vacuna.`, x, 245);

  ctx.strokeStyle = COLOR.linea;
  ctx.lineWidth = 4;
  for (let fila = 0; fila < 6; fila += 1) {
    const y = 360 + fila * 100;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(derecha, y);
    ctx.stroke();
  }
  huellas(ctx, [[derecha - 60, ALTO - 150, -0.4]], 40, 'rgba(238, 154, 53, 0.18)');
  numeroDePagina(ctx, 4, 'izquierda');
  return canvas;
}

// =========================================================
// 2. El librito en 3D
// =========================================================
// Rectángulo redondeado con el borde izquierdo en x = 0 (ahí va el lomo)
function formaRedondeada(w, h, r) {
  const forma = new THREE.Shape();
  const y = -h / 2;
  forma.moveTo(r, y);
  forma.lineTo(w - r, y);
  forma.quadraticCurveTo(w, y, w, y + r);
  forma.lineTo(w, y + h - r);
  forma.quadraticCurveTo(w, y + h, w - r, y + h);
  forma.lineTo(r, y + h);
  forma.quadraticCurveTo(0, y + h, 0, y + h - r);
  forma.lineTo(0, y + r);
  forma.quadraticCurveTo(0, y, r, y);
  return forma;
}

// Las UV de ShapeGeometry vienen en coordenadas de la forma: se pasan a 0..1 para que la textura llene la cara
function caraConTextura(forma, w, h) {
  const geometria = new THREE.ShapeGeometry(forma, 24);
  const uv = geometria.attributes.uv;
  const pos = geometria.attributes.position;
  for (let i = 0; i < uv.count; i += 1) uv.setXY(i, pos.getX(i) / w, (pos.getY(i) + h / 2) / h);
  return geometria;
}

function crearLibro(contenedor, caras, alCambiarPagina, estaActivo) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;   // colores fieles a las texturas
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.classList.add('carnet-popup__lienzo');
  contenedor.appendChild(renderer.domElement);

  const escena = new THREE.Scene();
  escena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  const camara = new THREE.PerspectiveCamera(30, 1, 0.1, 60);

  escena.add(new THREE.HemisphereLight(0xfff6ea, 0xe8d5c0, 0.85));
  const principal = new THREE.DirectionalLight(0xffffff, 0.8);   // con la hemisférica suman ~1: el blanco no se quema
  principal.position.set(-1, 6, 4);
  principal.castShadow = true;
  principal.shadow.mapSize.set(1024, 1024);
  principal.shadow.radius = 8;
  Object.assign(principal.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5 });
  escena.add(principal);
  const contraluz = new THREE.DirectionalLight(0xffb867, 0.6);
  contraluz.position.set(3, 1, -4);
  escena.add(contraluz);

  const textura = (canvas, espejo = false) => {
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    if (espejo) {                       // la cara de atrás de una hoja se ve desde el otro lado
      t.wrapS = THREE.RepeatWrapping;
      t.repeat.x = -1;
    }
    return t;
  };
  const materialTapa = (canvas) => new THREE.MeshPhysicalMaterial({
    map: textura(canvas), roughness: 0.62, clearcoat: 0.3, clearcoatRoughness: 0.5, envMapIntensity: 0.45,
  });
  const canto = new THREE.MeshPhysicalMaterial({
    color: 0xf3c58c, roughness: 0.35, metalness: 0.1, clearcoat: 0.8, clearcoatRoughness: 0.25,
  });

  // Tapa: cuerpo con grosor y bisel, y una cara con textura a cada lado
  const forma = formaRedondeada(TARJETA_W, TARJETA_H, RADIO);
  const cuerpoGeo = new THREE.ExtrudeGeometry(forma, {
    depth: GROSOR, bevelEnabled: true, bevelThickness: BISEL, bevelSize: BISEL, bevelSegments: 4, curveSegments: 20,
  });
  cuerpoGeo.translate(0, 0, -GROSOR / 2);
  const caraGeo = caraConTextura(forma, TARJETA_W, TARJETA_H);
  const superficie = GROSOR / 2 + BISEL + 0.0015;

  function tapa(afuera, adentro) {
    const grupo = new THREE.Group();
    const cuerpo = new THREE.Mesh(cuerpoGeo, canto);
    cuerpo.castShadow = true;
    const delante = new THREE.Mesh(caraGeo, materialTapa(afuera));
    delante.position.z = superficie;
    // La cara de adentro se ve por detrás: se gira la geometría alrededor del eje vertical que pasa por su centro
    const detras = new THREE.Mesh(caraGeo, materialTapa(adentro));
    detras.rotation.y = Math.PI;
    detras.position.set(TARJETA_W, 0, -superficie);
    grupo.add(cuerpo, delante, detras);
    return grupo;
  }

  // Hoja: un plano con muchas columnas para poder doblarlo al pasar la página
  const hojaW = TARJETA_W - MARGEN_HOJA - 0.02;
  const hojaH = TARJETA_H - MARGEN_HOJA * 2;
  const hojaGeo = new THREE.PlaneGeometry(hojaW, hojaH, 40, 1);
  hojaGeo.translate(hojaW / 2 + 0.02, 0, 0);
  const hojaPlana = Float32Array.from(hojaGeo.attributes.position.array);
  const materialHoja = (canvas, lado, espejo) => new THREE.MeshStandardMaterial({
    map: textura(canvas, espejo), roughness: 0.85, side: lado, alphaTest: 0.5, envMapIntensity: 0.4,   // el reflejo del ambiente quemaba el papel
  });

  // ---- Armado: contratapa fija a la derecha, hoja y portada encima ----
  const libro = new THREE.Group();          // lo que se gira arrastrando
  const centro = new THREE.Group();         // se corre a la derecha al abrirse, para quedar centrado
  libro.add(centro);
  escena.add(libro);

  const contratapa = tapa(caras.reverso, caras.reverso);
  // La contratapa muestra el reverso hacia atrás y, hacia adelante, la página de próximas dosis pegada encima
  contratapa.children[1].visible = false;
  const paginaFinal = new THREE.Mesh(new THREE.PlaneGeometry(hojaW, hojaH), materialHoja(caras.proximas, THREE.FrontSide, false));
  paginaFinal.position.set(hojaW / 2 + 0.02, 0, superficie + 0.002);
  contratapa.add(paginaFinal);
  centro.add(contratapa);

  const hojaGrupo = new THREE.Group();
  const hojaDelante = new THREE.Mesh(hojaGeo, materialHoja(caras.vacunas, THREE.FrontSide, false));
  const hojaDetras = new THREE.Mesh(hojaGeo, materialHoja(caras.vacunasMas, THREE.BackSide, true));
  hojaDelante.castShadow = true;
  hojaGrupo.add(hojaDelante, hojaDetras);
  centro.add(hojaGrupo);

  const portada = tapa(caras.portada, caras.datos);
  centro.add(portada);

  // Lomo: una varilla naranja que une las tapas
  const lomo = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, TARJETA_H * 0.96, 24), canto);
  lomo.position.z = superficie;
  centro.add(lomo);

  // Piso invisible que solo recibe la sombra
  const piso = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.ShadowMaterial({ opacity: 0.07 }));
  piso.rotation.x = -Math.PI / 2;
  piso.position.y = -TARJETA_H / 2 - 0.55;
  piso.receiveShadow = true;
  escena.add(piso);

  // Hojas que giran: portada y hoja. z = altura en la pila cerrada (derecha) y ya pasada (izquierda)
  const hojas = [
    { grupo: portada, cerrada: superficie * 2 + CAPA * 2, pasada: 0, progreso: 0, meta: 0 },
    { grupo: hojaGrupo, cerrada: superficie + CAPA, pasada: superficie + 0.012, progreso: 0, meta: 0, dobla: true },
  ];
  let pagina = 0;

  function irA(nueva) {
    pagina = THREE.MathUtils.clamp(nueva, 0, hojas.length);
    hojas.forEach((h, i) => { h.meta = i < pagina ? 1 : 0; });
    alCambiarPagina(pagina);
  }

  // Dobla la hoja: el borde libre se queda atrás mientras gira (curva más fuerte a mitad de camino)
  function doblar(h) {
    const pos = hojaGeo.attributes.position;
    const curva = Math.sin(h.progreso * Math.PI) * 0.55;
    for (let i = 0; i < pos.count; i += 1) {
      const u = (hojaPlana[i * 3] - 0.02) / hojaW;
      pos.setZ(i, -curva * u * u);
    }
    pos.needsUpdate = true;
    hojaGeo.computeVertexNormals();
  }

  // ---------- Movimiento ----------
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const giro = { x: 0, y: 0 };
  const meta = { x: 0, y: 0 };
  const inclinacion = { x: 0, y: 0 };
  const velocidad = { x: 0, y: 0 };
  let arrastrando = false;
  let recorrido = 0;
  let ultimo = null;
  let ultimaInteraccion = performance.now();
  let escala = 1;
  let distancia = 6;

  const lienzo3d = renderer.domElement;
  lienzo3d.addEventListener('pointerdown', (evento) => {
    arrastrando = true;
    recorrido = 0;
    ultimo = { x: evento.clientX, y: evento.clientY };
    velocidad.x = velocidad.y = 0;
    lienzo3d.setPointerCapture(evento.pointerId);
  });
  lienzo3d.addEventListener('pointermove', (evento) => {
    const caja = lienzo3d.getBoundingClientRect();
    if (arrastrando) {
      const dx = evento.clientX - ultimo.x;
      const dy = evento.clientY - ultimo.y;
      recorrido += Math.abs(dx) + Math.abs(dy);
      ultimo = { x: evento.clientX, y: evento.clientY };
      if (recorrido > 6) contenedor.classList.add('esta-arrastrando');
      velocidad.y = dx * 0.008;
      velocidad.x = dy * 0.005;
      meta.y += velocidad.y;
      meta.x = THREE.MathUtils.clamp(meta.x + velocidad.x, -0.6, 0.6);
      ultimaInteraccion = performance.now();
    } else if (evento.pointerType === 'mouse' && !sinMovimiento) {
      inclinacion.y = ((evento.clientX - caja.left) / caja.width - 0.5) * 0.16;
      inclinacion.x = ((evento.clientY - caja.top) / caja.height - 0.5) * 0.12;
    }
  });
  lienzo3d.addEventListener('pointerup', (evento) => {
    if (!arrastrando) return;
    arrastrando = false;
    contenedor.classList.remove('esta-arrastrando');
    if (recorrido <= 6) {
      // Un toque sin arrastrar: mitad derecha, página siguiente; mitad izquierda, la anterior
      const caja = lienzo3d.getBoundingClientRect();
      irA(pagina + (evento.clientX > caja.left + caja.width / 2 ? 1 : -1));
    } else {
      meta.y += velocidad.y * 10;     // inercia
    }
    ultimaInteraccion = performance.now();
  });
  lienzo3d.addEventListener('pointercancel', () => {
    arrastrando = false;
    contenedor.classList.remove('esta-arrastrando');
  });
  lienzo3d.addEventListener('pointerleave', () => { inclinacion.x = inclinacion.y = 0; });

  contenedor.addEventListener('keydown', (evento) => {
    if (evento.key === 'ArrowRight') irA(pagina + 1);
    else if (evento.key === 'ArrowLeft') irA(pagina - 1);
    else if (evento.key === 'ArrowUp') meta.x = Math.max(meta.x - 0.2, -0.6);
    else if (evento.key === 'ArrowDown') meta.x = Math.min(meta.x + 0.2, 0.6);
    else return;
    evento.preventDefault();
    ultimaInteraccion = performance.now();
  });

  // ---------- Tamaño: la cámara se aleja o se acerca para que el librito (cerrado o abierto) quepa ----------
  function distanciaIdeal(abierto) {
    const tangente = Math.tan(THREE.MathUtils.degToRad(camara.fov / 2));
    const porAlto = (TARJETA_H * 1.45) / (2 * tangente);
    const porAncho = (TARJETA_W * (1 + abierto) * 1.15) / (2 * tangente * camara.aspect);
    return Math.max(porAlto, porAncho);
  }
  function ajustar() {
    const { width, height } = contenedor.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camara.aspect = width / height;
    camara.updateProjectionMatrix();
  }
  new ResizeObserver(ajustar).observe(contenedor);
  ajustar();
  distancia = distanciaIdeal(0);

  // ---------- Bucle (solo mientras el pop-up está abierto en la vista 3D) ----------
  const reloj = new THREE.Clock();
  let autoAbrir = null;

  function cuadro() {
    requestAnimationFrame(cuadro);
    const dt = Math.min(reloj.getDelta(), 0.05);
    if (!estaActivo()) return;
    const t = reloj.elapsedTime;

    if (!arrastrando && performance.now() - ultimaInteraccion > 2500) {
      meta.x = 0;
      meta.y = Math.round(meta.y / Math.PI) * Math.PI;   // vuelve de frente (o de espaldas, si la dejaste así)
    }
    const suave = sinMovimiento ? 1 : 1 - Math.exp(-dt * (arrastrando ? 18 : 6));
    giro.x += (meta.x + inclinacion.x - giro.x) * suave;
    giro.y += (meta.y + inclinacion.y - giro.y) * suave;
    escala += (1 - escala) * suave;

    // Pasar páginas: cada hoja gira sobre el lomo y sube un poco a mitad de camino para no rozar la pila
    const suavePagina = sinMovimiento ? 1 : 1 - Math.exp(-dt * 4.5);
    hojas.forEach((h) => {
      const antes = h.progreso;
      h.progreso += (h.meta - h.progreso) * suavePagina;
      if (Math.abs(h.meta - h.progreso) < 0.0005) h.progreso = h.meta;
      h.grupo.rotation.y = -h.progreso * Math.PI;
      h.grupo.position.z = h.cerrada + (h.pasada - h.cerrada) * h.progreso + Math.sin(h.progreso * Math.PI) * 0.25;
      if (h.dobla && h.progreso !== antes) doblar(h);
    });

    // Cerrado, el librito se centra; abierto, el lomo queda al centro
    const abierto = hojas[0].progreso;
    centro.position.x = -TARJETA_W / 2 * (1 - abierto);
    distancia += (distanciaIdeal(abierto) - distancia) * (sinMovimiento ? 1 : 1 - Math.exp(-dt * 4));
    camara.position.set(0, 0.15, distancia);
    camara.lookAt(0, 0, 0);

    libro.rotation.set(giro.x, giro.y, 0);
    libro.position.y = sinMovimiento ? 0 : Math.sin(t * 1.1) * 0.04;   // flota apenas
    libro.scale.setScalar(escala);
    renderer.render(escena, camara);
  }
  cuadro();
  contenedor.classList.add('esta-lista');

  return {
    pasar(paso) {
      irA(pagina + paso);
      ultimaInteraccion = performance.now();
    },
    // Al abrir el pop-up: aparece cerrado, se acomoda y se abre solo en la primera página
    presentar() {
      window.clearTimeout(autoAbrir);
      irA(0);
      if (!sinMovimiento) {
        escala = 0.88;
        giro.y = -0.55;
        hojas.forEach((h) => { h.progreso = 0; });
        doblar(hojas[1]);
      }
      autoAbrir = window.setTimeout(() => irA(1), sinMovimiento ? 0 : 650);
    },
    captura() {
      renderer.render(escena, camara);
      return renderer.domElement.toDataURL('image/png');
    },
  };
}

// =========================================================
// 3. Descargas
// =========================================================
// Todas las páginas en una imagen: portada y reverso arriba, el interior debajo (dos por fila)
function descargarPaginas(caras, nombre) {
  const orden = [caras.portada, caras.reverso, caras.datos, caras.vacunas, caras.vacunasMas, caras.proximas];
  const margen = 96;
  const canvas = document.createElement('canvas');
  canvas.width = ANCHO * 2 + margen * 3;
  canvas.height = ALTO * 3 + margen * 4;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#f6efe6';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  orden.forEach((cara, i) => {
    const x = margen + (i % 2) * (ANCHO + margen);
    const y = margen + Math.floor(i / 2) * (ALTO + margen);
    ctx.save();
    ctx.shadowColor = 'rgba(59, 42, 34, 0.16)';
    ctx.shadowBlur = 36;
    ctx.shadowOffsetY = 14;
    ctx.beginPath();
    ctx.roundRect(x, y, ANCHO, ALTO, 50);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x, y, ANCHO, ALTO, 50);
    ctx.clip();
    ctx.drawImage(cara, x, y);
    ctx.restore();
  });
  descargar(canvas.toDataURL('image/png'), `carnet-${nombreArchivo(nombre)}.png`);
}

function descargar(url, nombre) {
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
}

function nombreArchivo(texto) {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'mascota';
}
