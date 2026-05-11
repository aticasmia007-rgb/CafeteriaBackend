from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and response.status_code == 400:
        return Response(
            {'status': '06', 'msg': 'Los datos de entrada no son válidos.', 'errors': response.data},
            status=422,
        )
    return response
