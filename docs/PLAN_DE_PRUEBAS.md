# Plan de pruebas del Core

Casos mínimos del **§3.5 del Documento de Análisis** y la prueba que cubre cada uno. Todas están en `citas/tests.py`
y se corren con `python manage.py test`.

## Dónde corren

| Entorno | Base de datos | Qué corre |
|---|---|---|
| Desarrollo (computadora local) | SQLite (sin `DATABASE_URL`) o Neon | Toda la suite. Las reservas simultáneas se saltan en SQLite |
| Integración (GitHub Actions, en cada PR) | Job `test`: SQLite · job `test-postgres`: PostgreSQL 16 | Toda la suite en las dos bases. En PostgreSQL corren también las reservas simultáneas |
| Producción | PostgreSQL en Neon | Las migraciones se aplican al desplegar en Render (`build.sh`) |

¿Por qué PostgreSQL en CI? `select_for_update()` (el bloqueo que ordena dos reservas que llegan a la vez)
solo bloquea de verdad en PostgreSQL; SQLite lo ignora. Neon es PostgreSQL, así que esa prueba se corre ahí.

## Casos del §3.5

| Caso de prueba | Resultado esperado | Prueba |
|---|---|---|
| Espacios libres con el ejemplo del §2.1 | Se ofrecen 09:00, 10:30, 11:00, 11:30 y 12:30 | `EjemploDelDocumentoTests.test_espacios_libres_del_ejemplo` |
| Dos citas que solo se tocan (09:00-09:30 y 09:30-10:00) | No se consideran cruce | `EjemploDelDocumentoTests.test_dos_citas_que_solo_se_tocan_no_se_cruzan` |
| Cita cancelada dentro del bloque | Su turno vuelve a estar disponible | `EjemploDelDocumentoTests.test_la_cita_cancelada_deja_su_turno_libre` · `AgendaServiceTests.test_cancelar_libera_el_turno` |
| Turno que terminaría después de `hora_fin` | No se ofrece | `AgendaServiceTests.test_un_turno_que_no_cabe_completo_no_se_ofrece` |
| Dos reservas simultáneas del mismo turno | Solo se crea una cita; la otra recibe el aviso de horario ocupado | `ReservasSimultaneasTests.test_dos_clientes_reservan_el_mismo_turno_y_solo_uno_lo_consigue` (PostgreSQL) |
| Insertar a la fuerza una cita duplicada | La base la rechaza por la regla UNIQUE (veterinario, inicio) | `AgendaServiceTests.test_la_base_rechaza_dos_citas_activas_a_la_misma_hora` |
| Cancelar o reprogramar después de la hora de inicio | El sistema lo rechaza | `EjemploDelDocumentoTests.test_cancelar_una_cita_que_ya_empezo_se_rechaza` · `ReprogramarTests.test_una_cita_cancelada_o_que_ya_empezo_no_se_reprograma` |
| Abrir la cita de otro cliente | Responde 404 | `AgendarVistasTests.test_cancelar_la_cita_de_otro_responde_404` · `ReprogramarTests.test_la_cita_de_otro_cliente_responde_404` · `CalificarVistaTests.test_la_cita_de_otro_cliente_responde_404` |
| Calificar dos veces la misma cita | El sistema lo rechaza | `CalificarServiceTests.test_calificar_dos_veces_se_rechaza` · `CalificarVistaTests.test_calificar_dos_veces_se_rechaza` |

## Además del mínimo

| Regla | Prueba |
|---|---|
| Reprogramar es una sola operación: si falla, la cita conserva su hora (comentario del profesor) | `ReprogramarTests.test_si_el_turno_esta_ocupado_la_cita_se_queda_en_su_hora` · `ReprogramarTests.test_si_la_base_rechaza_el_cambio_se_deshace_todo` · `ReservasSimultaneasTests.test_reprogramar_y_agendar_al_mismo_turno_no_pierde_la_reserva` (PostgreSQL) |
| Anticipación mínima de 1 hora (RF-12) | `AnticipacionMinimaTests` (PR #53) |
| No quitar ni recortar un bloque con citas (RF-09) | `BloqueConCitasTests` |
| Solo veterinarios verificados (RF-05) | `VeterinarioVerificadoTests` |
| Ocupación del §2.5 (33,3 % y 45,8 %) | `IndicadoresTests` (PR #57) |
| Registrar la consulta solo desde una cita atendida (RF-20) | `historial/tests.py` · `RegistrarConsultaVistaTests` (PR #55 y #56) |
