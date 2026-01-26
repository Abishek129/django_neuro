from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("control_pannel", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="user_uuid",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
