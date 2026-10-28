from django.db import migrations, models
import uuid


def seed_default_placements(apps, schema_editor):
    Placement = apps.get_model("marketing", "Placement")
    defaults = [
        {
            "audience": "corporate",
            "slot": "feature",
            "name": "Workplace leagues",
            "tagline": "Run the office cup, the factory ladder, the regional KPI table.",
            "body": "Fair Measure hosts branded competitions for staff, partners and customers — with your scoring, your feed and your results.",
            "cta_label": "Talk to partnerships",
            "display_order": 0,
        },
        {
            "audience": "corporate",
            "slot": "feature",
            "name": "Brand and broadcast",
            "tagline": "Kit, naming rights and live boards on public competitions.",
            "body": "Buy a commercial slot on the landing page, a league feed or a match day. Logos, banners and feature cards are managed from the admin.",
            "cta_label": "Book a slot",
            "display_order": 1,
        },
        {
            "audience": "government",
            "slot": "feature",
            "name": "Schools and municipalities",
            "tagline": "One platform for district sport, school cups and civic games.",
            "body": "Public-sector competitions stay public. Residents can follow tables and fixtures without an account. Officials still run scoring and reports.",
            "cta_label": "Plan a programme",
            "display_order": 0,
        },
        {
            "audience": "government",
            "slot": "feature",
            "name": "National and provincial programmes",
            "tagline": "Talent pathways, school-to-club and public results.",
            "body": "Government partners get reserved commercial space, a named programme on the landing page, and a route for federations and departments to enquire.",
            "cta_label": "Contact public sector",
            "display_order": 1,
        },
        {
            "audience": "general",
            "slot": "logo",
            "name": "Pitchside",
            "tagline": "Kit",
            "display_order": 0,
        },
        {
            "audience": "general",
            "slot": "logo",
            "name": "Harbour Radio",
            "tagline": "Broadcast",
            "display_order": 1,
        },
        {
            "audience": "general",
            "slot": "logo",
            "name": "Millwater",
            "tagline": "Hydration",
            "display_order": 2,
        },
        {
            "audience": "general",
            "slot": "logo",
            "name": "Northstand",
            "tagline": "Community",
            "display_order": 3,
        },
        {
            "audience": "general",
            "slot": "logo",
            "name": "Ledger & Co",
            "tagline": "Workplace",
            "display_order": 4,
        },
    ]
    for row in defaults:
        Placement.objects.create(**row)


def unseed_default_placements(apps, schema_editor):
    Placement = apps.get_model("marketing", "Placement")
    Placement.objects.all().delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Placement",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "audience",
                    models.CharField(
                        choices=[
                            ("corporate", "Corporate"),
                            ("government", "Government"),
                            ("general", "General"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "slot",
                    models.CharField(
                        choices=[
                            ("feature", "Feature card"),
                            ("banner", "Commercial banner"),
                            ("logo", "Sponsor logo"),
                        ],
                        default="feature",
                        max_length=16,
                    ),
                ),
                ("name", models.CharField(max_length=160)),
                ("tagline", models.CharField(blank=True, max_length=200)),
                ("body", models.TextField(blank=True)),
                ("cta_label", models.CharField(blank=True, max_length=80)),
                ("cta_url", models.URLField(blank=True)),
                ("logo_url", models.URLField(blank=True)),
                ("active", models.BooleanField(default=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Enquiry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "audience",
                    models.CharField(
                        choices=[
                            ("corporate", "Corporate"),
                            ("government", "Government"),
                        ],
                        max_length=20,
                    ),
                ),
                ("organisation", models.CharField(max_length=200)),
                ("contact_name", models.CharField(max_length=160)),
                ("email", models.EmailField(max_length=254)),
                ("message", models.TextField()),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name_plural": "enquiries",
            },
        ),
        migrations.AddIndex(
            model_name="placement",
            index=models.Index(
                fields=["active", "audience", "slot"],
                name="marketing_p_active_a1b2c3_idx",
            ),
        ),
        migrations.RunPython(seed_default_placements, unseed_default_placements),
    ]
