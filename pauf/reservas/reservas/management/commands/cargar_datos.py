import os
from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reservas.models import Espacio, Reserva


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("RESERVAS_DEFAULT_PASSWORD")
        if not password:
            raise CommandError(
                "Define la variable de entorno RESERVAS_DEFAULT_PASSWORD."
            )

        Reserva.objects.all().delete()

        usuarios = {}
        User = get_user_model()
        for username, is_staff in (
            ("profe1", False),
            ("profe2", False),
            ("conserje", True),
        ):
            usuario, _ = User.objects.get_or_create(
                username=username,
                defaults={"is_staff": is_staff, "is_active": True},
            )
            usuario.is_staff = is_staff
            usuario.is_active = True
            usuario.set_password(password)
            usuario.save(update_fields=["password", "is_staff", "is_active"])
            usuarios[username] = usuario

        espacios = {}
        for nombre, tipo, aforo, activo in (
            ("Aula 12", "aula", 30, True),
            ("Laboratorio de Física", "laboratorio", 24, True),
            ("Salón de actos", "salon", 200, True),
            ("Pista polideportiva", "pista", 60, True),
            ("Aula 3", "aula", 25, False),
        ):
            espacio, _ = Espacio.objects.update_or_create(
                nombre=nombre,
                defaults={"tipo": tipo, "aforo": aforo, "activo": activo},
            )
            espacios[nombre] = espacio

        reservas = (
            (
                "Aula 12",
                date(2027, 5, 20),
                time(9, 0),
                time(10, 0),
                "profe1",
                "confirmada",
                "Examen de Matemáticas",
            ),
            (
                "Aula 12",
                date(2027, 5, 20),
                time(10, 0),
                time(11, 0),
                "profe2",
                "confirmada",
                "Tutoría de 2.º DAW",
            ),
            (
                "Salón de actos",
                date(2027, 5, 20),
                time(12, 0),
                time(14, 0),
                "profe1",
                "pendiente",
                "Charla de orientación",
            ),
            (
                "Laboratorio de Física",
                date(2027, 5, 24),
                time(8, 30),
                time(10, 20),
                "profe2",
                "confirmada",
                "Práctica de óptica",
            ),
            (
                "Pista polideportiva",
                date(2027, 5, 24),
                time(11, 15),
                time(12, 10),
                "profe1",
                "cancelada",
                "Torneo de recreo",
            ),
            (
                "Aula 12",
                date(2027, 5, 24),
                time(9, 0),
                time(10, 0),
                "profe1",
                "pendiente",
                "Recuperación",
            ),
        )
        for (
            nombre_espacio,
            fecha,
            hora_inicio,
            hora_fin,
            username,
            estado,
            motivo,
        ) in reservas:
            Reserva.objects.create(
                espacio=espacios[nombre_espacio],
                fecha=fecha,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                usuario=usuarios[username],
                estado=estado,
                motivo=motivo,
            )

        self.stdout.write("Cargados 5 espacios y 6 reservas")
