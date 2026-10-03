# Historias de usuario — Woof

> **Borrador para revisar con Adrián.** Ajusten, quiten o agreguen. La columna *Entrega* dice si entra el lunes 5 de octubre (Entrega 1) o después.

Formato: **Como** `<rol>` **quiero** `<acción>` **para** `<beneficio>`, con criterios de aceptación verificables (lo que el profe puede probar en la demo).

## Roles

| Rol | Quién es |
|---|---|
| Visitante | Persona sin cuenta o sin sesión iniciada |
| Cliente | Dueño de una o varias mascotas, con cuenta |
| Veterinario | Personal de la clínica que atiende mascotas (Fase 3) |
| Administrador | Gestiona usuarios y datos del sistema (usa `/admin/` de Django) |

## Resumen

| ID | Historia | Rol | Responsable | Entrega |
|---|---|---|---|---|
| HU-01 | Ver la página de inicio | Visitante | Josselyn | **Lunes** |
| HU-02 | Registrarme | Visitante | Josselyn | **Lunes** |
| HU-03 | Iniciar sesión | Visitante | Josselyn | **Lunes** |
| HU-04 | Cerrar sesión | Cliente | Josselyn | **Lunes** |
| HU-05 | Páginas privadas protegidas | Visitante | Josselyn + Adrián | **Lunes** |
| HU-06 | Registrar una mascota | Cliente | Adrián | **Lunes** |
| HU-07 | Ver mis mascotas | Cliente | Adrián | **Lunes** |
| HU-08 | Ver el detalle de una mascota | Cliente | Adrián | **Lunes** |
| HU-09 | Editar una mascota | Cliente | Adrián | **Lunes** |
| HU-10 | Eliminar una mascota | Cliente | Adrián | **Lunes** |
| HU-11 | Gestionar todo desde el panel de administración | Administrador | Ambos | **Lunes** (ya viene con Django) |
| HU-15 | Confirmar mi inicio de sesión con un código por SMS (doble factor) | Cliente | Josselyn | **Lunes** |
| HU-12 | Iniciar sesión con Google | Visitante | Josselyn | Fase 2 |
| HU-13 | Verificar mi correo al registrarme | Cliente | Josselyn | Fase 2 |
| HU-14 | Recuperar mi contraseña por correo | Cliente | Josselyn | Fase 2 |
| HU-16 | Agendar una cita para mi mascota | Cliente | Por definir | Fase 3 |
| HU-17 | Ver y cancelar mis citas | Cliente | Por definir | Fase 3 |
| HU-18 | Ver la agenda del día | Veterinario | Por definir | Fase 3 |
| HU-19 | Registrar una consulta en el historial clínico | Veterinario | Por definir | Fase 3 |
| HU-20 | Ver el historial y las vacunas de mi mascota | Cliente | Por definir | Fase 3 |

---

## Entrega 1 (lunes)

### HU-01 · Ver la página de inicio
**Como** visitante **quiero** ver una página de inicio con la información de la veterinaria **para** saber qué ofrece y cómo crear una cuenta.

Criterios de aceptación:
- `/` carga sin iniciar sesión.
- Muestra botones *Iniciar sesión* y *Registrarse*.
- Si ya inicié sesión, la barra muestra mi nombre, *Mis mascotas* y *Cerrar sesión*.

### HU-02 · Registrarme
**Como** visitante **quiero** crear una cuenta con usuario, correo y contraseña **para** registrar a mis mascotas.

Criterios de aceptación:
- El formulario pide usuario, nombre, apellido, correo, teléfono celular (formato +593...), contraseña y confirmación.
- No permite un usuario o correo ya registrado (muestra el error en el formulario).
- Aplica las reglas de contraseña de Django (mínimo 8 caracteres, no solo números, no demasiado común).
- La contraseña se guarda cifrada (hash), nunca en texto plano.
- Al registrarme voy al inicio de sesión, que me pedirá el código por SMS.

### HU-03 · Iniciar sesión
**Como** visitante con cuenta **quiero** iniciar sesión con mi usuario y contraseña **para** entrar a la sección privada.

Criterios de aceptación:
- Con datos correctos paso al segundo paso (HU-15); todavía no tengo la sesión iniciada.
- Con datos incorrectos veo "Usuario o contraseña incorrectos" y no entro.
- El formulario lleva protección CSRF.

### HU-04 · Cerrar sesión
**Como** cliente **quiero** cerrar sesión **para** que nadie use mi cuenta en este equipo.

