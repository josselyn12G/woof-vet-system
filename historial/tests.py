from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from citas.models import EstadoCita
from citas.tests import crear_cita_pasada, crear_servicio, crear_veterinario
from mascotas.models import Especie
from mascotas.tests import crear_mascota, crear_usuario

from .models import Consulta, Prescripcion, Vacuna, VacunaAplicada
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
