from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0004_alter_loan_interest_type"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="loan",
            name="loan_exactly_one_interest",
        ),
        migrations.RenameField(
            model_name="loan",
            old_name="fixed_interest_amount",
            new_name="monthly_interest_amount",
        ),
        migrations.AlterField(
            model_name="loan",
            name="interest_type",
            field=models.CharField(
                choices=[
                    ("percentage", "Percentual"),
                    ("fixed_amount", "Juros fixos mensais"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=(
                    Q(
                        interest_type="percentage",
                        monthly_interest_percentage__isnull=False,
                        monthly_interest_amount__isnull=True,
                    )
                    | Q(
                        interest_type="fixed_amount",
                        monthly_interest_percentage__isnull=True,
                        monthly_interest_amount__isnull=False,
                    )
                ),
                name="loan_exactly_one_interest",
            ),
        ),
    ]
