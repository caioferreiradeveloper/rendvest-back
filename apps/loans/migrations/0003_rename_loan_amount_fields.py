from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0002_alter_loan_total_amount_alter_loanpayment_amount"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="loan",
            name="loan_exactly_one_monthly_interest",
        ),
        migrations.RemoveConstraint(
            model_name="loan",
            name="loan_total_amount_positive",
        ),
        migrations.RenameField(
            model_name="loan",
            old_name="total_amount",
            new_name="contracted_amount",
        ),
        migrations.RenameField(
            model_name="loan",
            old_name="monthly_interest_amount",
            new_name="fixed_interest_amount",
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=Q(contracted_amount__gt=0),
                name="loan_contracted_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=(
                    Q(
                        interest_type="percentage",
                        monthly_interest_percentage__isnull=False,
                        fixed_interest_amount__isnull=True,
                    )
                    | Q(
                        interest_type="fixed_amount",
                        monthly_interest_percentage__isnull=True,
                        fixed_interest_amount__isnull=False,
                    )
                ),
                name="loan_exactly_one_interest",
            ),
        ),
    ]
