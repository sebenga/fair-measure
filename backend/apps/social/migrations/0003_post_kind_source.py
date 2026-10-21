from django.db import migrations, models


def _mark_announcements(apps, schema_editor) -> None:
    Post = apps.get_model("social", "Post")
    Post.objects.filter(is_announcement=True).update(kind="competition")


class Migration(migrations.Migration):
    dependencies = [
        ("social", "0002_alter_comment_body_commentmedia"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="kind",
            field=models.CharField(
                choices=[
                    ("profile", "Personal profile"),
                    ("competition", "Competition"),
                    ("live", "Live update"),
                ],
                db_index=True,
                default="profile",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="source_key",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["kind", "-created_at"], name="social_post_kind_c_idx"),
        ),
        migrations.AddConstraint(
            model_name="post",
            constraint=models.UniqueConstraint(
                condition=models.Q(("source_key__gt", "")),
                fields=("source_key",),
                name="uniq_post_source_key",
            ),
        ),
        migrations.RunPython(_mark_announcements, migrations.RunPython.noop),
    ]
