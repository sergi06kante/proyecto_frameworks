import logging


class RegistroPeticionesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("reservas.peticiones")

    def __call__(self, request):
        response = self.get_response(request)
        self.logger.info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
        )
        return response