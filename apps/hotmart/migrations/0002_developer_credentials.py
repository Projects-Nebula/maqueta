from django.db import migrations, models


def _wipe_oauth_connections(apps, schema_editor):
    """Existing HotmartConnection rows were created under the abandoned
    `authorization_code` OAuth flow and hold tokens incompatible with the
    new `client_credentials` grant (client-confirmed, no real data exists
    yet). Cascades HotmartProductLink rows; affected sellers see a fresh
    "connect" prompt requiring credential re-entry."""
    HotmartConnection = apps.get_model("hotmart", "HotmartConnection")
    HotmartConnection.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hotmart", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotmartconnection",
            name="credentials_encrypted",
            field=models.TextField(blank=True),
        ),
        migrations.RemoveField(
            model_name="hotmartconnection",
            name="refresh_token_encrypted",
        ),
        migrations.RunPython(_wipe_oauth_connections, migrations.RunPython.noop),
    ]
