from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


class AuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            email="user@example.com",
            password="SecurePassword123!",
        )

    def get_csrf_headers(self):
        response = self.client.get(reverse("authentication:csrf"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("csrftoken", self.client.cookies)
        return {"HTTP_X_CSRFTOKEN": response.data["csrfToken"]}

    def test_registration_validates_password_and_normalizes_email(self):
        weak_password_response = self.client.post(
            reverse("users:register"),
            {"email": "new@example.com", "password": "password"},
        )
        self.assertEqual(weak_password_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(weak_password_response.data["code"], "RENDVEST_ERROR_0002")
        self.assertEqual(weak_password_response.data["errors"][0]["field"], "password")
        self.assertTrue(weak_password_response.data["errors"][0]["message"])
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

        response = self.client.post(
            reverse("users:register"),
            {"email": "  NEW@EXAMPLE.COM  ", "password": "AnotherSecure123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertNotIn("password", response.data)

    @override_settings(JWT_COOKIE_SECURE=True)
    def test_login_refresh_and_logout(self):
        csrf_headers = self.get_csrf_headers()
        login_response = self.client.post(
            reverse("authentication:login"),
            {"email": self.user.email, "password": "SecurePassword123!"},
            **csrf_headers,
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("access", login_response.data)
        self.assertNotIn("refresh", login_response.data)
        self.assertTrue(login_response.cookies["access_token"]["httponly"])
        self.assertTrue(login_response.cookies["refresh_token"]["httponly"])
        self.assertTrue(login_response.cookies["access_token"]["secure"])
        self.assertEqual(login_response.cookies["access_token"]["samesite"], "Lax")

        refresh_response = self.client.post(
            reverse("authentication:refresh"),
            **csrf_headers,
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("access", refresh_response.data)
        self.assertNotIn("refresh", refresh_response.data)
        self.assertNotEqual(
            refresh_response.cookies["refresh_token"].value,
            login_response.cookies["refresh_token"].value,
        )

        profile_response = self.client.get(reverse("users:me"))
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data["email"], self.user.email)

        self.client.cookies.pop("access_token", None)
        logout_response = self.client.post(
            reverse("authentication:logout"),
            **csrf_headers,
        )
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(logout_response.cookies["access_token"].value, "")
        self.assertEqual(logout_response.cookies["refresh_token"].value, "")

        retry_response = self.client.post(
            reverse("authentication:refresh"),
            **csrf_headers,
        )
        self.assertEqual(retry_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(retry_response.data["code"], "RENDVEST_ERROR_0010")

    def test_auth_endpoints_require_csrf(self):
        response = self.client.post(
            reverse("authentication:login"),
            {"email": self.user.email, "password": "SecurePassword123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "RENDVEST_ERROR_0011")

    def test_invalid_credentials_return_generic_message_and_error_code(self):
        csrf_headers = self.get_csrf_headers()
        response = self.client.post(
            reverse("authentication:login"),
            {"email": self.user.email, "password": "incorrect-password"},
            **csrf_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "RENDVEST_ERROR_0001")
        self.assertEqual(response.data["message"], "E-mail ou senha inválidos.")
        self.assertEqual(response.data["errors"], [])

    @override_settings(CORS_ALLOWED_ORIGINS=["https://app.example.com"])
    def test_cors_allows_configured_origin_with_credentials(self):
        response = self.client.options(
            reverse("authentication:login"),
            HTTP_ORIGIN="https://app.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,x-csrftoken",
        )

        self.assertEqual(response["Access-Control-Allow-Origin"], "https://app.example.com")
        self.assertEqual(response["Access-Control-Allow-Credentials"], "true")

    def test_local_development_origins_are_cors_and_csrf_trusted(self):
        self.assertIn("http://localhost:5173", settings.CORS_ALLOWED_ORIGINS)
        self.assertIn("http://localhost:5173", settings.CSRF_TRUSTED_ORIGINS)

    def test_unsafe_authenticated_request_requires_csrf(self):
        csrf_headers = self.get_csrf_headers()
        login_response = self.client.post(
            reverse("authentication:login"),
            {"email": self.user.email, "password": "SecurePassword123!"},
            **csrf_headers,
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        response = self.client.patch(reverse("users:me"), {"first_name": "Changed"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_is_rate_limited(self):
        csrf_headers = self.get_csrf_headers()
        for _ in range(5):
            self.client.post(
                reverse("authentication:login"),
                {"email": self.user.email, "password": "wrong-password"},
                **csrf_headers,
            )

        response = self.client.post(
            reverse("authentication:login"),
            {"email": self.user.email, "password": "wrong-password"},
            **csrf_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
