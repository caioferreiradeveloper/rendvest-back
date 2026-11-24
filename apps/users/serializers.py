from decimal import Decimal

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.notifications.models import Notification
from apps.users.models import ContactMessage

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
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Já existe um cadastro com este e-mail.")
        return email

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
        return User.objects.create_user(
            password=password, is_active=False, pending_approval=True, **validated_data
        )


# Serializer responsible for retrieving user profile information
class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "date_joined", "is_staff"]
        read_only_fields = ["id", "email", "date_joined", "is_staff"]


class AdminUserSerializer(UserSerializer):
    can_manage = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["is_active", "pending_approval", "can_manage"]
        read_only_fields = fields

    @staticmethod
    def user_can_manage(actor, user):
        return actor.pk != user.pk and (
            actor.is_superuser or not (user.is_staff or user.is_superuser)
        )

    @extend_schema_field(serializers.BooleanField())
    def get_can_manage(self, user):
        return self.user_can_manage(self.context["request"].user, user)


class UserStatusSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "disable", "enable"])


class ContactMessageSerializer(serializers.ModelSerializer):
    monthly_goal = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )

    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "message", "monthly_goal", "preferred_date", "created_at"]
        read_only_fields = ["id", "created_at"]

    @transaction.atomic
    def create(self, validated_data):
        notification = Notification.objects.create(
            title="Nova mensagem de contato",
            description=f'{validated_data["name"]} enviou uma mensagem pelo site.',
            type=Notification.Type.SYSTEM,
            staff_only=True,
        )
        return ContactMessage.objects.create(notification=notification, **validated_data)


class AdminDashboardSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    pending_users = serializers.IntegerField()
    disabled_users = serializers.IntegerField()
    contact_messages = serializers.IntegerField()
