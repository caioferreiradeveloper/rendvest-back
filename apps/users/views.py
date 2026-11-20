# Django imports
from rest_framework import generics, permissions
from rest_framework.throttling import ScopedRateThrottle

# App imports
from apps.users.serializers import RegistrationSerializer, UserSerializer


# API view responsible for handling external user registration
class ExternalUserCreate(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"


# API view responsible for retrieving and updating the authenticated user's profile
class CurrentUserDetail(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
