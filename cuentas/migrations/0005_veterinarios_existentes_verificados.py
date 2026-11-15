"""Los veterinarios que ya existían quedan verificados: así la demo sigue ofreciéndolos al agendar."""
from django.db import migrations


def verificar_existentes(apps, schema_editor):
    Usuario = apps.get_model('cuentas', 'Usuario')
    PerfilVeterinario = apps.get_model('cuentas', 'PerfilVeterinario')
    for veterinario in Usuario.objects.filter(rol='veterinario', perfil_veterinario__isnull=True):
        PerfilVeterinario.objects.create(usuario=veterinario, verificado=True)


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0004_perfil_veterinario'),
    ]

    operations = [
        # Al deshacerla no se borra nada: los perfiles se van con la migración 0004
        migrations.RunPython(verificar_existentes, migrations.RunPython.noop),
    ]
