# Historias de usuario — Woof

> **Borrador para revisar con Adrián.** Ajusten, quiten o agreguen. La columna *Entrega* dice si entra el lunes 5 de octubre (Entrega 1) o después.

Formato: **Como** `<rol>` **quiero** `<acción>` **para** `<beneficio>`, con criterios de aceptación verificables (lo que el profe puede probar en la demo).

Las historias marcadas con ➕ no estaban en la lista original del equipo: son sugerencias para completar el sistema. Revísenlas y quiten las que no quieran.

## Roles

| Rol | Quién es |
|---|---|
| Visitante | Persona sin cuenta o sin sesión iniciada |
| Cliente | Dueño de una o varias mascotas, con cuenta |
| Veterinario | Personal de la clínica que atiende mascotas (Fase 3) |
| Administrador | Gestiona usuarios, servicios y datos del sistema; ve los reportes |

## Resumen

### Entrega 1 · lunes 5 de octubre

| ID | Historia | Rol | Responsable |
|---|---|---|---|
| HU-01 | Ver la página de inicio | Visitante | Josselyn |
| HU-02 | Registrarme | Visitante | Josselyn |
| HU-03 | Iniciar sesión | Visitante | Josselyn |
| HU-04 | Cerrar sesión | Cliente | Josselyn |
| HU-05 | Páginas privadas protegidas | Visitante | Josselyn + Adrián |
| HU-15 | Confirmar mi inicio de sesión con un código por SMS (doble factor) | Cliente | Josselyn |
| HU-06 | Registrar una mascota | Cliente | Adrián |
| HU-07 | Ver mis mascotas | Cliente | Adrián |
| HU-08 | Ver el detalle de una mascota | Cliente | Adrián |
| HU-09 | Editar una mascota | Cliente | Adrián |
| HU-10 | Eliminar una mascota | Cliente | Adrián |
| HU-11 | Gestionar todo desde el panel de administración | Administrador | Ambos (ya viene con Django) |

### Fase 2 · Cuenta y acceso

| ID | Historia | Rol |
|---|---|---|
| HU-12 | Iniciar sesión con Google | Visitante |
| HU-13 | Verificar mi correo al registrarme | Cliente |
| HU-14 | Recuperar mi contraseña por correo | Cliente |
| HU-21 | Cambiar mi contraseña | Cliente / Veterinario |
| HU-22 | Editar mi información básica | Cliente / Veterinario |
| HU-23 | Aceptar los términos y la política de tratamiento de datos | Visitante |
| HU-24 ➕ | Eliminar mi cuenta y mis datos | Cliente |

### Fase 3 · Clínica

| ID | Historia | Rol |
|---|---|---|
| HU-25 ➕ | Gestionar el catálogo de servicios | Administrador |
| HU-26 | Definir mi horario disponible | Veterinario |
| HU-27 | Completar mi perfil profesional | Veterinario |
| HU-28 | Ver el perfil del veterinario que me atenderá | Cliente |
| HU-16 | Agendar una cita (servicio, fecha, hora y veterinario) | Cliente |
| HU-17 | Ver mis citas agendadas | Cliente |
| HU-29 | Reprogramar una cita | Cliente |
| HU-30 | Cancelar una cita | Cliente |
| HU-31 ➕ | Recibir un recordatorio de mi cita | Cliente |
| HU-18 | Ver mi agenda del día | Veterinario |
| HU-32 ➕ | Marcar una cita como atendida o como inasistencia | Veterinario |
| HU-19 | Registrar la consulta y enviar el tratamiento | Veterinario |
| HU-33 | Solicitar exámenes de laboratorio y cargar sus resultados | Veterinario |
| HU-34 | Ver los resultados de los exámenes de mi mascota | Cliente |
| HU-35 | Registrar vacunas en el carnet | Veterinario |
| HU-36 | Ver el carnet de vacunación de mi mascota | Cliente |
| HU-20 | Ver el historial clínico de mi mascota | Cliente |
| HU-37 ➕ | Recibir un recordatorio de la próxima vacuna | Cliente |
| HU-38 | Ver el plan de tratamiento con horarios y dosis | Cliente |
| HU-39 | Marcar cada toma en un checklist | Cliente |
| HU-40 | Recibir una notificación en cada toma | Cliente |
| HU-41 ➕ | Ver si el cliente cumple el tratamiento | Veterinario |
| HU-42 ➕ | Elegir por dónde recibo las notificaciones | Cliente |
| HU-43 | Gestionar las cuentas de veterinarios y clientes | Administrador |
| HU-44 | Ver un dashboard con ingresos, citas y métricas | Administrador |
| HU-45 ➕ | Calificar la atención recibida | Cliente |

