# Utility imports
import logging

# Django imports
from django.db.utils import IntegrityError, InterfaceError, OperationalError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

# Core imports
from core.errors import ERROR_CATALOG

# Initializes the module-level logger for recording application errors
logger = logging.getLogger(__name__)


# Recursively flattens nested validation errors into a standardized list of field messages
def _flatten_field_errors(detail, field=None):
    flattened = []
    if isinstance(detail, dict):
        for key, value in detail.items():
            key = str(key)
            nested_field = key if field is None else f"{field}.{key}"
            flattened.extend(_flatten_field_errors(value, nested_field))
    elif isinstance(detail, list | tuple):
        if all(isinstance(item, str | bytes) for item in detail):
            for message in detail:
                flattened.append({"field": field or "non_field_errors", "message": str(message)})
        else:
            for item in detail:
                flattened.extend(_flatten_field_errors(item, field))
    else:
        flattened.append({"field": field or "non_field_errors", "message": str(detail)})
    return flattened


# Builds a standardized API error response using the configured error catalog
def _error_response(error_code, *, errors=None, status_code=None):
    definition = ERROR_CATALOG[error_code]
    return Response(
        {
            "code": error_code,
            "message": definition["message"],
            "errors": errors or [],
        },
        status=status_code or definition["status"],
    )


# Handles application and framework exceptions using the RendVest API error format
def rendvest_exception_handler(exc, context):
    if isinstance(exc, OperationalError | InterfaceError):
        logger.error(
            "Database unavailable while handling API request",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error_response("RENDVEST_ERROR_0009")

    if isinstance(exc, InvalidToken | TokenError):
        return _error_response("RENDVEST_ERROR_0010")

    if isinstance(exc, exceptions.PermissionDenied) and "CSRF Failed" in str(exc.detail):
        return _error_response("RENDVEST_ERROR_0011")

    if isinstance(exc, IntegrityError):
        logger.error(
            "Database integrity conflict while handling API request",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error_response("RENDVEST_ERROR_0007")

    if isinstance(exc, exceptions.ValidationError):
        return _error_response(
            "RENDVEST_ERROR_0002",
            errors=_flatten_field_errors(exc.detail),
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.error(
            "Unhandled exception while handling API request",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error_response("RENDVEST_ERROR_0008")

    error_code = getattr(exc, "error_code", None)
    if error_code is None and isinstance(
        exc,
        exceptions.NotAuthenticated | exceptions.AuthenticationFailed,
    ):
        error_code = "RENDVEST_ERROR_0003"
    elif error_code is None and isinstance(exc, exceptions.PermissionDenied):
        error_code = "RENDVEST_ERROR_0004"
    elif error_code is None and isinstance(exc, exceptions.NotFound):
        error_code = "RENDVEST_ERROR_0005"
    elif error_code is None and isinstance(exc, exceptions.Throttled):
        error_code = "RENDVEST_ERROR_0006"
    elif (
        error_code is None
        and isinstance(exc, exceptions.APIException)
        and response.status_code == status.HTTP_409_CONFLICT
    ):
        error_code = "RENDVEST_ERROR_0007"
    elif error_code is None:
        error_code = "RENDVEST_ERROR_0002"

    errors = _flatten_field_errors(getattr(exc, "detail", ""))
    if error_code in {
        "RENDVEST_ERROR_0001",
        "RENDVEST_ERROR_0003",
        "RENDVEST_ERROR_0004",
        "RENDVEST_ERROR_0005",
        "RENDVEST_ERROR_0006",
        "RENDVEST_ERROR_0007",
    }:
        errors = []
    return _error_response(error_code, errors=errors, status_code=response.status_code)
