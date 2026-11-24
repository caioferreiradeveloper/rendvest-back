# Django imports
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.users.models import ContactMessage

# App imports
from apps.users.serializers import (
    AdminDashboardSerializer,
    AdminUserSerializer,
    ContactMessageSerializer,
    RegistrationSerializer,
    UserSerializer,
    UserStatusSerializer,
)

User = get_user_model()


# API view responsible for handling external user registration
class ExternalUserCreate(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"
    authentication_classes = []


# API view responsible for retrieving and updating the authenticated user's profile
class CurrentUserDetail(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class AdminUserList(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.all()

    @extend_schema(parameters=[OpenApiParameter("pending", bool)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("pending") == "true":
            queryset = queryset.filter(pending_approval=True)
        return queryset


class AdminUserStatus(generics.GenericAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = UserStatusSerializer
    queryset = User.objects.all()

    @extend_schema(responses=AdminUserSerializer)
    @transaction.atomic
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        if not AdminUserSerializer.user_can_manage(request.user, user):
            raise PermissionDenied()

        action = serializer.validated_data["action"]
        if action == "approve" and user.pending_approval:
            user.pending_approval = False
            user.is_active = True
        elif action in ("disable", "enable") and not user.pending_approval:
            user.is_active = action == "enable"
        else:
            raise serializers.ValidationError({"action": "Ação indisponível para este cadastro."})

        user.save(update_fields=["is_active", "pending_approval"])
        return Response(AdminUserSerializer(user, context=self.get_serializer_context()).data)


class ContactMessageCreate(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact_message"
    serializer_class = ContactMessageSerializer


class AdminMessageList(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ContactMessageSerializer
    queryset = ContactMessage.objects.all()


class AdminMessageDetail(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ContactMessageSerializer
    queryset = ContactMessage.objects.all()


class AdminDashboard(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses=AdminDashboardSerializer)
    def get(self, request):
        counts = User.objects.aggregate(
            total_users=Count("pk"),
            active_users=Count("pk", filter=Q(is_active=True, pending_approval=False)),
            pending_users=Count("pk", filter=Q(pending_approval=True)),
            disabled_users=Count("pk", filter=Q(is_active=False, pending_approval=False)),
        )
        counts["contact_messages"] = ContactMessage.objects.count()
        return Response(AdminDashboardSerializer(counts).data)
