import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Debtor',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('debtor_name', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('description', models.TextField(blank=True)),
                ('occurred_at', models.DateTimeField()),
                ('paid_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='debtors', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-occurred_at', '-created_at'],
                'indexes': [models.Index(fields=['user', '-occurred_at'], name='debtor_user_date_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='debtor_amount_positive'), models.CheckConstraint(condition=models.Q(('paid_amount__gte', 0)), name='debtor_paid_amount_nonnegative'), models.CheckConstraint(condition=models.Q(('paid_amount__lte', models.F('amount'))), name='debtor_paid_amount_lte_amount')],
            },
        ),
    ]
