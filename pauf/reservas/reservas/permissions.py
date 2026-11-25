from rest_framework.permissions import SAFE_METHODS, BasePermission


class EsPersonalSoloLectura(BasePermission):
    def has_permission(self, request, _):
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class EsPropietarioSoloLectura(BasePermission):
    def has_object_permission(self, request, _, obj):
        if request.method in SAFE_METHODS:
            return True

        return obj.usuario == request.user
