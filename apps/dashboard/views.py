from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .metrics import build_dashboard
from .serializers import Dashboard, DashboardParams


@method_decorator(never_cache, name="dispatch")
class DashboardView(APIView):
    @extend_schema(parameters=[DashboardParams], responses=Dashboard)
    def get(self, request):
        params = DashboardParams(data=request.query_params)
        params.is_valid(raise_exception=True)
        summary = build_dashboard(request.user, params.validated_data["bank"])
        return Response(Dashboard(summary).data)
