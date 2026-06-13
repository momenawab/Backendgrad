# Generated migration for face recognition fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='worker',
            name='face_encoding',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='Cached 128-dimensional face encoding vector'
            ),
        ),
        migrations.AddField(
            model_name='worker',
            name='face_photo_valid',
            field=models.BooleanField(
                default=False,
                help_text='Whether the photo contains a valid detectable face'
            ),
        ),
    ]
