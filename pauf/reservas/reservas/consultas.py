from django.db.models import Count, Q

from .models import Espacio, Reserva


def ocupacion(fecha):
    return (
        Espacio.objects.filter(activo=True)
        .annotate(
            reservas_confirmadas=Count(
                "reservas",
                filter=Q(
                    reservas__estado=Reserva.Estado.CONFIRMADA,
                    reservas__fecha=fecha,
                ),
            )
        )
        .order_by("-reservas_confirmadas", "nombre")
    )
