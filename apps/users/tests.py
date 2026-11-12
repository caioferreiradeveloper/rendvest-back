from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.loans.models import Loan, LoanInstallment
from apps.transactions.models import Transaction

User = get_user_model()


class UserProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com",
            password="SecurePassword123!",
            first_name="Test",
        )

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("users:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_update_own_profile_but_not_email(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            reverse("users:me"),
            {"first_name": "Updated", "email": "attacker@example.com"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Updated")
        self.assertEqual(response.data["email"], "user@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "user@example.com")

    def test_registration_is_available_under_users_namespace(self):
        response = self.client.post(
            reverse("users:register"),
            {"email": "new@example.com", "password": "AnotherSecure123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LoadFixturesCommandTests(APITestCase):
    @override_settings(DEBUG=True)
    def test_load_fixtures_is_repeatable(self):
        call_command("load_fixtures", stdout=StringIO())
        call_command("load_fixtures", stdout=StringIO())

        demo_user = User.objects.get(email="demo@rendvest.local")
        self.assertTrue(demo_user.check_password("RendvestDemo2026!"))
        self.assertEqual(Transaction.objects.filter(user=demo_user).count(), 4)
        loan = Loan.objects.get(user=demo_user)
        self.assertEqual(loan.contracted_amount, Decimal("8000.00"))
        self.assertEqual(loan.iof_amount, Decimal("117.98"))
        self.assertEqual(loan.monthly_interest_percentage, Decimal("8.4500"))
        self.assertEqual(loan.total_with_interest, Decimal("11083.23"))
        self.assertEqual(loan.term_months, 7)
        self.assertEqual(LoanInstallment.objects.filter(loan=loan).count(), 7)

    @override_settings(DEBUG=False)
    def test_load_fixtures_is_blocked_when_debug_is_disabled(self):
        with self.assertRaises(CommandError):
            call_command("load_fixtures", stdout=StringIO())
