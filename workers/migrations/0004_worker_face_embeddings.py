from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workers', '0003_worker_training_assigned'),
    ]

    operations = [
        migrations.AddField(
            model_name='worker',
            name='face_embeddings',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of L2-normalized face embedding vectors',
            ),
        ),
        migrations.AddField(
            model_name='worker',
            name='embedding_model',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Model id that produced the stored embeddings',
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='worker',
            name='face_encoding',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='Legacy 128-d dlib encoding (deprecated)',
            ),
        ),
    ]
