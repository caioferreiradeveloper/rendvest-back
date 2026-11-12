from rest_framework.exceptions import APIException


class RendvestAPIException(APIException):
    error_code = None


class InvalidCredentials(RendvestAPIException):
    error_code = "RENDVEST_ERROR_0001"
    status_code = 401
    default_detail = "E-mail ou senha inválidos."
    default_code = "invalid_credentials"
