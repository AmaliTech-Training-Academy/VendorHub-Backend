from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
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
    ]