from datetime import date

from django.db.models.deletion import ProtectedError
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .consultas import ocupacion
from .models import Espacio, Reserva
from .permissions import EsPersonalSoloLectura, EsPropietarioSoloLectura
from .serializers import EspacioSerializer, ReservaSerializer


class EspacioViewSet(viewsets.ModelViewSet):
    queryset = Espacio.objects.all()
    serializer_class = EspacioSerializer
    permission_classes = [EsPersonalSoloLectura]

    def get_queryset(self):
        queryset = super().get_queryset()
        tipo = self.request.query_params.get("tipo")
        activo = self.request.query_params.get("activo")

        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if activo == "true":
            queryset = queryset.filter(activo=True)
        elif activo == "false":
            queryset = queryset.filter(activo=False)

        return queryset

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "El espacio tiene reservas y no se puede borrar."},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=False, methods=["get"], url_path="ocupacion")
    def ocupacion(self, request):
        fecha_param = request.query_params.get("fecha")
        if not fecha_param:
            return Response(
                {"detail": "Falta el parámetro fecha (AAAA-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            raise serializers.ValidationError(
                {"fecha": "Formato de fecha no válido (AAAA-MM-DD)."}
            )

        if fecha.isoformat() != fecha_param:
            raise serializers.ValidationError(
                {"fecha": "Formato de fecha no válido (AAAA-MM-DD)."}
            )

        resultados = ocupacion(fecha)
        return Response(
            [
                {
                    "id": espacio.pk,
                    "nombre": espacio.nombre,
                    "reservas_confirmadas": espacio.reservas_confirmadas,
                }
                for espacio in resultados
            ]
        )


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.select_related("espacio", "usuario")
    serializer_class = ReservaSerializer
    permission_classes = [IsAuthenticated, EsPropietarioSoloLectura]

    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_param = self.request.query_params.get("fecha")
        espacio_param = self.request.query_params.get("espacio")
        estado = self.request.query_params.get("estado")

        if fecha_param is not None:
            try:
                fecha = date.fromisoformat(fecha_param)
            except ValueError:
                raise serializers.ValidationError(
                    {"fecha": "Formato de fecha no válido (AAAA-MM-DD)."}
                )
            if fecha.isoformat() != fecha_param:
                raise serializers.ValidationError(
                    {"fecha": "Formato de fecha no válido (AAAA-MM-DD)."}
                )
            queryset = queryset.filter(fecha=fecha)

        if espacio_param is not None:
            if not espacio_param.isdigit():
                raise serializers.ValidationError(
                    {"espacio": "El espacio debe ser un identificador numérico."}
                )
            queryset = queryset.filter(espacio_id=int(espacio_param))

        if estado:
            queryset = queryset.filter(estado=estado)

        return queryset

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
