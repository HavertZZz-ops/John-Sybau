from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Slot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot', models.CharField(default='1', max_length=16, unique=True)),
                ('area', models.CharField(default='catacumbas', max_length=64)),
                ('x', models.FloatField(default=0.0)),
                ('y', models.FloatField(default=0.0)),
                ('direcao', models.CharField(default='sul', max_length=8)),
                ('tempo_jogado', models.FloatField(default=0.0)),
                ('versao', models.IntegerField(default=1)),
                ('extra', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'slot de save',
                'verbose_name_plural': 'slots de save',
                'ordering': ['-atualizado_em'],
            },
        ),
    ]
