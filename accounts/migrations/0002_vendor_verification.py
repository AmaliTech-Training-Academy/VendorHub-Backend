from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE accounts_vendorprofile "
                        "ADD COLUMN IF NOT EXISTS decline_reason varchar(255) "
                        "NOT NULL DEFAULT ''; "
                        "ALTER TABLE accounts_vendorprofile "
                        "ADD COLUMN IF NOT EXISTS verification_status varchar(10) "
                        "NOT NULL DEFAULT 'APPROVED'; "
                        "UPDATE accounts_vendorprofile "
                        "SET verification_status = 'APPROVED' "
                        "WHERE verification_status IS NULL; "
                        "ALTER TABLE accounts_vendorprofile "
                        "ALTER COLUMN verification_status SET NOT NULL; "
                        "ALTER TABLE accounts_vendorprofile "
                        "ALTER COLUMN is_active SET DEFAULT false;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="vendorprofile",
                    name="decline_reason",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="vendorprofile",
                    name="verification_status",
                    field=models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("DECLINED", "Declined"),
                        ],
                        # Existing vendors were active before verification existed, so preserve access.
                        default="APPROVED",
                        max_length=10,
                    ),
                ),
                migrations.AlterField(
                    model_name="vendorprofile",
                    name="is_active",
                    field=models.BooleanField(default=False),
                ),
                migrations.AlterField(
                    model_name="vendorprofile",
                    name="verification_status",
                    field=models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("DECLINED", "Declined"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
            ],
        ),
    ]