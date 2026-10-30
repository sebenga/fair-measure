from django.db import migrations, models

# The sponsors seeded in 0001 get a showcase photo and a line of copy, unless an
# admin has already filled them in.
SEEDED = {
    "Pitchside": (
        "assets/landing/corp-merch.jpg",
        "Match kit, training wear and merchandise in your league’s colours.",
    ),
    "Harbour Radio": (
        "assets/landing/gov-programme.jpg",
        "Live commentary and results from community grounds every weekend.",
    ),
    "Millwater": (
        "assets/landing/hero.jpg",
        "Cold water on the touchline at every match day and fun run.",
    ),
    "Northstand": (
        "assets/landing/moment-fans.jpg",
        "Backing the clubs, schools and supporters who fill the stands.",
    ),
    "Ledger & Co": (
        "assets/landing/moment-office.jpg",
        "Sponsor of the after-work five-a-side and the quarterly KPI cup.",
    ),
}


def fill_seeded_sponsors(apps, schema_editor):
    Placement = apps.get_model("marketing", "Placement")
    for name, (image, body) in SEEDED.items():
        for row in Placement.objects.filter(slot="logo", name=name):
            changed = []
            if not row.image_url:
                row.image_url = image
                changed.append("image_url")
            if not row.body:
                row.body = body
                changed.append("body")
            if changed:
                row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("marketing", "0003_rename_marketing_p_active_a1b2c3_idx_marketing_p_active_754b56_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="placement",
            name="image_url",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.RunPython(fill_seeded_sponsors, migrations.RunPython.noop),
    ]
