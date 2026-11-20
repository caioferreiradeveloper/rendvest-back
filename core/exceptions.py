# Django imports
from rest_framework.exceptions import APIException


# Base exception class for custom RendVest API errors
class RendvestAPIException(APIException):
    error_code = None


# Exception raised when the provided email or password is invalid
class InvalidCredentials(RendvestAPIException):
    error_code = "RENDVEST_ERROR_0001"
    status_code = 401
    default_detail = "E-mail ou senha inválidos."
    default_code = "invalid_credentials"
