from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fixtures", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="scoreevent",
            name="unit_index",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
