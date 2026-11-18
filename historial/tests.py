from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from citas.models import EstadoCita
from citas.tests import crear_cita_pasada, crear_servicio, crear_veterinario
from cuentas.models import Roles
from mascotas.models import Especie
from mascotas.tests import crear_mascota, crear_usuario

from .models import Consulta, Prescripcion, TomaDia, Vacuna, VacunaAplicada
from .services import HistorialService


class HistorialBaseTests(TestCase):
    """Milo (perro de Ana) tuvo una consulta general con la Dra. Sofía ayer, ya atendida."""

    def setUp(self):
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        self.cliente = crear_usuario('ana')
        self.milo = crear_mascota(self.cliente, nombre='Milo')
        self.cita = crear_cita_pasada(self.milo, self.veterinario, self.servicio, dias=1)

    def consulta(self, cita=None, **datos):
        cita = cita or self.cita
        valores = {'cita': cita, 'mascota': cita.mascota, 'veterinario': cita.veterinario, 'fecha': cita.inicio,
                   'motivo': 'Tos desde hace 3 días', 'diagnostico': 'Traqueobronquitis leve.'}
        valores.update(datos)
        return Consulta(**valores)

    def rabia_perro(self):
        return Vacuna.objects.get(nombre='Rabia', especie__codigo='perro')


class ConsultaModelTests(HistorialBaseTests):
    def test_se_registra_la_consulta_de_una_cita_atendida(self):
        consulta = self.consulta()
        consulta.full_clean()
        consulta.save()
        self.assertEqual(self.cita.consulta, consulta)

    def test_una_cita_que_no_esta_atendida_no_tiene_consulta(self):
        for estado in (EstadoCita.CONFIRMADA, EstadoCita.NO_ASISTIO, EstadoCita.CANCELADA):
            with self.subTest(estado=estado):
                self.cita.estado = estado
                with self.assertRaisesMessage(ValidationError, 'cita atendida'):
                    self.consulta().full_clean()

    def test_una_cita_no_tiene_dos_consultas(self):
        self.consulta().save()
        with self.assertRaises(IntegrityError):
            self.consulta().save()

    def test_la_mascota_y_el_veterinario_son_los_de_la_cita(self):
        otro = crear_veterinario('mario')
        with self.assertRaisesMessage(ValidationError, 'Solo el veterinario de la cita'):
            self.consulta(veterinario=otro).full_clean()
        luna = crear_mascota(self.cliente, nombre='Luna')
        with self.assertRaisesMessage(ValidationError, 'La mascota debe ser la de la cita'):
            self.consulta(mascota=luna).full_clean()

    def test_sin_cita_vale_para_una_emergencia(self):
        consulta = self.consulta(cita=None)
        consulta.cita = None
        consulta.full_clean()

    def test_el_peso_debe_ser_positivo(self):
        with self.assertRaises(ValidationError):
            self.consulta(peso_kg=Decimal('0')).full_clean()
        with self.assertRaises(IntegrityError):
            self.consulta(peso_kg=Decimal('-1')).save()

    def test_una_cita_con_consulta_no_se_borra(self):
        self.consulta().save()
        with self.assertRaises(ProtectedError):
            self.cita.delete()


class PrescripcionTests(HistorialBaseTests):
    def setUp(self):
        super().setUp()
        self.consulta_milo = self.consulta()
        self.consulta_milo.save()

    def receta(self, **datos):
        valores = {'consulta': self.consulta_milo, 'medicamento': 'Amoxicilina 250 mg', 'dosis': '1 tableta',
                   'frecuencia_horas': 12, 'duracion_dias': 7}
        valores.update(datos)
        return Prescripcion(**valores)

    def test_calcula_cuantas_tomas_salen(self):
        # Como en el prototipo: cada 12 h por 7 días son 14 tomas; cada 8 h por 5 días, 15
        self.assertEqual(self.receta().tomas, 14)
        self.assertEqual(self.receta(frecuencia_horas=8, duracion_dias=5).tomas, 15)

    def test_frecuencia_y_duracion_deben_ser_positivas(self):
        for campo in ('frecuencia_horas', 'duracion_dias'):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                self.receta(**{campo: 0}).full_clean()

    def test_la_receta_queda_en_la_consulta(self):
        self.receta().save()
        self.receta(medicamento='Jarabe antitusivo', dosis='5 ml', frecuencia_horas=8, duracion_dias=5).save()
        self.assertEqual([p.medicamento for p in self.consulta_milo.prescripciones.all()],
                         ['Amoxicilina 250 mg', 'Jarabe antitusivo'])