### Fase 4 · Extensiones (alcance por confirmar con el profesor)

El **pago**, el **envío** y el **traslado** son **simulados**: el sistema recorre todo el flujo (pagar, enviar, trasladar) sin cobrar dinero real ni usar repartidores o conductores reales.

| ID | Historia | Rol |
|---|---|---|
| HU-46 | Ver el marketplace con filtros | Cliente |
| HU-47 | Comprar productos (carrito y pago simulado) | Cliente |
| HU-48 | Seguir el envío simulado de mi pedido | Cliente |
| HU-49 ➕ | Gestionar productos y precios | Administrador |
| HU-51 | Solicitar un traslado simulado eligiendo la ubicación en el mapa | Cliente |
| HU-52 | Seguir el estado del traslado simulado | Cliente |
| HU-54 | Conversar con un asistente de IA sobre los síntomas de mi mascota | Cliente |
| HU-55 | Que el asistente consulte los datos de mis mascotas | Cliente |
| HU-56 ➕ | Que el asistente detecte una urgencia y me derive | Cliente |

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

### HU-15 · Doble factor por SMS
**Como** cliente **quiero** que después de mi contraseña se me pida un código enviado a mi celular **para** que nadie entre a mi cuenta aunque conozca mi contraseña.

Criterios de aceptación:
- Tras usuario y contraseña correctos llega un SMS con un código de 6 dígitos (Twilio Verify).
- Con el código correcto inicio sesión y voy a *Mis mascotas* (o a la página que intentaba abrir).
- Con un código incorrecto o vencido veo un error y sigo sin sesión.
- Mientras no ingrese el código, las URLs protegidas siguen redirigiendo al login.
- Abrir `/verificar/` sin haber pasado por el login redirige al login.

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

### HU-11 · Panel de administración
**Como** administrador **quiero** ver y gestionar usuarios y mascotas desde `/admin/` **para** corregir datos cuando haga falta.

Criterios de aceptación:
- Usuario y Mascota están registrados en el admin, con búsqueda por nombre.

---

## Fase 2 · Cuenta y acceso

### HU-12 · Iniciar sesión con Google
**Como** visitante **quiero** entrar con mi cuenta de Google **para** no crear otra contraseña.
- Si el correo ya existe, se vincula a la cuenta existente.

### HU-13 · Verificar mi correo
**Como** cliente **quiero** recibir un correo de verificación al registrarme **para** confirmar que el correo es mío.

### HU-14 · Recuperar mi contraseña
**Como** cliente **quiero** recibir un enlace por correo **para** crear una contraseña nueva si la olvido.
- El enlace caduca y solo sirve una vez.

### HU-21 · Cambiar mi contraseña
**Como** usuario con sesión **quiero** cambiar mi contraseña **para** mantener segura mi cuenta.
- Pide la contraseña actual y la nueva dos veces; aplica las mismas reglas que el registro.
- Después del cambio sigo con la sesión iniciada en este equipo.

### HU-22 · Editar mi información básica
**Como** usuario **quiero** actualizar mi nombre, correo, teléfono y sector **para** que la veterinaria tenga mis datos al día.
- Si cambio el teléfono, debo confirmarlo con un código por SMS antes de que se guarde (ahí llega el doble factor).
- No puedo usar un correo que ya tenga otra cuenta.

### HU-23 · Aceptar términos y política de datos
**Como** visitante **quiero** leer y aceptar los términos y la política de tratamiento de datos al registrarme **para** saber cómo se usan mis datos y los de mis mascotas.
- No puedo registrarme sin marcar la casilla de aceptación.
- Se guarda la fecha y la versión de los términos que acepté.
- Los términos se pueden leer en una página pública.
- Si los términos cambian, al iniciar sesión se me pide aceptarlos de nuevo.

