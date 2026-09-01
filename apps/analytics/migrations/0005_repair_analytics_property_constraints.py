from django.db import migrations


def repair_postgres_foreign_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        for column_name, referenced_table, constraint_name in (
            ("property_id", "properties", "analytics_events_property_fk"),
            ("unit_id", "property_units", "analytics_events_unit_fk"),
        ):
            cursor.execute(
                """
                SELECT conname, confdeltype
                FROM pg_constraint
                WHERE conrelid = 'analytics_events'::regclass
                  AND contype = 'f'
                  AND conkey = ARRAY[
                      (SELECT attnum
                       FROM pg_attribute
                       WHERE attrelid = 'analytics_events'::regclass
                         AND attname = %s)
                  ]
                """,
                [column_name],
            )
            constraints = cursor.fetchall()
            cascade_constraint_exists = False
            for existing_name, delete_action in constraints:
                if delete_action == "c":
                    cascade_constraint_exists = True
                    continue
                cursor.execute(
                    f'ALTER TABLE "analytics_events" DROP CONSTRAINT "{existing_name}"'
                )

            if not cascade_constraint_exists:
                cursor.execute(
                    f"""
                    ALTER TABLE "analytics_events"
                    ADD CONSTRAINT "{constraint_name}"
                    FOREIGN KEY ("{column_name}")
                    REFERENCES "{referenced_table}" ("id")
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED
                    """
                )


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0004_alter_analyticsevent_property_and_more"),
    ]

    operations = [
        migrations.RunPython(repair_postgres_foreign_keys, migrations.RunPython.noop),
    ]