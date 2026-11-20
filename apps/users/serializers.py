# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

# Retrieves the active user model configured in Django
User = get_user_model()


# Serializer responsible for validating and creating new user accounts
class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name"]
        read_only_fields = ["id"]

    # Normalizes the email by removing whitespace and converting it to lowercase
    def validate_email(self, value):
        return value.strip().lower()

    # Validates the password against Django's configured password validators
    def validate(self, attrs):
        user = User(email=attrs["email"], first_name=attrs.get("first_name", ""))
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    # Creates a new user using the custom user manager and securely hashes the password
    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


# Serializer responsible for retrieving user profile information
class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "date_joined"]
        read_only_fields = ["id", "email", "date_joined"]
