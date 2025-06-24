from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('interviews', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='round',
            field=models.IntegerField(
                blank=True,
                help_text='Interview round (1-4). Leave null for questions available in all rounds.',
                null=True
            ),
        ),
    ]
