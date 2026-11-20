# Django imports
from django.db import migrations


# Reconcile databases where the initial migration ran with the legacy fields.
def reconcile_legacy_debtor_schema(apps, schema_editor):
    debtor = apps.get_model("debtors", "Debtor")
    table_name = debtor._meta.db_table
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = {
            field.name
            for field in connection.introspection.get_table_description(cursor, table_name)
        }

    if not {"debit_amount", "started_at"}.issubset(columns):
        return

    table = schema_editor.quote_name(table_name)
    schema_editor.execute(f'ALTER TABLE {table} RENAME COLUMN "debit_amount" TO "amount"')
    schema_editor.execute(f'ALTER TABLE {table} RENAME COLUMN "started_at" TO "occurred_at"')

    for field_name in ("description", "paid_amount", "paid_at"):
        schema_editor.add_field(debtor, debtor._meta.get_field(field_name))

    schema_editor.execute(
        f'ALTER TABLE {table} RENAME CONSTRAINT "debtor_debit_amount_positive" '
        'TO "debtor_amount_positive"'
    )
    schema_editor.execute('ALTER INDEX "debtor_user_started_idx" RENAME TO "debtor_user_date_idx"')

    for constraint in debtor._meta.constraints:
        if constraint.name != "debtor_amount_positive":
            schema_editor.add_constraint(debtor, constraint)


class Migration(migrations.Migration):
    dependencies = [("debtors", "0001_initial")]

    # The migration state already matches the model, so reversing keeps the reconciled schema.
    operations = [
        migrations.RunPython(reconcile_legacy_debtor_schema, migrations.RunPython.noop),
    ]
