from django.db.utils import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from core.exception_handler import rendvest_exception_handler


class APIExceptionHandlerTests(SimpleTestCase):
    def test_database_unavailable_returns_safe_response(self):
        request = APIRequestFactory().get("/")
        response = rendvest_exception_handler(
            OperationalError("private database connection details"),
            {"request": request},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "RENDVEST_ERROR_0009")
        self.assertNotIn("private database connection details", str(response.data))
        self.assertEqual(response.data["errors"], [])
