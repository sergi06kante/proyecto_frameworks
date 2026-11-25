from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0002_espacios_iniciales"),
    ]

    operations = [
        migrations.AlterField(
            model_name="espacio",
            name="nombre",
            field=models.CharField(max_length=80),
        ),
    ]
