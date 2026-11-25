from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0003_quitar_unicidad_nombre_espacio"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="reserva",
            options={"ordering": ("fecha", "hora_inicio")},
        ),
    ]
