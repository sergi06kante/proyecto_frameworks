import copy

from django.core.exceptions import (
    NON_FIELD_ERRORS,
    ValidationError as DjangoValidationError,
)
from rest_framework import serializers
from rest_framework.settings import api_settings

from .models import Espacio, Reserva


class EspacioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Espacio
        fields = ["id", "nombre", "tipo", "aforo", "activo"]


class ReservaSerializer(serializers.ModelSerializer):
    espacio_nombre = serializers.CharField(
        source="espacio.nombre",
        read_only=True,
    )
    usuario = serializers.CharField(
        source="usuario.username",
        read_only=True,
    )
    estado = serializers.CharField(read_only=True)
    creada = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Reserva
        fields = [
            "id",
            "espacio",
            "espacio_nombre",
            "usuario",
            "fecha",
            "hora_inicio",
            "hora_fin",
            "motivo",
            "estado",
            "creada",
        ]

    def validate(self, attrs):
        if self.instance is None:
            reserva = Reserva(**attrs)
        else:
            reserva = copy.copy(self.instance)
            for field, value in attrs.items():
                setattr(reserva, field, value)

        try:
            reserva.clean()
        except DjangoValidationError as error:
            if hasattr(error, "error_dict"):
                message_dict = error.message_dict
                if NON_FIELD_ERRORS in message_dict:
                    message_dict[api_settings.NON_FIELD_ERRORS_KEY] = (
                        message_dict.pop(NON_FIELD_ERRORS)
                    )
                raise serializers.ValidationError(message_dict) from error
            raise serializers.ValidationError(error.messages) from error

        return attrs
