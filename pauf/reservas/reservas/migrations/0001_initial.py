import django.conf
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Espacio",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=80, unique=True)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("aula", "Aula"),
                            ("laboratorio", "Laboratorio"),
                            ("salon", "Salón"),
                            ("pista", "Pista"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "aforo",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("aforo__gte", 1)),
                        name="espacio_aforo_minimo_uno",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Reserva",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("fecha", models.DateField()),
                ("hora_inicio", models.TimeField()),
                ("hora_fin", models.TimeField()),
                ("motivo", models.TextField()),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("confirmada", "Confirmada"),
                            ("cancelada", "Cancelada"),
                        ],
                        default="pendiente",
                        max_length=10,
                    ),
                ),
                ("creada", models.DateTimeField(auto_now_add=True)),
                (
                    "espacio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reservas",
                        to="reservas.espacio",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservas",
                        to=django.conf.settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("hora_fin__gt", models.F("hora_inicio"))
                        ),
                        name="reserva_fin_posterior_inicio",
                    ),
                ],
            },
        ),
    ]
