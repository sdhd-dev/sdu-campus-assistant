# Initial campus data schema, compatible with Django 5.2.17.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Block',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(choices=[('D', 'D'), ('E', 'E'), ('F', 'F'), ('G', 'G'), ('H', 'H'), ('I', 'I')], max_length=1, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('horizontal_order', models.PositiveSmallIntegerField(unique=True)),
                ('recommendation_status', models.CharField(choices=[('USER_REPORTED', 'Reported by the project team'), ('PROVISIONAL', 'Assumed from the block layout; needs checking'), ('UNKNOWN', 'Not established')], default='UNKNOWN', max_length=16)),
                ('recommendation_note', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['horizontal_order'],
            },
        ),
        migrations.CreateModel(
            name='Entrance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(choices=[('MAIN', 'Main entrance'), ('G', 'Block G entrance'), ('I', 'Block I entrance')], max_length=4, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('block', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='entrances', to='campus.block')),
            ],
        ),
        migrations.AddField(
            model_name='block',
            name='recommended_entrance',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recommended_for_blocks', to='campus.entrance'),
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=4, unique=True)),
                ('floor', models.PositiveSmallIntegerField(help_text='0 = basement; 1–4 = floors.')),
                ('kind', models.CharField(choices=[('UNKNOWN', 'Not classified'), ('CLASSROOM', 'Classroom'), ('STAFF_OFFICE', 'Staff office'), ('BARREL', 'Barrel lecture hall')], default='UNKNOWN', max_length=12)),
                ('name', models.CharField(blank=True, max_length=120)),
                ('aliases', models.JSONField(blank=True, default=list)),
                ('description', models.TextField(blank=True)),
                ('source', models.CharField(blank=True, max_length=200)),
                ('block', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rooms', to='campus.block')),
                ('recommended_entrance', models.ForeignKey(blank=True, help_text='Optional room-specific override of the block recommendation.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recommended_for_rooms', to='campus.entrance')),
            ],
            options={
                'ordering': ['block__horizontal_order', 'floor', 'code'],
            },
        ),
        migrations.AddConstraint(
            model_name='block',
            constraint=models.CheckConstraint(condition=models.Q(('code__in', ['D', 'E', 'F', 'G', 'H', 'I'])), name='campus_block_valid_code'),
        ),
        migrations.AddIndex(
            model_name='room',
            index=models.Index(fields=['block', 'floor'], name='campus_room_block_floor'),
        ),
        migrations.AddConstraint(
            model_name='room',
            constraint=models.CheckConstraint(condition=models.Q(('floor__gte', 0), ('floor__lte', 4)), name='campus_room_valid_floor'),
        ),
    ]
