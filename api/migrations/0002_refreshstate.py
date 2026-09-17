"""Add durable refresh progress."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("api", "0001_initial")]
    operations = [migrations.CreateModel(
        name="RefreshState",
        fields=[
            ("name", models.CharField(default="worms", max_length=32, primary_key=True, serialize=False)),
            ("last_success_at", models.DateTimeField(blank=True, null=True)),
            ("started_at", models.DateTimeField(blank=True, null=True)),
            ("finished_at", models.DateTimeField(blank=True, null=True)),
            ("status", models.CharField(default="never_run", max_length=16)),
            ("failed_ids", models.JSONField(default=list)),
        ],
    )]