### HU-24 ➕ · Eliminar mi cuenta y mis datos
**Como** cliente **quiero** eliminar mi cuenta **para** ejercer mi derecho sobre mis datos personales (Ley Orgánica de Protección de Datos Personales de Ecuador).
- Pide confirmación y la contraseña.
- Se eliminan o anonimizan mis datos personales; los registros clínicos que la clínica deba conservar quedan sin datos que me identifiquen.

---

## Fase 3 · Clínica

### Servicios y horarios

#### HU-25 ➕ · Catálogo de servicios
**Como** administrador **quiero** crear los servicios que ofrece la clínica (consulta general, vacunación, desparasitación, laboratorio, peluquería, cirugía) con su duración y precio **para** que los clientes elijan qué necesitan.
- Cada servicio indica qué veterinarios pueden atenderlo.
- Un servicio desactivado ya no aparece al agendar, pero las citas pasadas lo conservan.

#### HU-26 · Mi horario disponible
**Como** veterinario **quiero** definir los días y horas en que atiendo **para** que el sistema solo ofrezca esos espacios a los clientes.
- Cargo los días concretos y las horas en que atiendo (por ejemplo, lunes 12 de octubre de 9:00 a 13:00). Si un día no atiendo, simplemente no lo cargo.
- Puedo copiar el horario de la semana anterior para no cargarlo todo de nuevo.
- No puedo quitar un horario que ya tiene citas reservadas sin cancelarlas antes.

#### HU-27 · Mi perfil profesional
**Como** veterinario **quiero** completar mi perfil con foto, especialidad, estudios, experiencia y una descripción **para** que los clientes confíen en quien los atiende.
- El administrador verifica el perfil antes de que el veterinario pueda recibir citas (ver HU-43).

#### HU-28 · Ver al veterinario
**Como** cliente **quiero** ver el perfil del veterinario que me atenderá **para** saber quién es y su especialidad.
- Al agendar puedo abrir el perfil de cada veterinario disponible.
- Muestra su calificación promedio (HU-45).

### Citas

#### HU-16 · Agendar una cita
**Como** cliente **quiero** agendar una cita eligiendo la mascota, el tipo de servicio, el veterinario, la fecha y la hora **para** que atiendan a mi mascota.
- Solo se ofrecen horas libres dentro del horario del veterinario (HU-26) y según la duración del servicio.
- Un horario reservado deja de aparecer para los demás clientes. Si dos clientes confirman el mismo horario al mismo tiempo, solo uno lo consigue; el otro ve un aviso para elegir otra hora.
- No se puede agendar en una fecha u hora pasada.
- Al confirmar veo el resumen (servicio, veterinario, fecha, hora y precio) y recibo una confirmación.

#### HU-17 · Ver mis citas
**Como** cliente **quiero** ver mis citas próximas y pasadas **para** organizarme.
- Las próximas aparecen primero, con su estado (pendiente, confirmada, atendida, cancelada).

#### HU-29 · Reprogramar una cita
**Como** cliente **quiero** cambiar la fecha u hora de mi cita **para** adaptarla si me surge un imprevisto.
- Solo con al menos 24 horas de anticipación (regla a confirmar).
- El horario anterior queda libre para otros clientes.

#### HU-30 · Cancelar una cita
**Como** cliente **quiero** cancelar una cita **para** liberar el espacio si ya no puedo ir.
- Solo puedo cancelar una cita *pendiente* o *confirmada*, antes de su hora de inicio; una cita ya atendida no se cancela.
- La cita no se borra: queda con estado *cancelada*, para conservar el historial, y no genera consulta.
- El horario vuelve a quedar libre para otros clientes.
- El veterinario ve la cancelación en su agenda.

#### HU-31 ➕ · Recordatorio de cita
**Como** cliente **quiero** recibir un recordatorio el día anterior a mi cita **para** no olvidarla.

#### HU-18 · Agenda del día
**Como** veterinario **quiero** ver mis citas del día y de la semana **para** organizar mi trabajo.
- Desde cada cita puedo abrir la ficha y el historial de la mascota.

