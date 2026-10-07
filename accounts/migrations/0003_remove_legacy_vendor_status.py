from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_vendor_verification"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE accounts_vendorprofile DROP COLUMN IF EXISTS status",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
