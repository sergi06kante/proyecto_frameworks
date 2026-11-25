from django.db import migrations


def crear_espacios_iniciales(apps, schema_editor):
    Espacio = apps.get_model("reservas", "Espacio")
    espacios = [
        ("Aula 12", "aula", 30),
        ("Laboratorio de Física", "laboratorio", 24),
        ("Salón de actos", "salon", 200),
    ]
    for nombre, tipo, aforo in espacios:
        Espacio.objects.get_or_create(
            nombre=nombre,
            defaults={"tipo": tipo, "aforo": aforo, "activo": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_espacios_iniciales, migrations.RunPython.noop),
    ]
