import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("storefront", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="order",
            old_name="stripe_session_id",
            new_name="gateway_session_id",
        ),
        migrations.AlterField(
            model_name="order",
            name="gateway_session_id",
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="gateway",
            # Every existing Order row was necessarily created via Stripe —
            # it was the only gateway that existed before this migration.
            field=models.CharField(
                choices=[
                    ("stripe", "Stripe"),
                    ("mercadopago", "Mercadopago"),
                    ("paypal", "Paypal"),
                    ("braintree", "Braintree"),
                    ("wompi", "Wompi"),
                    ("payu", "Payu"),
                    ("epayco", "Epayco"),
                    ("bold", "Bold"),
                ],
                default="stripe",
                max_length=16,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="order",
            unique_together={("gateway", "gateway_session_id")},
        ),
        migrations.CreateModel(
            name="PaymentGatewayConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "gateway",
                    models.CharField(
                        choices=[
                            ("stripe", "stripe"),
                            ("mercadopago", "mercadopago"),
                            ("paypal", "paypal"),
                            ("braintree", "braintree"),
                            ("wompi", "wompi"),
                            ("payu", "payu"),
                            ("epayco", "epayco"),
                            ("bold", "bold"),
                        ],
                        max_length=16,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=False)),
                ("credentials_encrypted", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_gateway_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["gateway"],
                "unique_together": {("owner", "gateway")},
            },
        ),
    ]
