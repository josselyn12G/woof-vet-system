<p align="center">
  <img src="static/img/logo.png" alt="Woof" width="220">
</p>

<h1 align="center">Woof · Sistema veterinario</h1>

<p align="center">
  Citas, recetas, tratamientos y el carnet de vacunas de tu mascota, en un solo lugar.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/estado-en%20desarrollo-ee9a35" alt="Estado: en desarrollo">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Django-5.2%20LTS-092E20?logo=django&logoColor=white" alt="Django 5.2 LTS">
  <img src="https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL en Neon">
  <img src="https://img.shields.io/badge/pruebas-196%20pasan-2e7d32" alt="196 pruebas pasan">
</p>

<p align="center">
  <img src="docs/img/inicio.webp" alt="Portada de Woof" width="800">
</p>

## Índice

- [Descripción](#descripción)
- [Estado del proyecto](#estado-del-proyecto)
- [Funcionalidades](#funcionalidades)
- [Capturas](#capturas)
- [Cómo ejecutarlo](#cómo-ejecutarlo)
- [Despliegue en Render](#despliegue-en-render)
- [Pruebas](#pruebas)
- [Tecnologías](#tecnologías)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Documentación](#documentación)
- [Cómo contribuir](#cómo-contribuir)
- [Personas desarrolladoras](#personas-desarrolladoras)
- [Licencia](#licencia)

## Descripción

Woof es una aplicación web para una clínica veterinaria. Los dueños de mascotas registran a sus animales y agendan citas con el veterinario que atiende cada servicio; los veterinarios publican su horario y llevan su agenda del día, y el administrador gestiona usuarios y el catálogo de servicios. En las siguientes fases llegan la historia clínica y el carnet de vacunación.

**Demo:** https://woof-b6yo.onrender.com (plan gratuito de Render: la primera visita puede tardar unos segundos en despertar el servidor).

Es el proyecto de la materia **Ingeniería Web**, construido con Django siguiendo el patrón MVC (en Django, MTV: modelo, plantilla y vista).

## Estado del proyecto

**En desarrollo.** La Entrega 1, los roles y el Core de citas están terminados.

| Versión | Alcance | Estado |
|---|---|---|
| `v0.1.0` · Entrega 1 | Portada, registro, login con doble factor, CRUD de mascotas con URLs protegidas | Terminada |
| `v0.2.0` · Roles y citas | Roles con su panel, cédula validada, catálogo de servicios, horario del veterinario, agendar y cancelar citas, agenda y pacientes, despliegue en Render | Terminada |
| Próximas | Historia clínica, carnet de vacunación, login con Google y correos con SendGrid | Pendiente |

## Funcionalidades

- **Registro de usuarios** en 3 pasos, con validación del teléfono en formato internacional (`+593…`).
- **Inicio de sesión con doble factor:** después de la contraseña, Woof envía un código de 6 dígitos al correo.
  - El código vence a los 5 minutos y se puede usar una sola vez.
  - Se genera con `secrets` y se compara con `secrets.compare_digest`.
- **Cierre de sesión** por POST, protegido con CSRF.
- **CRUD de mascotas:** crear, ver, editar y eliminar, con foto.
  - La foto se reduce a 800 px y se guarda en formato WEBP.
- **URLs protegidas:** sin sesión, cualquier página de mascotas redirige al login y, al terminar, vuelve a la página que se pidió.
- **Cada dueño ve solo sus mascotas:** la mascota de otra persona responde 404.
- **Cédula ecuatoriana validada en el servidor:** provincia, tercer dígito y dígito verificador (módulo 10).

### Roles

- **Cliente, veterinario y administrador**, cada uno con su panel. Una página de otro rol responde 403.
- **El administrador** busca usuarios, cambia su rol y descarga un reporte en CSV.

### Citas

- **Catálogo de servicios (administrador):** nombre, descripción, duración, precio y veterinarios que lo atienden. Un servicio con citas no se borra: se desactiva.
- **Mi horario (veterinario):** bloques por día, sin cruces ni fechas pasadas; copiar la semana anterior y elegir los servicios que atiende.
- **Agendar (cliente):** en un pop-up dentro de Mis citas: mascota, servicio, calendario con los días que tienen horas libres y las horas agrupadas por doctor.
  - Los turnos se calculan cortando el horario del veterinario en bloques del largo del servicio.
  - Dos clientes no pueden ganar el mismo turno: la reserva se guarda en una transacción con la fila del veterinario bloqueada, y la base tiene un índice único como respaldo.
- **Mis citas (cliente):** próximas, pasadas y canceladas; cancelar con confirmación, lo que libera el turno.
- **Agenda (veterinario):** las citas del día y el cierre de cada una como «atendida» o «no asistió».
- **Pacientes (veterinario):** mascotas con su dueño, buscador por nombre, cédula o teléfono, y filtro «mis pacientes».

## Capturas

### Cuentas

| Registro | Inicio de sesión | Código de verificación |
|---|---|---|
| <img src="docs/img/registro.webp" alt="Registro en 3 pasos" width="280"> | <img src="docs/img/login.webp" alt="Pantalla de inicio de sesión" width="280"> | <img src="docs/img/verificar.webp" alt="Ventana para escribir el código de 6 dígitos" width="280"> |

### CRUD de mascotas

<p align="center">
  <img src="docs/img/mascotas-lista.webp" alt="Lista de mascotas del usuario, con foto, especie, edad y peso" width="800">
</p>

| Crear | Ver detalle |
|---|---|
| <img src="docs/img/mascotas-nueva.webp" alt="Formulario para registrar una mascota" width="400"> | <img src="docs/img/mascotas-detalle.webp" alt="Ficha completa de una mascota" width="400"> |

| Editar | Eliminar |
|---|---|
| <img src="docs/img/mascotas-editar.webp" alt="Formulario para editar una mascota" width="400"> | <img src="docs/img/mascotas-eliminar.webp" alt="Confirmación antes de eliminar una mascota" width="400"> |

<sub>Las capturas usan datos de ejemplo.</sub>

## Cómo ejecutarlo

### Requisitos

- Python **3.12**
- Git
- Una cuenta de Gmail con [contraseña de aplicación](https://myaccount.google.com/apppasswords), para enviar los códigos de acceso.
- Opcional: una base de datos PostgreSQL en [Neon](https://neon.tech). Sin ella, el proyecto usa SQLite.

### Pasos

```bash
git clone https://github.com/josselyn12G/woof-vet-system.git
cd woof-vet-system

python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # y completa los valores (ver abajo)

python manage.py migrate
python manage.py createsuperuser   # opcional: usuario para /admin/
python manage.py runserver
```

Abre http://127.0.0.1:8000/ · Panel de administración: http://127.0.0.1:8000/admin/

### Variables de entorno (`.env`)

| Variable | Para qué sirve | ¿Obligatoria? |
|---|---|---|
| `EMAIL_HOST_USER` | Correo de Gmail que envía los códigos | Sí |
| `EMAIL_HOST_PASSWORD` | Contraseña de aplicación de ese Gmail (16 letras) | Sí |
| `DATABASE_URL` | Conexión a PostgreSQL en Neon | No: sin ella usa SQLite |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | Configuración para producción | Solo en producción |
| `DJANGO_DOBLE_FACTOR` | `False` apaga el código por correo al iniciar sesión | No: por defecto `True` |

> [!WARNING]
> El archivo `.env` tiene contraseñas: nunca lo subas a Git. Ya está en `.gitignore`.

> [!TIP]
> Cada vez que un `git pull` cambie `requirements.txt`, vuelve a ejecutar `pip install -r requirements.txt`.

## Despliegue en Render

La app está publicada en https://woof-b6yo.onrender.com como *Web Service* de Python, con la misma base de Neon.

| Paso | Qué hace |
|---|---|
| Build Command: `./build.sh` | Instala dependencias, ejecuta `collectstatic` y aplica las migraciones (`migrate`) |
| Start Command: `gunicorn config.wsgi:application` | Arranca Django |
| Estáticos | Los sirve WhiteNoise, comprimidos y con caché |
| Variables | `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_DOBLE_FACTOR=False` (el plan gratuito bloquea el SMTP) |
| Publicar cambios | *Manual Deploy* → *Deploy latest commit* después de fusionar el PR |

> [!WARNING]
> `build.sh` ejecuta `migrate` en la base de Neon que usa todo el equipo. Antes de desplegar una migración nueva, revísala con `python manage.py migrate --plan` y avisa al equipo.

## Pruebas

```bash
python manage.py test
```

196 pruebas:

| App | Pruebas | Qué cubren |
|---|---|---|
| `cuentas` | 40 | Modelo de usuario, cédula, registro, login, doble factor y acceso por rol |
| `mascotas` | 59 | CRUD, acceso sin sesión, mascotas de otro dueño y fotos |
| `citas` | 97 | Servicios, horario, turnos libres, agendar (incluye turno ocupado y cruces), cancelar, agenda, pacientes y acceso por rol |

Durante las pruebas no se envían correos reales: Django los guarda en memoria.

## Tecnologías

| Área | Tecnología |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Base de datos | PostgreSQL en Neon (`psycopg`, `dj-database-url`); SQLite en local |
| Correo | Gmail por SMTP |
| Despliegue | Render, gunicorn y WhiteNoise |
| Imágenes | Pillow |
| Frontend | Plantillas de Django, Bootstrap 5.3, Bootstrap Icons, Three.js, JavaScript con `fetch` para el calendario de citas |
| Calidad | Pruebas con `django.test`, Ruff, Conventional Commits; todo validado con GitHub Actions |

## Estructura del proyecto

```
woof-vet-system/
├── config/              configuración del proyecto (settings.py, urls.py)
├── cuentas/             portada, registro, login, doble factor, roles y panel de cada rol
├── mascotas/            CRUD de mascotas y carnet
├── citas/               servicios, horario, agendar, Mis citas, agenda y pacientes
│   └── services.py      AgendaService: reglas de turnos libres, agendar y cancelar
├── templates/           plantillas comunes (base.html y panel_base.html)
├── static/              CSS, JavaScript e imágenes comunes
├── docs/                guías del equipo, historias de usuario y modelo de datos
├── .github/             CI (pruebas, Ruff y migraciones), validación de commits y releases
├── build.sh             pasos de despliegue en Render
├── requirements.txt     dependencias de Python
└── manage.py            comandos de Django
```

## Documentación

| Documento | Contenido |
|---|---|
| [HISTORIAS_DE_USUARIO.md](docs/HISTORIAS_DE_USUARIO.md) | Alcance y criterios de aceptación de cada fase |
| [MODELO_DE_DATOS.md](docs/MODELO_DE_DATOS.md) | Diagrama entidad-relación y campos de cada tabla |
| `Guia_Git_y_CI_CD.docx` · [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) | Ramas, commits y el trabajo diario paso a paso |
| `Guia_GitHub_Projects.docx` | Issues, tablero del equipo y cómo se conectan con ramas y PRs |
| `Arquitectura_del_Proyecto.docx` | Qué es cada archivo y cómo crear un módulo nuevo |
| `Crear_un_Modulo_Mascotas.docx` | Tutorial: módulo de mascotas completo (modelo, vistas, URLs, plantillas y pruebas) |
| `Entorno_Virtual_Python.docx` | Qué es el `.venv`, para qué sirve y cómo usarlo |
| `Pruebas_y_CI_CD.docx` · [CI_CD.md](docs/CI_CD.md) | Cómo escribir pruebas y cómo las valida GitHub Actions |

## Cómo contribuir

1. Crea una rama desde `develop` actualizado: `feat/<issue>-<nombre>`.
2. Escribe commits con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/): el tipo en inglés y la descripción en español, por ejemplo `feat(mascotas): agrega la foto de la mascota`.
3. Antes del Pull Request, `python manage.py test` debe pasar.
4. Abre el Pull Request hacia `develop`. Se fusiona con *squash and merge*.

Más detalles en [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md).

## Personas desarrolladoras

| [<img src="https://github.com/josselyn12G.png" width="100" alt="Foto de Josselyn Guevara"><br><sub>Josselyn Guevara</sub>](https://github.com/josselyn12G) | [<img src="https://github.com/adripatacon.png" width="100" alt="Foto de Adrián Freire"><br><sub>Adrián Freire</sub>](https://github.com/adripatacon) |
| :---: | :---: |
| Portada, registro, login y doble factor · roles y panel · cédula · agendar, Mis citas, agenda y pacientes | CRUD de mascotas y URLs protegidas · modelos de servicio y horario · catálogo de servicios · Mi horario · despliegue en Render |

## Licencia

Proyecto académico de la materia Ingeniería Web. Todavía no tiene una licencia de código abierto.
