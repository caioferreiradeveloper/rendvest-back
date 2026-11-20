# Django imports
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication

# App imports
from apps.authentication.csrf import enforce_csrf


# Custom JWT authentication class that retrieves the token from cookies
class CookieJWTAuthentication(JWTAuthentication):
    
    # Override the authenticate method to retrieve the token from cookies
    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.JWT_COOKIE_ACCESS_NAME)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            enforce_csrf(request)
        return user, validated_token