class VacunaTests(HistorialBaseTests):
    def aplicar(self, vacuna=None, **datos):
        valores = {'mascota': self.milo, 'vacuna': vacuna or self.rabia_perro(), 'veterinario': self.veterinario,
                   'fecha_aplicacion': timezone.localdate() - timedelta(days=10), 'lote': 'L-2026-11'}
        valores.update(datos)
        return VacunaAplicada(**valores)

    def test_la_migracion_carga_las_vacunas_comunes(self):
        self.assertTrue(Vacuna.objects.filter(nombre='Rabia', especie__codigo='perro').exists())
        self.assertTrue(Vacuna.objects.filter(nombre='Triple felina', especie__codigo='gato').exists())

    def test_la_proxima_dosis_se_calcula_con_el_refuerzo(self):
        aplicada = self.aplicar()
        aplicada.save()
        self.assertEqual(aplicada.proxima_dosis, aplicada.fecha_aplicacion + timedelta(days=365))

    def test_sin_refuerzo_no_hay_proxima_dosis(self):
        unica = Vacuna.objects.create(nombre='Dosis única')
        aplicada = self.aplicar(unica)
        aplicada.save()
        self.assertIsNone(aplicada.proxima_dosis)

    def test_una_proxima_dosis_escrita_a_mano_se_respeta(self):
        manual = timezone.localdate() + timedelta(days=30)
        aplicada = self.aplicar(proxima_dosis=manual)
        aplicada.save()
        self.assertEqual(aplicada.proxima_dosis, manual)

    def test_la_proxima_dosis_no_puede_ser_antes_de_la_aplicacion(self):
        with self.assertRaises(IntegrityError):
            self.aplicar(proxima_dosis=timezone.localdate() - timedelta(days=20)).save()

    def test_no_se_aplica_una_vacuna_de_otra_especie(self):
        triple = Vacuna.objects.get(nombre='Triple felina')
        with self.assertRaisesMessage(ValidationError, 'Esa vacuna es para Gato'):
            self.aplicar(triple).full_clean()

    def test_la_fecha_de_aplicacion_no_puede_ser_futura(self):
        with self.assertRaisesMessage(ValidationError, 'no puede ser futura'):
            self.aplicar(fecha_aplicacion=timezone.localdate() + timedelta(days=1)).full_clean()

    def test_el_nombre_no_se_repite_en_la_misma_especie(self):
        perro = Especie.objects.get(codigo='perro')
        with self.assertRaises(IntegrityError):
            Vacuna.objects.create(nombre='rabia', especie=perro)

    def test_una_vacuna_aplicada_no_se_borra_del_catalogo(self):
        self.aplicar().save()
        with self.assertRaises(ProtectedError):
            self.rabia_perro().delete()


class HistorialServiceTests(HistorialBaseTests):
    def test_la_historia_trae_las_consultas_de_la_mas_nueva_a_la_mas_vieja(self):
        vieja = crear_cita_pasada(self.milo, self.veterinario, self.servicio, dias=30)
        self.consulta(vieja, fecha=vieja.inicio).save()
        self.consulta().save()
        historia = HistorialService.de_la_mascota(self.milo)
        self.assertEqual([c.cita for c in historia['consultas']], [self.cita, vieja])

    def test_la_historia_trae_la_receta_y_las_vacunas(self):
        consulta = self.consulta()
        consulta.save()
        Prescripcion.objects.create(consulta=consulta, medicamento='Amoxicilina', dosis='1 tableta',
                                    frecuencia_horas=12, duracion_dias=7)
        VacunaAplicada.objects.create(mascota=self.milo, vacuna=self.rabia_perro(), veterinario=self.veterinario,
                                      consulta=consulta)
        historia = HistorialService.de_la_mascota(self.milo)
        self.assertEqual(len(historia['consultas'][0].prescripciones.all()), 1)
        self.assertEqual(len(historia['consultas'][0].vacunas_aplicadas.all()), 1)
        self.assertEqual(len(historia['vacunas']), 1)

    def test_no_mezcla_la_historia_de_otra_mascota(self):
        self.consulta().save()
        luna = crear_mascota(self.cliente, nombre='Luna')
        self.assertEqual(HistorialService.de_la_mascota(luna), {'consultas': [], 'vacunas': []})

    def test_vacunas_para_una_mascota_son_las_de_su_especie_y_las_generales(self):
        general = Vacuna.objects.create(nombre='Desparasitación preventiva')
        inactiva = Vacuna.objects.create(nombre='Antigua', especie=self.milo.especie, activa=False)
        vacunas = HistorialService.vacunas_para(self.milo)
        self.assertIn(self.rabia_perro(), vacunas)
        self.assertIn(general, vacunas)
        self.assertNotIn(Vacuna.objects.get(nombre='Triple felina'), vacunas)
        self.assertNotIn(inactiva, vacunas)

    def test_solo_una_cita_atendida_y_sin_consulta_permite_registrar(self):
        self.assertTrue(HistorialService.puede_registrar_consulta(self.cita))
        self.consulta().save()
        self.assertFalse(HistorialService.puede_registrar_consulta(self.cita))
        confirmada = crear_cita_pasada(self.milo, self.veterinario, self.servicio,
                                       estado=EstadoCita.CONFIRMADA, dias=3)
        self.assertFalse(HistorialService.puede_registrar_consulta(confirmada))


