from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse


class Espacio(models.Model):
    class Tipo(models.TextChoices):
        AULA = "aula", "Aula"
        LABORATORIO = "laboratorio", "Laboratorio"
        SALON = "salon", "Salón"
        PISTA = "pista", "Pista"

    nombre = models.CharField(max_length=80)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    aforo = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(aforo__gte=1),
                name="espacio_aforo_minimo_uno",
            ),
        ]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("reservas:detalle", kwargs={"pk": self.pk})


class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADA = "confirmada", "Confirmada"
        CANCELADA = "cancelada", "Cancelada"

    espacio = models.ForeignKey(
        Espacio,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservas",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    motivo = models.TextField()
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("fecha", "hora_inicio")
        constraints = [
            models.CheckConstraint(
                condition=Q(hora_fin__gt=F("hora_inicio")),
                name="reserva_fin_posterior_inicio",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            errors["hora_fin"] = "La hora de fin debe ser posterior a la hora de inicio."

        espacio_activo = None
        if self.espacio_id:
            espacio_activo = Espacio.objects.filter(pk=self.espacio_id).values_list(
                "activo", flat=True
            ).first()
            if espacio_activo is False:
                errors["espacio"] = "No se puede reservar un espacio inactivo."

        if (
            self.espacio_id
            and self.fecha
            and self.hora_inicio
            and self.hora_fin
            and self.estado != self.Estado.CANCELADA
            and self.hora_fin > self.hora_inicio
            and espacio_activo is True
        ):
            solapa = (
                Reserva.objects.filter(
                    espacio_id=self.espacio_id,
                    fecha=self.fecha,
                    hora_inicio__lt=self.hora_fin,
                    hora_fin__gt=self.hora_inicio,
                )
                .exclude(estado=self.Estado.CANCELADA)
                .exclude(pk=self.pk)
                .exists()
            )
            if solapa:
                errors["__all__"] = "El espacio ya tiene una reserva en ese horario."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.espacio} - {self.fecha} ({self.hora_inicio}-{self.hora_fin})"
