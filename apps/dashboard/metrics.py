from datetime import datetime, time
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.debtors.models import Debtor
from apps.loans.models import Loan, LoanInstallment, LoanPayment
from apps.monthlies.models import Monthly, MonthlySettlement
from apps.transactions.models import Transaction
from apps.wishlist.models import WishlistItem
from core.enums import Type

ZERO = Decimal("0.00")


def month_offset(month, offset):
    year, index = divmod(month.year * 12 + month.month - 1 + offset, 12)
    return month.replace(year=year, month=index + 1)


def midnight(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def transaction_metrics(user, now, month, bank):
    transactions = Transaction.objects.filter(user=user, occurred_at__lte=now, invoice__isnull=True)
    if bank:
        transactions = transactions.filter(bank=bank)

    start = month_offset(month, -5)
    rows = (
        transactions.filter(occurred_at__gte=midnight(start))
        .order_by()
        .annotate(period=TruncMonth("occurred_at"))
        .values("period", "type")
        .annotate(total=Sum("amount"), count=Count("pk"))
    )
    totals = {(row["period"].date(), row["type"]): row["total"] for row in rows}
    history = []
    for offset in range(-5, 1):
        period = month_offset(month, offset)
        income = totals.get((period, Type.INCOME), ZERO)
        expenses = totals.get((period, Type.EXPENSE), ZERO)
        history.append(
            {
                "month": period,
                "income": income,
                "expenses": expenses,
                "net": income - expenses,
            }
        )

    balance = transactions.aggregate(
        income=Sum("amount", filter=Q(type=Type.INCOME), default=ZERO),
        expenses=Sum("amount", filter=Q(type=Type.EXPENSE), default=ZERO),
    )
    current = history[-1]
    return (
        {
            "balance": balance["income"] - balance["expenses"],
            "income": current["income"],
            "expenses": current["expenses"],
            "net": current["net"],
            "transaction_count": sum(row["count"] for row in rows if row["period"].date() == month),
        },
        history,
        list(
            transactions.values(
                "id", "category", "description", "amount", "type", "bank", "occurred_at"
            )[:5]
        ),
    )


def loan_metrics(user, today, month, now):
    loans = Loan.objects.filter(user=user, started_at__lte=today).annotate(
        paid=Sum(
            "installments__payments__amount",
            filter=Q(installments__payments__paid_at__lte=now),
            default=ZERO,
        ),
        discounts=Sum(
            "installments__payments__discount_amount",
            filter=Q(installments__payments__paid_at__lte=now),
            default=ZERO,
        ),
    )
    balances = [max(loan.total_with_interest - loan.paid - loan.discounts, ZERO) for loan in loans]
    overdue = (
        LoanInstallment.objects.filter(loan__in=loans, due_date__lt=today)
        .annotate(
            paid=Sum("payments__amount", filter=Q(payments__paid_at__lte=now), default=ZERO),
            discounts=Sum(
                "payments__discount_amount", filter=Q(payments__paid_at__lte=now), default=ZERO
            ),
        )
        .filter(amount_due__gt=F("paid") + F("discounts"))
        .count()
    )
    paid_this_month = LoanPayment.objects.filter(
        installment__loan__in=loans, paid_at__range=(midnight(month), now)
    ).aggregate(total=Sum("amount", default=ZERO))["total"]
    return {
        "active_count": sum(balance > ZERO for balance in balances),
        "outstanding": sum(balances, ZERO),
        "paid_this_month": paid_this_month,
        "overdue_installments": overdue,
    }


def monthly_metrics(user, month, next_month, today):
    settlements = MonthlySettlement.objects.filter(
        monthly__user=user, month=month, settled_on__lte=today
    )
    settled_ids = set(settlements.values_list("monthly_id", flat=True))
    invoice_totals = dict(
        Transaction.objects.filter(user=user, invoice_month=month)
        .order_by()
        .values("invoice")
        .annotate(total=Sum("amount"))
        .values_list("invoice", "total")
    )
    recurring = Monthly.objects.filter(user=user, start_date__lt=next_month).filter(
        Q(end_date__gte=month) | Q(end_date__isnull=True)
    )
    income = expenses = ZERO
    pending = 0
    for item in recurring:
        if item.pk in settled_ids or item.due_date_for(month) is None:
            continue
        amount = invoice_totals.get(item.pk, ZERO) if item.is_invoice else item.amount
        if not amount:
            continue
        pending += 1
        if item.type == Type.INCOME:
            income += amount
        else:
            expenses += amount
    return {
        "settled_count": len(settled_ids),
        "pending_count": pending,
        "pending_income": income,
        "pending_expenses": expenses,
    }


def build_dashboard(user, bank=""):
    now = timezone.now()
    today = timezone.localdate(now)
    month = today.replace(day=1)
    next_month = month_offset(month, 1)
    transactions, history, recent = transaction_metrics(user, now, month, bank)
    debtors = Debtor.objects.filter(user=user, occurred_at__lte=now).aggregate(
        outstanding=Sum(F("amount") - F("paid_amount"), default=ZERO),
        open_count=Count("pk", filter=Q(amount__gt=F("paid_amount"))),
        received_this_month=Sum(
            "paid_amount", filter=Q(paid_at__range=(midnight(month), now)), default=ZERO
        ),
    )
    wishlist = WishlistItem.objects.filter(user=user).aggregate(
        count=Count("pk"),
        total=Sum("amount", default=ZERO),
        planned_this_month=Sum(
            "amount",
            filter=Q(expected_purchase_date__gte=month, expected_purchase_date__lt=next_month),
            default=ZERO,
        ),
    )
    return {
        "as_of": today,
        "transactions": transactions,
        "loans": loan_metrics(user, today, month, now),
        "debtors": debtors,
        "wishlist": wishlist,
        "monthlies": monthly_metrics(user, month, next_month, today),
        "history": history,
        "recent": recent,
    }