#### HU-32 ➕ · Cerrar una cita
**Como** veterinario **quiero** marcar una cita como *atendida* o *no asistió* **para** llevar el control de la agenda.
- Solo una cita *atendida* permite registrar la consulta (HU-19). Una cita *no asistió* queda registrada para el dashboard, sin consulta.

### Historia clínica

#### HU-19 · Registrar la consulta y enviar el tratamiento
**Como** veterinario **quiero** registrar el motivo, el diagnóstico, el peso y el tratamiento después de una consulta **para** que quede en el historial y el cliente reciba las indicaciones.
- El tratamiento indica cada medicamento con dosis, frecuencia (cada cuántas horas) y duración (cuántos días).
- Al guardar, el cliente recibe una notificación y el tratamiento aparece en su plan (HU-38).

#### HU-33 · Exámenes de laboratorio
**Como** veterinario **quiero** solicitar exámenes de laboratorio durante la consulta y luego cargar sus resultados **para** completar el diagnóstico.
- Los resultados se cargan como texto o archivo PDF/imagen.
- El cliente recibe una notificación cuando los resultados están listos.

#### HU-34 · Ver resultados de exámenes
**Como** cliente **quiero** ver y descargar los resultados de los exámenes de mi mascota **para** tenerlos a mano.
- Solo veo los exámenes de mis mascotas.

#### HU-35 · Registrar vacunas
**Como** veterinario **quiero** registrar en el carnet la vacuna aplicada, el lote, la fecha y la próxima dosis **para** llevar el control de vacunación.

#### HU-36 · Ver el carnet de vacunación
**Como** cliente **quiero** ver el carnet de vacunación de mi mascota **para** saber qué vacunas tiene y cuándo toca la siguiente.
- Se puede descargar en PDF (útil para viajes o guarderías).

#### HU-20 · Ver el historial clínico
**Como** cliente **quiero** ver todas las consultas, diagnósticos y tratamientos de mi mascota **para** conocer su salud.

#### HU-37 ➕ · Recordatorio de vacuna
**Como** cliente **quiero** recibir un aviso unos días antes de la próxima dosis **para** agendar la cita a tiempo.

### Seguimiento de tratamientos

#### HU-38 · Plan de tratamiento
**Como** cliente **quiero** ver el plan de tratamiento de mi mascota con cada medicamento, la dosis y las horas exactas de cada toma **para** dárselo correctamente.
- El sistema calcula las tomas a partir de la frecuencia y la duración (por ejemplo, cada 8 horas durante 5 días = 15 tomas) desde la hora de inicio que yo elija.

#### HU-39 · Checklist de tomas
**Como** cliente **quiero** marcar cada toma como dada **para** no saltarme ni repetir dosis.
- Veo el avance (por ejemplo, 9 de 15 tomas) y qué tomas están atrasadas.

#### HU-40 · Notificación de cada toma
**Como** cliente **quiero** recibir una notificación a la hora de cada toma **para** no olvidarla.
- Puedo pausar las notificaciones de un tratamiento.

#### HU-41 ➕ · Cumplimiento del tratamiento
**Como** veterinario **quiero** ver qué tomas marcó el cliente **para** evaluar si el tratamiento se cumplió antes del control.

#### HU-42 ➕ · Preferencias de notificación
**Como** cliente **quiero** elegir si recibo los avisos por SMS, correo o dentro de la aplicación **para** recibirlos donde los voy a ver.

### Administración

#### HU-43 · Gestionar cuentas
**Como** administrador **quiero** crear, activar, desactivar y verificar las cuentas de veterinarios y clientes **para** controlar quién usa el sistema.
- Un veterinario nuevo queda *pendiente de verificación* hasta que el administrador revise su título profesional.
- Una cuenta desactivada no puede iniciar sesión, pero sus datos se conservan.

#### HU-44 · Dashboard
**Como** administrador **quiero** ver un panel con ingresos, citas atendidas, canceladas e inasistencias, servicios más pedidos y clientes nuevos **para** tomar decisiones.
- Se puede filtrar por rango de fechas y por veterinario.

#### HU-45 ➕ · Calificar la atención
**Como** cliente **quiero** calificar de 1 a 5 estrellas y comentar la atención después de una cita **para** ayudar a otros clientes y a la clínica a mejorar.
- Solo puedo calificar citas atendidas, una vez por cita.

