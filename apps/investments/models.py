from django.db import models


class MarketSnapshot(models.Model):
    endpoint = models.CharField(max_length=120, primary_key=True)
    data = models.JSONField(null=True)
    fetched_at = models.DateTimeField(null=True)