class RegistrarConsultaVistaTests(HistorialBaseTests):
    """RF-20: el veterinario registra la consulta, la receta y las vacunas desde una cita atendida suya."""

    def setUp(self):
        super().setUp()
        self.url = reverse('historial:consulta', args=[self.cita.pk])
        self.client.force_login(self.veterinario)

    def datos(self, recetas=(), vacunas=(), **consulta):
        """El POST como lo manda el navegador: la consulta y los dos formsets con su formulario de gestión."""
        valores = {'motivo': 'Tos desde hace 3 días', 'peso_kg': '12.60', 'diagnostico': 'Traqueobronquitis leve.',
                   'indicaciones': 'Reposo 5 días.'}
        valores.update(consulta)
        for prefijo, filas in (('recetas', recetas), ('vacunas', vacunas)):
            valores.update({f'{prefijo}-TOTAL_FORMS': str(len(filas)), f'{prefijo}-INITIAL_FORMS': '0',
                            f'{prefijo}-MIN_NUM_FORMS': '0', f'{prefijo}-MAX_NUM_FORMS': '1000'})
            for i, fila in enumerate(filas):
                valores.update({f'{prefijo}-{i}-{campo}': valor for campo, valor in fila.items()})
        return valores

    def receta(self, **datos):
        valores = {'medicamento': 'Amoxicilina 250 mg', 'dosis': '1 tableta', 'frecuencia_horas': '12',
                   'duracion_dias': '7'}
        valores.update(datos)
        return valores

    # ---------- Quién la abre ----------
    def test_el_veterinario_de_la_cita_ve_el_formulario(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Registrar consulta')
        self.assertContains(respuesta, 'Milo')
        self.assertContains(respuesta, 'Rabia')            # vacunas de perro
        self.assertNotContains(respuesta, 'Triple felina')  # y no las de gato

    def test_otro_veterinario_recibe_404(self):
        self.client.force_login(crear_veterinario('mario'))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_un_cliente_recibe_403(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_sin_sesion_va_al_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('cuentas:login')}?next={self.url}",
                             fetch_redirect_response=False)

    def test_una_cita_que_no_esta_atendida_vuelve_a_la_agenda(self):
        self.cita.estado = EstadoCita.CONFIRMADA
        self.cita.save()
        for respuesta in (self.client.get(self.url), self.client.post(self.url, self.datos())):
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn(reverse('citas:agenda'), respuesta.url)
        self.assertFalse(Consulta.objects.exists())

    # ---------- Guardar ----------
    def test_guarda_la_consulta_con_su_receta_y_sus_vacunas(self):
        respuesta = self.client.post(self.url, self.datos(
            recetas=[self.receta(), self.receta(medicamento='Jarabe', dosis='5 ml', frecuencia_horas='8',
                                                duracion_dias='5')],
            vacunas=[{'vacuna': self.rabia_perro().pk, 'lote': 'L-01'}],
        ))
        self.assertEqual(respuesta.status_code, 302)
        consulta = Consulta.objects.get(cita=self.cita)
        self.assertEqual((consulta.mascota, consulta.veterinario), (self.milo, self.veterinario))
        self.assertEqual(consulta.prescripciones.count(), 2)
        aplicada = consulta.vacunas_aplicadas.get()
        self.assertEqual((aplicada.mascota, aplicada.veterinario, aplicada.lote), (self.milo, self.veterinario, 'L-01'))
        self.assertEqual(aplicada.fecha_aplicacion, timezone.localtime(self.cita.inicio).date())
        self.assertIsNotNone(aplicada.proxima_dosis)

    def test_el_peso_de_la_consulta_pasa_a_la_mascota(self):
        self.client.post(self.url, self.datos())
        self.milo.refresh_from_db()
        self.assertEqual(self.milo.peso_kg, Decimal('12.60'))

    def test_las_filas_vacias_se_ignoran(self):
        self.client.post(self.url, self.datos(recetas=[{}], vacunas=[{}]))
        consulta = Consulta.objects.get(cita=self.cita)
        self.assertFalse(consulta.prescripciones.exists())
        self.assertFalse(consulta.vacunas_aplicadas.exists())

    def test_si_la_receta_tiene_un_error_no_se_guarda_nada(self):
        respuesta = self.client.post(self.url, self.datos(recetas=[self.receta(frecuencia_horas='0')]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'la consulta todavía no se guardó')
        self.assertFalse(Consulta.objects.exists())
        self.milo.refresh_from_db()
        self.assertIsNone(self.milo.peso_kg)

    def test_sin_diagnostico_no_se_guarda(self):
        respuesta = self.client.post(self.url, self.datos(diagnostico=''))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Consulta.objects.exists())

    def test_no_acepta_una_vacuna_de_otra_especie(self):
        triple = Vacuna.objects.get(nombre='Triple felina')
        respuesta = self.client.post(self.url, self.datos(vacunas=[{'vacuna': triple.pk}]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Consulta.objects.exists())

    def test_vuelve_a_la_agenda_del_dia_de_la_cita(self):
        respuesta = self.client.post(self.url, self.datos())
        fecha = timezone.localtime(self.cita.inicio).date()
        self.assertRedirects(respuesta, f"{reverse('citas:agenda')}?fecha={fecha.isoformat()}",
                             fetch_redirect_response=False)

    # ---------- Editar ----------
    def test_si_ya_tiene_consulta_se_edita_la_misma(self):
        self.client.post(self.url, self.datos(recetas=[self.receta()]))
        consulta = Consulta.objects.get()
        receta = consulta.prescripciones.get()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Editar consulta')
        self.assertContains(respuesta, 'Traqueobronquitis leve.')

        datos = self.datos(diagnostico='Bronquitis, mejorando.')
        datos.update({'recetas-TOTAL_FORMS': '1', 'recetas-INITIAL_FORMS': '1', 'recetas-0-id': receta.pk,
                      'recetas-0-consulta': consulta.pk, 'recetas-0-DELETE': 'on',
                      **{f'recetas-0-{campo}': valor for campo, valor in self.receta().items()}})
        self.client.post(self.url, datos)
        self.assertEqual(Consulta.objects.count(), 1)
        consulta.refresh_from_db()
        self.assertEqual(consulta.diagnostico, 'Bronquitis, mejorando.')
        self.assertFalse(consulta.prescripciones.exists())   # se quitó de la receta

    # ---------- La agenda ----------
    def test_la_agenda_muestra_registrar_y_luego_ver_consulta(self):
        agenda = reverse('citas:agenda') + f'?fecha={timezone.localtime(self.cita.inicio).date().isoformat()}'
        self.assertContains(self.client.get(agenda), 'Registrar consulta')
        self.client.post(self.url, self.datos())
        respuesta = self.client.get(agenda)
        self.assertContains(respuesta, 'Ver consulta')
        self.assertNotContains(respuesta, 'Registrar consulta')

    def test_una_cita_confirmada_no_muestra_el_boton(self):
        self.cita.estado = EstadoCita.CONFIRMADA
        self.cita.save()
        agenda = reverse('citas:agenda') + f'?fecha={timezone.localtime(self.cita.inicio).date().isoformat()}'
        self.assertNotContains(self.client.get(agenda), self.url)


class HistoriaClinicaVistaTests(HistorialBaseTests):
    """La historia clínica de solo lectura: el dueño ve la de su mascota, los veterinarios y la clínica la ven."""

    def setUp(self):
        super().setUp()
        consulta = self.consulta(peso_kg=Decimal('12.60'), indicaciones='Reposo 5 días.')
        consulta.save()
        Prescripcion.objects.create(consulta=consulta, medicamento='Amoxicilina 250 mg', dosis='1 tableta',
                                    frecuencia_horas=12, duracion_dias=7)
        VacunaAplicada.objects.create(mascota=self.milo, vacuna=self.rabia_perro(), consulta=consulta,
                                      veterinario=self.veterinario, fecha_aplicacion=timezone.localdate())
        self.url = reverse('mascotas:historial', args=[self.milo.pk])

    def test_el_cliente_ve_la_historia_de_su_mascota(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Traqueobronquitis leve.')
        self.assertContains(respuesta, 'Tos desde hace 3 días')
        self.assertContains(respuesta, 'Reposo 5 días.')
        self.assertContains(respuesta, 'Amoxicilina 250 mg')
        self.assertContains(respuesta, '14 tomas')
        self.assertContains(respuesta, 'Rabia')
        self.assertContains(respuesta, reverse('mascotas:detalle', args=[self.milo.pk]))   # volver a su mascota

    def test_el_cliente_recibe_404_con_la_mascota_de_otro(self):
        self.client.force_login(crear_usuario('carlos'))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_el_veterinario_ve_la_historia(self):
        # Cualquier veterinario, no solo el que la atendió: es el mismo alcance de Pacientes
        self.client.force_login(crear_veterinario('mario'))
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Traqueobronquitis leve.')
        self.assertContains(respuesta, reverse('citas:pacientes'))

    def test_el_administrador_y_el_superadministrador_la_ven(self):
        for rol in (Roles.ADMINISTRADOR, Roles.SUPERADMIN):
            with self.subTest(rol=rol):
                self.client.force_login(crear_usuario(f'gestion{rol}', rol=rol))
                respuesta = self.client.get(self.url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'Traqueobronquitis leve.')
                self.assertContains(respuesta, reverse('mascotas:gestion_detalle', args=[self.milo.pk]))

    def test_un_visitante_va_al_login(self):
        self.assertRedirects(self.client.get(self.url), f"{reverse('cuentas:login')}?next={self.url}",
                             fetch_redirect_response=False)

    def test_sin_consultas_muestra_el_estado_vacio(self):
        luna = crear_mascota(self.cliente, nombre='Luna')
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('mascotas:historial', args=[luna.pk]))
        self.assertContains(respuesta, 'Aún no hay consultas registradas')
        self.assertNotContains(respuesta, 'Traqueobronquitis leve.')   # no mezcla la de Milo

    def test_las_tres_entradas_enlazan_a_la_historia(self):
        """El detalle de la mascota (cliente), Pacientes (veterinario) y la gestión (administrador)."""
        entradas = (
            (self.cliente, reverse('mascotas:detalle', args=[self.milo.pk])),
            (self.veterinario, reverse('citas:pacientes')),
            (crear_usuario('laura', rol=Roles.ADMINISTRADOR), reverse('mascotas:gestion_detalle', args=[self.milo.pk])),
        )
        for usuario, pagina in entradas:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertContains(self.client.get(pagina), self.url)


class CatalogoVacunasTests(HistorialBaseTests):
    """El administrador crea, edita y desactiva las vacunas que el veterinario puede registrar."""

    def setUp(self):
        super().setUp()
        self.admin = crear_usuario('laura', rol=Roles.ADMINISTRADOR)
        self.client.force_login(self.admin)
        self.url = reverse('historial:vacunas')

    def datos(self, **cambios):
        valores = {'nombre': 'Parvovirus', 'especie': str(Especie.objects.get(codigo='perro').pk),
                   'refuerzo_cada_dias': '365', 'activa': 'on'}
        valores.update(cambios)
        return valores

    # ---------- Quién entra ----------
    def test_el_administrador_y_el_superadministrador_ven_el_catalogo(self):
        for usuario in (self.admin, crear_usuario('jefa', rol=Roles.SUPERADMIN)):
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                respuesta = self.client.get(self.url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'Rabia')   # de las vacunas que carga la migración

    def test_el_veterinario_y_el_cliente_reciben_403(self):
        for usuario in (self.veterinario, self.cliente):
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.get(reverse('historial:vacuna_crear')).status_code, 403)

    def test_un_visitante_va_al_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('cuentas:login')}?next={self.url}",
                             fetch_redirect_response=False)

    # ---------- Crear y editar ----------
    def test_crea_una_vacuna(self):
        respuesta = self.client.post(reverse('historial:vacuna_crear'), self.datos())
        self.assertRedirects(respuesta, self.url)
        vacuna = Vacuna.objects.get(nombre='Parvovirus')
        self.assertEqual(vacuna.especie.codigo, 'perro')
        self.assertEqual(vacuna.refuerzo_cada_dias, 365)
        self.assertTrue(vacuna.activa)

    def test_sin_especie_sirve_para_todas(self):
        self.client.post(reverse('historial:vacuna_crear'), self.datos(nombre='Vitamina', especie=''))
        self.assertIsNone(Vacuna.objects.get(nombre='Vitamina').especie)

    def test_no_repite_el_nombre_en_la_misma_especie(self):
        respuesta = self.client.post(reverse('historial:vacuna_crear'), self.datos(nombre='rabia'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe la vacuna rabia para Perro')
        self.assertEqual(Vacuna.objects.filter(nombre__iexact='rabia', especie__codigo='perro').count(), 1)

    def test_el_mismo_nombre_vale_para_otra_especie(self):
        conejo = Especie.objects.get(codigo='conejo')
        self.client.post(reverse('historial:vacuna_crear'), self.datos(nombre='Rabia', especie=str(conejo.pk)))
        self.assertTrue(Vacuna.objects.filter(nombre='Rabia', especie=conejo).exists())

    def test_edita_una_vacuna(self):
        rabia = self.rabia_perro()
        url = reverse('historial:vacuna_editar', args=[rabia.pk])
        respuesta = self.client.post(url, self.datos(nombre='Rabia', refuerzo_cada_dias='730'))
        self.assertRedirects(respuesta, self.url)
        rabia.refresh_from_db()
        self.assertEqual(rabia.refuerzo_cada_dias, 730)

    # ---------- Desactivar ----------
    def test_desactivar_y_volver_a_activar(self):
        rabia = self.rabia_perro()
        url = reverse('historial:vacuna_estado', args=[rabia.pk])
        self.assertEqual(self.client.get(url).status_code, 405)   # solo POST
        self.client.post(url)
        rabia.refresh_from_db()
        self.assertFalse(rabia.activa)
        self.client.post(url)
        rabia.refresh_from_db()
        self.assertTrue(rabia.activa)

    def test_una_vacuna_desactivada_no_se_ofrece_al_registrar(self):
        rabia = self.rabia_perro()
        self.client.post(reverse('historial:vacuna_estado', args=[rabia.pk]))
        self.assertNotIn(rabia, HistorialService.vacunas_para(self.milo))
        self.client.force_login(self.veterinario)
        respuesta = self.client.get(reverse('historial:consulta', args=[self.cita.pk]))
        self.assertNotIn(rabia, respuesta.context['vacunas'].forms[0].fields['vacuna'].queryset)

    def test_cuenta_cuantas_veces_se_aplico(self):
        rabia = self.rabia_perro()
        respuesta = self.client.get(self.url, {'q': 'Polivalente'})
        self.assertContains(respuesta, '0 veces')
        VacunaAplicada.objects.create(mascota=self.milo, vacuna=rabia, veterinario=self.veterinario,
                                      fecha_aplicacion=timezone.localdate())
        respuesta = self.client.get(self.url, {'q': 'Rabia'})
        self.assertContains(respuesta, '1 vez')
        self.assertNotContains(respuesta, 'vezes')

    def test_filtra_por_estado_y_busca(self):
        rabia = self.rabia_perro()
        self.client.post(reverse('historial:vacuna_estado', args=[rabia.pk]))
        inactivas = self.client.get(self.url, {'estado': 'inactivas'}).context['vacunas']
        self.assertEqual(list(inactivas), [rabia])
        buscadas = self.client.get(self.url, {'q': 'rabia'}).context['vacunas']
        self.assertTrue(all('rabia' in vacuna.nombre.lower() for vacuna in buscadas))


class ClienteConRecetasBase(HistorialBaseTests):
    """Milo con una consulta, una receta en curso (desde ayer), una terminada y la vacuna de rabia; Ana en sesión."""

    def setUp(self):
        super().setUp()
        self.consulta_milo = self.consulta(peso_kg=Decimal('12.50'))
        self.consulta_milo.save()
        ahora = timezone.now()
        self.en_curso = Prescripcion.objects.create(consulta=self.consulta_milo, medicamento='Amoxicilina 250 mg',
                                                    dosis='1 tableta', frecuencia_horas=12, duracion_dias=7,
                                                    fecha_inicio=ahora - timedelta(days=1))
        self.terminada = Prescripcion.objects.create(consulta=self.consulta_milo, medicamento='Jarabe antitusivo',
                                                     dosis='5 ml', frecuencia_horas=8, duracion_dias=3,
                                                     fecha_inicio=ahora - timedelta(days=10))
        VacunaAplicada.objects.create(mascota=self.milo, vacuna=self.rabia_perro(), veterinario=self.veterinario,
                                      consulta=self.consulta_milo, fecha_aplicacion=timezone.localdate() - timedelta(days=1))
        self.luna = crear_mascota(self.cliente, nombre='Luna', especie='gato')
        self.client.force_login(self.cliente)



class HistoriaDelClienteTests(ClienteConRecetasBase):
    """Menú del cliente: Historia clínica y Mis recetas por mascota; y la historia en PDF."""

    # ---------- Historia clínica ----------
    def test_la_historia_muestra_la_primera_mascota_y_sus_consultas(self):
        respuesta = self.client.get(reverse('historial:mi_historia'))
        self.assertEqual(respuesta.context['mascota'], self.luna)   # por nombre: Luna va antes que Milo
        respuesta = self.client.get(reverse('historial:mi_historia'), {'mascota': self.milo.pk})
        self.assertEqual(respuesta.context['mascota'], self.milo)
        self.assertContains(respuesta, 'Traqueobronquitis leve.')
        self.assertContains(respuesta, 'Rabia')
        self.assertContains(respuesta, reverse('mascotas:historial_pdf', args=[self.milo.pk]))

    def test_una_mascota_ajena_no_se_muestra(self):
        ajena = crear_mascota(crear_usuario('luis'), nombre='Toby')
        respuesta = self.client.get(reverse('historial:mi_historia'), {'mascota': ajena.pk})
        self.assertNotEqual(respuesta.context['mascota'], ajena)
        self.assertNotContains(respuesta, 'Toby')

    def test_sin_mascotas_explica_que_hacer(self):
        self.client.force_login(crear_usuario('nuevo'))
        self.assertContains(self.client.get(reverse('historial:mi_historia')), 'Todavía no registras mascotas')

    def test_solo_la_abre_el_cliente(self):
        self.client.force_login(self.veterinario)
        for url in ('historial:mi_historia', 'historial:mis_recetas'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(reverse(url)).status_code, 403)

    def test_el_menu_del_cliente_enlaza_las_dos_secciones(self):
        respuesta = self.client.get(reverse('citas:mis_citas'))
        self.assertContains(respuesta, reverse('historial:mi_historia'))
        self.assertContains(respuesta, reverse('historial:mis_recetas'))

    # ---------- Mis recetas ----------
    def test_mis_recetas_agrupadas_por_mascota_y_con_su_estado(self):
        respuesta = self.client.get(reverse('historial:mis_recetas'))
        ((mascota, recetas),) = respuesta.context['por_mascota']
        self.assertEqual(mascota, self.milo)
        estados = {receta.medicamento: receta.en_curso for receta in recetas}
        self.assertEqual(estados, {'Amoxicilina 250 mg': True, 'Jarabe antitusivo': False})
        self.assertEqual(respuesta.context['en_curso'], 1)
        self.assertContains(respuesta, 'En curso')
        self.assertContains(respuesta, 'Terminada')

    def test_mis_recetas_filtra_por_mascota(self):
        respuesta = self.client.get(reverse('historial:mis_recetas'), {'mascota': self.luna.pk})
        self.assertEqual(respuesta.context['por_mascota'], [])
        self.assertContains(respuesta, 'Luna no tiene recetas todavía')

    def test_no_muestra_recetas_de_otro_cliente(self):
        self.client.force_login(crear_usuario('luis'))
        self.assertEqual(self.client.get(reverse('historial:mis_recetas')).context['por_mascota'], [])

    # ---------- Tablero ----------
    def test_el_tablero_trae_el_peso_y_la_proxima_vacuna(self):
        datos = HistorialService.de_la_mascota(self.milo)
        tablero = HistorialService.tablero(self.milo, datos['consultas'])
        self.assertEqual([barra['peso'] for barra in tablero['barras_peso']], [Decimal('12.50')])
        self.assertEqual(tablero['proxima_vacuna']['linea'].vacuna.nombre, 'Rabia')
        self.assertEqual(tablero['proxima_vacuna']['dias'], 364)
        self.assertEqual((tablero['al_dia'], tablero['total_recetas'], tablero['recetas_en_curso']), (1, 2, 1))

    # ---------- PDF ----------
    def test_el_dueno_descarga_la_historia_en_pdf(self):
        respuesta = self.client.get(reverse('mascotas:historial_pdf', args=[self.milo.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="historia-clinica-milo-', respuesta['Content-Disposition'])
        self.assertTrue(respuesta.content.startswith(b'%PDF'))

    def test_el_veterinario_tambien_la_descarga(self):
        self.client.force_login(self.veterinario)
        self.assertEqual(self.client.get(reverse('mascotas:historial_pdf', args=[self.milo.pk])).status_code, 200)

    def test_el_pdf_de_una_mascota_ajena_responde_404(self):
        self.client.force_login(crear_usuario('luis'))
        self.assertEqual(self.client.get(reverse('mascotas:historial_pdf', args=[self.milo.pk])).status_code, 404)

    def test_un_diagnostico_con_simbolos_no_rompe_el_pdf(self):
        Consulta.objects.filter(pk=self.consulta_milo.pk).update(diagnostico='Fiebre < 39 °C & tos <b>leve</b>')
        self.assertTrue(self.client.get(reverse('mascotas:historial_pdf', args=[self.milo.pk])).content.startswith(b'%PDF'))



class SeguimientoDelTratamientoTests(ClienteConRecetasBase):
    """Un check por día del tratamiento: lo marca el dueño, nunca por adelantado y solo en sus recetas."""

    def marcar(self, dia, receta=None, **datos):
        receta = receta or self.en_curso
        return self.client.post(reverse('historial:marcar_dia', args=[receta.pk]),
                                {'dia': dia.isoformat(), **datos})

    def test_el_seguimiento_trae_los_dias_y_el_avance(self):
        seg = HistorialService.seguimiento(self.en_curso)
        self.assertEqual(len(seg['dias']), 7)
        self.assertEqual([d['estado'] for d in seg['dias'][:3]], ['sin_marcar', 'hoy', 'proximo'])
        self.assertEqual((seg['hechos'], seg['avance'], seg['tomas_por_dia']), (0, 0, 2))
        self.assertEqual(seg['tipo'], 'tableta')

    def test_marcar_hoy_suma_avance_y_se_ve_en_mis_recetas(self):
        hoy = timezone.localdate()
        respuesta = self.marcar(hoy, volver=reverse('historial:mis_recetas'))
        self.assertRedirects(respuesta, reverse('historial:mis_recetas') + f'#receta-{self.en_curso.pk}',
                             fetch_redirect_response=False)
        self.assertTrue(TomaDia.objects.filter(prescripcion=self.en_curso, dia=hoy).exists())
        pagina = self.client.get(reverse('historial:mis_recetas'))
        self.assertContains(pagina, '1 de 7')
        self.assertContains(pagina, 'Dosis dada')

    def test_marcar_dos_veces_lo_desmarca(self):
        hoy = timezone.localdate()
        self.marcar(hoy)
        self.marcar(hoy)
        self.assertFalse(TomaDia.objects.filter(prescripcion=self.en_curso).exists())

    def test_un_dia_que_no_llega_o_fuera_del_tratamiento_se_rechaza(self):
        for dia in (timezone.localdate() + timedelta(days=1), timezone.localdate() - timedelta(days=20)):
            with self.subTest(dia=dia):
                self.marcar(dia)
        self.assertFalse(TomaDia.objects.exists())

    def test_la_receta_de_otro_cliente_responde_404(self):
        self.client.force_login(crear_usuario('luis'))
        self.assertEqual(self.marcar(timezone.localdate()).status_code, 404)

    def test_solo_por_post(self):
        url = reverse('historial:marcar_dia', args=[self.en_curso.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_volver_a_otro_sitio_no_se_sigue(self):
        respuesta = self.marcar(timezone.localdate(), volver='https://otro-sitio.com/')
        self.assertTrue(respuesta.url.startswith(reverse('historial:mis_recetas')))

    def test_el_tipo_de_medicamento_decide_la_imagen(self):
        casos = {('Jarabe antitusivo', '5 ml'): 'jarabe', ('Gotas óticas', '4 gotas'): 'gotas',
                 ('Pomada', 'una capa'): 'crema', ('Amoxicilina', '1 tableta'): 'tableta'}
        for (medicamento, dosis), tipo in casos.items():
            with self.subTest(medicamento=medicamento):
                receta = Prescripcion(medicamento=medicamento, dosis=dosis, frecuencia_horas=8, duracion_dias=3)
                self.assertEqual(HistorialService.tipo_de_medicamento(receta)[0], tipo)