---

## Fase 4 · Extensiones (alcance por confirmar con el profesor)

### Marketplace

#### HU-46 · Ver el marketplace
**Como** cliente **quiero** ver los productos de la clínica (comida, medicamentos, accesorios) con filtros por categoría y rango de precio, y un buscador por nombre **para** encontrar lo que necesito.

#### HU-47 · Comprar (pago simulado)
**Como** cliente **quiero** agregar productos a un carrito y pagarlos **para** comprar desde casa.
- El pago es **simulado**: un formulario de tarjeta de prueba que no cobra dinero real.
- Con la tarjeta de prueba de éxito (por ejemplo, `4242 4242 4242 4242`) el pago se aprueba; con la de rechazo (por ejemplo, `4000 0000 0000 0002`) se rechaza y el pedido queda sin pagar.
- La página indica claramente que es un pago de prueba.
- El sistema nunca guarda el número completo de la tarjeta, ni siquiera en la simulación: solo los últimos 4 dígitos.

#### HU-48 · Envío simulado
**Como** cliente **quiero** ver en qué estado está mi pedido (preparando, en camino, entregado) **para** saber cuándo llega.
- El envío es **simulado**: no hay repartidor. El estado avanza solo con el tiempo (por ejemplo, *preparando* → *en camino* a los 2 minutos → *entregado* a los 5 minutos).
- Al comprar escribo la dirección de entrega, y veo la fecha estimada de entrega.
- Recibo una notificación en cada cambio de estado.

#### HU-49 ➕ · Gestionar productos
**Como** administrador **quiero** crear y editar productos (categoría, nombre, descripción, precio y foto) **para** mantener el catálogo al día.
- Un producto que ya no se vende se desactiva en lugar de borrarse, para no perder los pedidos anteriores.

### Traslado de mascotas (simulado)

No hay conductores reales: el sistema simula el servicio de principio a fin.

#### HU-51 · Solicitar traslado
**Como** cliente **quiero** solicitar que recojan a mi mascota en casa y la lleven a la veterinaria (y de regreso) **para** atenderla aunque no tenga cómo transportarla.
- Elijo el punto de recogida en un mapa de Google o buscando la dirección; el destino es la veterinaria.
- Puedo pedirlo al agendar una cita o por separado, eligiendo ida, vuelta o ida y vuelta, y la hora de recogida.
- Antes de confirmar veo la distancia, el tiempo estimado y el costo: la distancia y el tiempo se obtienen de Google Maps y el costo se calcula con una tarifa simulada (por ejemplo, $2,00 base + $0,50 por km).

#### HU-52 · Seguir el traslado
**Como** cliente **quiero** ver el estado de mi traslado (confirmado, en camino, recogida, entregada) **para** estar tranquilo.
- El estado avanza solo según la hora de recogida, como si hubiera un conductor.
- Puedo cancelarlo mientras no esté *en camino*.

### Asistente de IA

#### HU-54 · Consultar síntomas
**Como** cliente **quiero** describir los síntomas de mi mascota a un asistente de IA **para** recibir una orientación inicial.
- Cada respuesta aclara que es una orientación y no reemplaza la consulta veterinaria.
- Al final sugiere agendar una cita si corresponde.

#### HU-55 · Contexto de mi mascota
**Como** cliente **quiero** que el asistente conozca la especie, edad, peso, vacunas y tratamientos de mi mascota **para** que su orientación sea más precisa.
- El asistente solo puede consultar los datos de **mis** mascotas, nunca los de otros clientes.
- Puedo ver qué datos usó en la respuesta.

#### HU-56 ➕ · Detectar urgencias
**Como** cliente **quiero** que el asistente reconozca señales de emergencia (envenenamiento, dificultad para respirar, convulsiones, sangrado abundante) **para** que me indique ir de inmediato a una veterinaria en lugar de seguir conversando.

---

## Fuera de alcance (por ahora)
Pagos con dinero real, repartidores y conductores reales (envíos y traslados son simulados), app móvil nativa, facturación electrónica, telemedicina por videollamada y pagos de veterinarios (nómina).
