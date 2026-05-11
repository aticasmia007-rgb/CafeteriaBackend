from rest_framework import status
from rest_framework.response import Response


def success(data=None, msg=None, created=False):
    body = {'status': '00'}
    if msg:
        body['msg'] = msg
    if data is not None:
        body['data'] = data
    return Response(body, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


def error(http_status, internal_status, msg, errors=None):
    return Response(
        {'status': internal_status, 'msg': msg, 'errors': errors or []},
        status=http_status,
    )
