import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def mover_tipo_de_contenido(apps, schema_editor):
    """Los permisos (view_notificacion...) apuntan al ContentType del modelo: se pasa de citas a notificaciones."""
    ContentType = apps.get_model('contenttypes', 'ContentType')
    if not ContentType.objects.filter(app_label='notificaciones', model='notificacion').exists():
        ContentType.objects.filter(app_label='citas', model='notificacion').update(app_label='notificaciones')


def devolver_tipo_de_contenido(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    if not ContentType.objects.filter(app_label='citas', model='notificacion').exists():
        ContentType.objects.filter(app_label='notificaciones', model='notificacion').update(app_label='citas')


class Migration(migrations.Migration):
    """
    Notificacion llega desde la app citas sin perder ningún aviso.

    1. SeparateDatabaseAndState: Django pasa a creer que el modelo es de notificaciones, pero en la base no se
       crea nada: sigue usando la tabla citas_notificacion (db_table), con todas sus filas.
    2. Los permisos del modelo se mueven a la app nueva (ContentType).
    3. 0002 renombra la tabla a notificaciones_notificacion.
    """

    initial = True

    dependencies = [
        ('citas', '0007_notificacion_pasa_a_su_app'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('historial', '0003_seguimiento_del_tratamiento'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Notificacion',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('tipo', models.CharField(choices=[('agendada', 'Cita agendada'), ('reprogramada', 'Cita reprogramada'), ('cancelada', 'Cita cancelada'), ('recordatorio', 'Recordatorio de cita'), ('vacuna', 'Recordatorio de vacuna')], max_length=15)),
                        ('mensaje', models.TextField()),
                        ('creado', models.DateTimeField(auto_now_add=True)),
                        ('leida', models.BooleanField(default=False)),
                        ('correo_enviado', models.BooleanField(default=False)),
                        ('intentos_correo', models.PositiveSmallIntegerField(default=0)),
                        ('cita', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones', to='citas.cita')),
                        ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones', to=settings.AUTH_USER_MODEL)),
                        ('vacuna_aplicada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones', to='historial.vacunaaplicada')),
                    ],
                    options={
                        'verbose_name': 'notificación',
                        'verbose_name_plural': 'notificaciones',
                        'db_table': 'citas_notificacion',
                        'ordering': ['-creado'],
                        'indexes': [models.Index(fields=['usuario', 'leida'], name='notificacion_usuario_leida')],
                        'constraints': [
                            models.UniqueConstraint(condition=models.Q(('tipo', 'recordatorio')), fields=('cita', 'usuario'), name='notificacion_un_recordatorio_por_cita'),
                            models.UniqueConstraint(condition=models.Q(('tipo', 'vacuna')), fields=('vacuna_aplicada', 'usuario'), name='notificacion_un_recordatorio_por_vacuna'),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(mover_tipo_de_contenido, devolver_tipo_de_contenido),
    ]
