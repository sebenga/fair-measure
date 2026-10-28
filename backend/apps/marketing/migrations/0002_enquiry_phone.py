from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="enquiry",
            name="phone",
            field=models.CharField(default="", max_length=32),
            preserve_default=False,
        ),
    ]
