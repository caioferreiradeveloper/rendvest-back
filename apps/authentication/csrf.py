# Django imports
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied


# Custom CSRF check class that overrides the _reject method to return the reason for rejection
class CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


# Function to enforce CSRF protection on a request
def enforce_csrf(request):
    django_request = request._request
    check = CSRFCheck(lambda request: None)
    check.process_request(django_request)
    reason = check.process_view(django_request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")