Criterios de aceptación:
- El botón *Cerrar sesión* envía un POST (Django 5 no acepta GET en logout).
- Después de salir vuelvo al inicio y ya no puedo abrir páginas privadas.

### HU-05 · Páginas privadas protegidas
**Como** dueño del sistema **quiero** que las URLs privadas no se puedan abrir sin iniciar sesión **para** proteger los datos de los clientes.

Criterios de aceptación:
- Abrir `/mascotas/` (o cualquier URL del CRUD) sin sesión redirige a `/login/?next=/mascotas/`.
- Escribir a mano la URL de editar o eliminar sin sesión también redirige al login.
- Hay pruebas automáticas que lo comprueban.

### HU-06 · Registrar una mascota
**Como** cliente **quiero** registrar a mi mascota con sus datos **para** tenerla en la veterinaria.

Criterios de aceptación:
- Campos: nombre, especie, raza, sexo, fecha de nacimiento, peso (kg) y foto opcional.
- Nombre y especie son obligatorios; el peso debe ser mayor que 0; la fecha no puede ser futura.
- La mascota queda asignada automáticamente a mí (no elijo el dueño en el formulario).
- Veo un mensaje de confirmación.

### HU-07 · Ver mis mascotas
**Como** cliente **quiero** ver la lista de mis mascotas **para** consultar y administrar sus datos.

Criterios de aceptación:
- Solo aparecen mis mascotas, nunca las de otros clientes.
- Si no tengo mascotas veo un mensaje y un botón para registrar la primera.

### HU-08 · Ver el detalle de una mascota
**Como** cliente **quiero** ver todos los datos de una de mis mascotas **para** revisarlos.

Criterios de aceptación:
- Muestra todos los campos y la edad calculada.
- Si intento abrir la mascota de otro cliente cambiando el número en la URL, obtengo 404.

### HU-09 · Editar una mascota
**Como** cliente **quiero** editar los datos de mi mascota **para** mantenerlos actualizados.

Criterios de aceptación:
- El formulario aparece con los datos actuales.
- Se aplican las mismas validaciones que al crear.
- No puedo editar mascotas de otro cliente (404).

### HU-10 · Eliminar una mascota
**Como** cliente **quiero** eliminar una mascota **para** quitar registros que ya no necesito.

Criterios de aceptación:
- Antes de borrar se muestra una página de confirmación.
- No puedo eliminar mascotas de otro cliente (404).

### HU-15 · Doble factor por SMS
**Como** cliente **quiero** que después de mi contraseña se me pida un código enviado a mi celular **para** que nadie entre a mi cuenta aunque conozca mi contraseña.

Criterios de aceptación:
- Tras usuario y contraseña correctos llega un SMS con un código de 6 dígitos (Twilio Verify).
- Con el código correcto inicio sesión y voy a *Mis mascotas* (o a la página que intentaba abrir).
- Con un código incorrecto o vencido veo un error y sigo sin sesión.
- Mientras no ingrese el código, las URLs protegidas siguen redirigiendo al login.
- Abrir `/verificar/` sin haber pasado por el login redirige al login.

### HU-11 · Panel de administración
**Como** administrador **quiero** ver y gestionar usuarios y mascotas desde `/admin/` **para** corregir datos cuando haga falta.

Criterios de aceptación:
- Usuario y Mascota están registrados en el admin, con búsqueda por nombre.

---

## Fase 2 (después del lunes)

- **HU-12 · Google:** Como visitante quiero entrar con mi cuenta de Google para no crear otra contraseña. *Si el correo ya existe, se vincula a la cuenta existente.*
- **HU-13 · Verificar correo:** Como cliente quiero recibir un correo de verificación al registrarme para confirmar que el correo es mío.
- **HU-14 · Recuperar contraseña:** Como cliente quiero recibir un enlace por correo para crear una contraseña nueva si la olvido. *El enlace caduca.*

## Fase 3 (alcance por confirmar)

- **HU-16 · Agendar cita:** Como cliente quiero agendar una cita para una de mis mascotas eligiendo fecha, hora y motivo. *No se permite una hora ya ocupada ni una fecha pasada.*
- **HU-17 · Mis citas:** Como cliente quiero ver mis citas próximas y cancelarlas.
- **HU-18 · Agenda:** Como veterinario quiero ver las citas del día.
- **HU-19 · Consulta:** Como veterinario quiero registrar diagnóstico, tratamiento y peso en el historial de la mascota.
- **HU-20 · Historial:** Como cliente quiero ver el historial clínico y las vacunas de mi mascota.

## Fuera de alcance (por ahora)
Pagos en línea, facturación, inventario de medicamentos, app móvil.
