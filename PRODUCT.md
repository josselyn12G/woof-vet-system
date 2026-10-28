# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Woof es un proyecto académico de la materia Ingeniería Web (Universidad de las Américas), hecho por Josselyn Guevara y Adrián Freire, para una clínica veterinaria ficticia de Quito. Se evalúa en entregas presenciales y videos ante el docente.

Dentro del producto hay tres roles, todos con el mismo modelo `Usuario` y el mismo inicio de sesión:

- **Cliente** (dueño de una o varias mascotas, rol por defecto al registrarse): registra a sus mascotas y, con el Core, agenda, reprograma y cancela sus citas. Usa el sistema de vez en cuando, muchas veces desde el celular.
- **Veterinario** (personal de la clínica): publica su horario por fecha, elige los servicios que atiende, revisa su agenda del día y cierra cada cita (atendida o no asistió). Lo usa todos los días, entre consulta y consulta.
- **Administrador** (responsable de la clínica): gestiona las cuentas y sus roles, mantiene el catálogo de servicios y supervisa las citas y la ocupación.
- **Visitante**: ve la portada pública, se registra e inicia sesión.

## Product Purpose

Reemplazar la coordinación por teléfono, WhatsApp y papel de una clínica veterinaria por una sola aplicación web: desde que el dueño registra a su mascota y agenda una cita, hasta que el veterinario la atiende y registra la consulta.

Éxito, en el contexto académico: cada entrega cumple su consigna y se puede demostrar en vivo y defender en el código (patrón MVC con Django, URLs protegidas, validaciones en el servidor).

## Positioning

El Core es el **agendamiento de citas con control de disponibilidad**: el sistema calcula solo los horarios realmente libres de cada veterinario (según su horario publicado y la duración del servicio) y garantiza que nunca existan dos citas activas que se crucen, aunque dos clientes reserven el mismo turno al mismo tiempo (transacción con bloqueo, revisión del cruce y una regla `UniqueConstraint` en la base). La cita se crea ya confirmada, y reprogramar es una sola operación atómica: si el nuevo horario falla, la cita conserva el anterior.

## Operating Context

- El horario es del veterinario, no del servicio: publica bloques por fecha; el servicio solo aporta la duración con que se cortan los turnos, y el cruce se revisa contra todas sus citas.
- Estados de la cita: confirmada, atendida, no asistió, cancelada. Una cita no se borra: cambia de estado.
- Cada pantalla privada exige sesión con doble factor (código de 6 dígitos por correo) y muestra solo lo que el rol permite; un recurso ajeno responde 404.
- La evaluación ocurre en demos en vivo y videos (Loom o YouTube): el recorrido debe poder mostrarse de punta a punta con datos de ejemplo.

## Capabilities and Constraints

- Stack existente: Django 5.2 (patrón MVC/MTV), plantillas de Django, Bootstrap 5.3, PostgreSQL en Neon. Sin framework de JavaScript.
- Interfaz y textos en español (Ecuador). Zona horaria `America/Guayaquil`.
- Apps: `cuentas` (portada, registro, login con doble factor, roles, panel por rol, gestión de usuarios) y `mascotas` (CRUD con foto). En construcción: `citas` (Servicio, HorarioVeterinario, Cita, AgendaService).
- La cédula ecuatoriana es el dato sensible: se valida en el servidor (módulo 10) y es única.
- Cada funcionalidad lleva pruebas en el `tests.py` de su app; GitHub Actions las corre en cada Pull Request.
- Debe estar desplegado (pendiente para la Fase 2).
- Fuera del alcance actual: cobro en línea, historia clínica completa, vacunas, tratamientos, SMS, login con Google.

## Brand Commitments

- Nombre: **Woof**. Logos en `static/img/logo.png`, `static/img/logo-blanco.png` y `cuentas/static/cuentas/img/logo-correo.png`.
- Voz: español cercano, tuteando ("Revisa tu correo", "Registra a tu primera mascota"); claro y concreto, sin tecnicismos para el cliente.
- La identidad visual aprobada está en los prototipos del Anexo A del documento de análisis (`docs/Documento_de_Analisis_Woof_Guevara_Freire.pdf`).

## Evidence on Hand

- Solo hay **datos de ejemplo**: no existen clientes, veterinarios, opiniones, calificaciones ni cifras reales. Ninguna pantalla debe mostrar testimonios, estadísticas o logros inventados como si fueran reales.
- Documento de análisis del Core aprobado por el docente: `docs/Documento_de_Analisis_Woof_Guevara_Freire.pdf` (reglas, estados, RF-01 a RF-25, plan de pruebas, wireframes).
- Historias de usuario y modelo de datos: `docs/HISTORIAS_DE_USUARIO.md`, `docs/MODELO_DE_DATOS.md`.

## Product Principles

1. **El servidor decide.** Toda regla importante (cédula, cruces de horario, permisos por rol) se valida en Django y, cuando se puede, también en la base; el JavaScript solo avisa antes.
2. **Ninguna cita se pierde ni se cruza.** Agendar y reprogramar son operaciones atómicas; ante la duda, la reserva existente se conserva.
3. **Cada quien ve solo lo suyo.** El rol define las pantallas y los datos; lo ajeno no existe para el usuario (404).
4. **Honesto con los datos.** Mostrar números y estados reales, aunque sean cero; un vacío explica qué hacer, nunca se rellena con cifras inventadas.
5. **Defendible en la demo.** Cada decisión debe poder explicarse en el código y probarse con una prueba automática.

## Accessibility & Inclusion

Sin un estándar formal exigido. Prácticas ya presentes que se mantienen: foco visible con el teclado, respeto de `prefers-reduced-motion`, textos alternativos y etiquetas en los formularios.
