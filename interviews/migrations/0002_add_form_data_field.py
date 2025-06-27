# Generated migration to add form_data field for XForm integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interviews', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='interview',
            name='form_data',
            field=models.JSONField(
                blank=True, 
                null=True, 
                help_text='XForm data submitted for this interview'
            ),
        ),
    ]
