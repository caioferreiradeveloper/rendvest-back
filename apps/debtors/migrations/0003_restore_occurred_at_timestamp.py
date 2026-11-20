from django.conf import settings
from django.db import migrations


def restore_occurred_at_timestamp(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    debtor = apps.get_model("debtors", "Debtor")
    table_name = debtor._meta.db_table
    column_name = debtor._meta.get_field("occurred_at").column

    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table_name)
        column = next(field for field in columns if field.name == column_name)
        column_type = connection.introspection.get_field_type(column.type_code, column)

    if column_type == "DateField":
        table = schema_editor.quote_name(table_name)
        field = schema_editor.quote_name(column_name)
        # Legacy dates represent calendar days in the application's timezone.
        schema_editor.execute(
            f"ALTER TABLE {table} ALTER COLUMN {field} TYPE timestamp with time zone "
            f"USING ({field}::timestamp AT TIME ZONE %s)",
            [settings.TIME_ZONE],
        )


class Migration(migrations.Migration):
    dependencies = [("debtors", "0002_reconcile_legacy_debtor_schema")]
    operations = [
        migrations.RunPython(restore_occurred_at_timestamp, migrations.RunPython.noop),
    ]
