# Django imports
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

# Core imports
from core.exceptions import InvalidCredentials


# Serializer for user login that extends the TokenObtainPairSerializer
class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed as exc:
            raise InvalidCredentials from exc

# Serializer for user logout that handles the refresh token
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            self.token = RefreshToken(value)
        except TokenError as exc:
            raise serializers.ValidationError("Refresh token inválido ou expirado.") from exc
        return value

    def save(self, **kwargs):
        self.token.blacklist()
