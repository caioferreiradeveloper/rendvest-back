from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied


class CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    django_request = request._request
    check = CSRFCheck(lambda request: None)
    check.process_request(django_request)
    reason = check.process_view(django_request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")
