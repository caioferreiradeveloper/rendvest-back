from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.notifications.models import Notification

User = get_user_model()


class AdministrationTests(APITestCase):
    password = "River-Canopy-37!"

    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user("staff@example.com", is_staff=True)

    def login(self, client, email):
        csrf = client.get(reverse("authentication:csrf-token-auth")).data["csrfToken"]
        return client.post(
            reverse("authentication:login-auth"),
            {"email": email, "password": self.password},
            HTTP_X_CSRFTOKEN=csrf,
        )

    def test_registration_approval_disable_and_reenable(self):
        guest = APIClient()
        email = "new@example.com"
        registered = guest.post(reverse("users:external-user-create"), {
            "email": email, "password": self.password, "is_staff": True, "is_active": True,
        })
        self.assertEqual(registered.status_code, 201)
        user = User.objects.get(email=email)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertNotEqual(self.login(guest, email).status_code, 200)

        admin_users = reverse("users:admin-users")
        change_status = reverse("users:admin-user-status", args=[user.pk])
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(admin_users).status_code, 403)
        self.assertEqual(self.client.post(change_status, {"action": "approve"}).status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(admin_users, {"pending": "true"}).data["count"], 1)
        self.assertEqual(self.client.post(change_status, {"action": "enable"}).status_code, 400)
        self.assertEqual(self.client.post(change_status, {"action": "approve"}).status_code, 200)
        self.assertEqual(self.client.get(admin_users, {"pending": "true"}).data["count"], 0)
        self.assertEqual(self.login(guest, email).status_code, 200)

        self.assertEqual(self.client.post(change_status, {"action": "disable"}).status_code, 200)
        self.assertEqual(guest.get(reverse("users:current-user-detail")).status_code, 401)
        csrf = guest.get(reverse("authentication:csrf-token-auth")).data["csrfToken"]
        self.assertIn(settings.JWT_COOKIE_REFRESH_NAME, guest.cookies)
        self.assertEqual(guest.post(
            reverse("authentication:refresh-auth"), HTTP_X_CSRFTOKEN=csrf,
        ).status_code, 401)
        self.assertNotEqual(self.login(guest, email).status_code, 200)
        self.assertEqual(self.client.post(change_status, {"action": "enable"}).status_code, 200)
        self.assertEqual(self.login(guest, email).status_code, 200)

    def test_contact_notification_is_staff_only_with_individual_read_status(self):
        contact = self.client.post(reverse("users:contact-create"), {
            "name": "Visitante", "email": "visitor@example.com", "message": "Olá",
        })
        self.assertEqual(contact.status_code, 201)
        message_pk = contact.data["id"]
        message_url = reverse("users:admin-message", args=[message_pk])
        notifications = "/api/v1/notifications/"
        notification = Notification.objects.get(contact_message__pk=message_pk)
        read_url = f"{notifications}{notification.pk}/read/"

        self.client.force_authenticate(User.objects.create_user("member@example.com"))
        self.assertEqual(self.client.get(message_url).status_code, 403)
        self.assertEqual(self.client.get(notifications).data, [])
        self.assertEqual(self.client.post(read_url).status_code, 404)

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(message_url).data["message"], "Olá")
        self.assertEqual(self.client.get(notifications).data[0]["contact_message_id"], message_pk)
        self.assertEqual(self.client.post(read_url).data["status"], "read")
        self.client.force_authenticate(User.objects.create_user("other@example.com", is_staff=True))
        self.assertEqual(self.client.get(notifications).data[0]["status"], "no_read")

    def test_dashboard_totals_are_staff_only_and_distinguish_pending_from_disabled(self):
        dashboard = reverse("users:admin-dashboard")
        member = User.objects.create_user("member@example.com")
        self.assertEqual(self.client.get(dashboard).status_code, 401)
        self.client.force_authenticate(member)
        self.assertEqual(self.client.get(dashboard).status_code, 403)

        User.objects.create_user("pending@example.com", is_active=False, pending_approval=True)
        User.objects.create_user("disabled@example.com", is_active=False)
        response = self.client.post(reverse("users:contact-create"), {
            "name": "Visitante", "email": "visitor@example.com", "message": "Olá",
        })
        self.assertEqual(response.status_code, 201)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(dashboard).data, {
            "total_users": 4,
            "active_users": 2,
            "pending_users": 1,
            "disabled_users": 1,
            "contact_messages": 1,
        })
