# Django imports
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings

# App imports
from apps.authentication.csrf import enforce_csrf
from apps.authentication.serializers import LoginSerializer, LogoutSerializer


# Utility functions to set authentication cookies
def set_auth_cookies(response, access_token, refresh_token=None):
    cookie_options = {
        "secure": settings.JWT_COOKIE_SECURE,
        "httponly": True,
        "samesite": settings.JWT_COOKIE_SAMESITE,
        "domain": settings.JWT_COOKIE_DOMAIN,
    }
    response.set_cookie(
        settings.JWT_COOKIE_ACCESS_NAME,
        access_token,
        max_age=int(jwt_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
        path=settings.JWT_COOKIE_ACCESS_PATH,
        **cookie_options,
    )
    if refresh_token is not None:
        response.set_cookie(
            settings.JWT_COOKIE_REFRESH_NAME,
            refresh_token,
            max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
            path=settings.JWT_COOKIE_REFRESH_PATH,
            **cookie_options,
        )
    response["Cache-Control"] = "no-store"
    return response

# Utility functions to clear authentication cookies
def clear_auth_cookies(response):
    response.delete_cookie(
        settings.JWT_COOKIE_ACCESS_NAME,
        path=settings.JWT_COOKIE_ACCESS_PATH,
        domain=settings.JWT_COOKIE_DOMAIN,
        samesite=settings.JWT_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.JWT_COOKIE_REFRESH_NAME,
        path=settings.JWT_COOKIE_REFRESH_PATH,
        domain=settings.JWT_COOKIE_DOMAIN,
        samesite=settings.JWT_COOKIE_SAMESITE,
    )
    response["Cache-Control"] = "no-store"
    return response


# API view for handling CSRF token retrieval, user login, token refresh, and user logout
class CsrfTokenAuth(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrfToken": get_token(request._request)})


# API view for user login that uses the LoginSerializer to validate credentials and set authentication cookies
class LoginAuth(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        enforce_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response({"detail": "Login realizado com sucesso."})
        return set_auth_cookies(
            response,
            access_token=serializer.validated_data["access"],
            refresh_token=serializer.validated_data["refresh"],
        )


# API view for refreshing the access token using the refresh token stored in cookies
class RefreshAuth(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"

    def post(self, request):
        enforce_csrf(request)
        refresh_token = request.COOKIES.get(settings.JWT_COOKIE_REFRESH_NAME)
        if not refresh_token:
            raise InvalidToken("Refresh token ausente.")

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        response = Response({"detail": "Token renovado com sucesso."})
        return set_auth_cookies(
            response,
            access_token=serializer.validated_data["access"],
            refresh_token=serializer.validated_data.get("refresh"),
        )


# API view for user logout that uses the LogoutSerializer to validate the refresh token and clear authentication cookies
class LogoutAuth(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_logout"

    def post(self, request, *args, **kwargs):
        enforce_csrf(request)
        refresh_token = request.COOKIES.get(settings.JWT_COOKIE_REFRESH_NAME)
        if not refresh_token:
            raise InvalidToken("Refresh token ausente.")
        serializer = self.get_serializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        return clear_auth_cookies(response)
