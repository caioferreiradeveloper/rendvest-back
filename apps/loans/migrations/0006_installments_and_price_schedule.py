import calendar
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


CENT = Decimal("0.01")


def _due_date(first_due_date, month_offset):
    month_index = first_due_date.year * 12 + first_due_date.month - 1 + month_offset
    year, month_zero_indexed = divmod(month_index, 12)
    month = month_zero_indexed + 1
    day = min(first_due_date.day, calendar.monthrange(year, month)[1])
    due_date = first_due_date.replace(year=year, month=month, day=day)
    while due_date.weekday() >= 5:
        due_date += timedelta(days=1)
    return due_date


def _payment_amount(principal, rate, term_months):
    if rate == 0:
        return principal / term_months
    return principal * rate / (Decimal("1") - (Decimal("1") + rate) ** -term_months)


def prepare_legacy_loans(apps, schema_editor):
    Loan = apps.get_model("loans", "Loan")

    for loan in Loan.objects.all().iterator():
        if loan.interest_type == "fixed_amount":
            principal = Decimal(loan.contracted_amount)
            term_months = loan.term_months
            target_payment = (
                principal + Decimal(loan.monthly_interest_amount) * term_months
            ) / term_months

            if target_payment <= principal / term_months:
                monthly_rate = Decimal("0")
            else:
                low = Decimal("0")
                high = Decimal("1")
                while _payment_amount(principal, high, term_months) < target_payment:
                    high *= 2
                for _ in range(100):
                    middle = (low + high) / 2
                    if _payment_amount(principal, middle, term_months) < target_payment:
                        low = middle
                    else:
                        high = middle
                monthly_rate = ((low + high) / 2 * 100).quantize(
                    Decimal("0.0001"),
                    rounding=ROUND_HALF_UP,
                )

            loan.monthly_interest_percentage = monthly_rate

        if loan.first_due_date is None:
            loan.first_due_date = _due_date(loan.started_at, 1)

        loan.save(update_fields=["monthly_interest_percentage", "first_due_date"])


def create_legacy_schedules(apps, schema_editor):
    Loan = apps.get_model("loans", "Loan")
    Installment = apps.get_model("loans", "LoanInstallment")
    Payment = apps.get_model("loans", "LoanPayment")

    installments_by_loan = {}
    for loan in Loan.objects.all().iterator():
        principal = Decimal(loan.contracted_amount) + Decimal(loan.iof_amount)
        rate = Decimal(loan.monthly_interest_percentage) / Decimal("100")
        term_months = loan.term_months
        exact_payment = _payment_amount(principal, rate, term_months)
        regular_payment = exact_payment.quantize(CENT, rounding=ROUND_HALF_UP)
        total = (exact_payment * term_months).quantize(CENT, rounding=ROUND_HALF_UP)
        balance = principal
        installments = []

        for number in range(1, term_months + 1):
            amount_due = (
                total - regular_payment * (term_months - 1)
                if number == term_months
                else regular_payment
            )
            interest = (balance * rate).quantize(CENT, rounding=ROUND_HALF_UP)
            if number == term_months:
                principal_due = balance
                interest = amount_due - principal_due
            else:
                principal_due = amount_due - interest

            installment = Installment.objects.create(
                loan_id=loan.pk,
                number=number,
                due_date=_due_date(loan.first_due_date, number - 1),
                amount_due=amount_due,
                interest_amount=interest,
                principal_amount=principal_due,
            )
            installments.append(installment)
            balance -= principal_due

        installments_by_loan[loan.pk] = installments

    for payment in Payment.objects.select_related("loan").order_by("paid_at", "created_at"):
        installments = installments_by_loan.get(payment.loan_id, [])
        if not installments:
            continue
        paid_date = payment.paid_at.date()
        installment = min(
            installments,
            key=lambda item: abs((item.due_date - paid_date).days),
        )
        previous_interest = Payment.objects.filter(installment=installment).aggregate(
            total=models.Sum("interest_portion")
        )["total"] or Decimal("0.00")
        interest_portion = min(
            Decimal(payment.amount),
            max(Decimal(installment.interest_amount) - previous_interest, Decimal("0.00")),
        )
        payment.installment_id = installment.pk
        payment.interest_portion = interest_portion
        payment.principal_portion = Decimal(payment.amount) - interest_portion
        payment.save(update_fields=["installment", "interest_portion", "principal_portion"])


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0005_rename_fixed_interest_to_monthly"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="loan",
            name="loan_exactly_one_interest",
        ),
        migrations.AddField(
            model_name="loan",
            name="iof_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="monthly_cet_percentage",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=7,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="first_due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="LoanInstallment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("number", models.PositiveSmallIntegerField()),
                ("due_date", models.DateField()),
                ("amount_due", models.DecimalField(decimal_places=2, max_digits=12)),
                ("interest_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("principal_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "loan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="installments",
                        to="loans.loan",
                    ),
                ),
            ],
            options={"ordering": ["number"]},
        ),
        migrations.AddField(
            model_name="loanpayment",
            name="installment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payments",
                to="loans.loaninstallment",
            ),
        ),
        migrations.AddField(
            model_name="loanpayment",
            name="interest_portion",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.AddField(
            model_name="loanpayment",
            name="principal_portion",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.RunPython(prepare_legacy_loans, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="loan",
            name="first_due_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="loan",
            name="monthly_interest_percentage",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=7,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=Q(iof_amount__gte=0), name="loan_iof_nonnegative"
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=Q(monthly_interest_percentage__gte=0),
                name="loan_monthly_interest_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="loaninstallment",
            constraint=models.UniqueConstraint(
                fields=("loan", "number"),
                name="loan_installment_number_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="loaninstallment",
            constraint=models.CheckConstraint(
                condition=Q(number__gt=0),
                name="loan_installment_number_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="loaninstallment",
            constraint=models.CheckConstraint(
                condition=Q(amount_due__gt=0),
                name="loan_installment_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="loaninstallment",
            constraint=models.CheckConstraint(
                condition=Q(interest_amount__gte=0),
                name="loan_installment_interest_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="loaninstallment",
            constraint=models.CheckConstraint(
                condition=Q(principal_amount__gte=0),
                name="loan_installment_principal_nonnegative",
            ),
        ),
        migrations.RunPython(create_legacy_schedules, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="loanpayment",
            name="loan",
        ),
        migrations.AlterField(
            model_name="loanpayment",
            name="installment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payments",
                to="loans.loaninstallment",
            ),
        ),
        migrations.AddConstraint(
            model_name="loanpayment",
            constraint=models.CheckConstraint(
                condition=Q(interest_portion__gte=0),
                name="loan_payment_interest_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="loanpayment",
            constraint=models.CheckConstraint(
                condition=Q(principal_portion__gte=0),
                name="loan_payment_principal_nonnegative",
            ),
        ),
        migrations.RemoveField(
            model_name="loan",
            name="interest_type",
        ),
        migrations.RemoveField(
            model_name="loan",
            name="monthly_interest_amount",
        ),
    ]
