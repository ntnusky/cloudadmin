# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=50)),
                ('description', models.TextField()),
                ('projectprefix', models.CharField(max_length=50)),
                ('groups', models.ManyToManyField(to='auth.Group')),
                ('parent', models.ForeignKey(null=True, default=None, on_delete=django.db.models.deletion.PROTECT, to='cloudadmin.Project')),
            ],
        ),
        migrations.CreateModel(
            name='Quota',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('cpu_cores', models.IntegerField(default=0)),
                ('ram_gb', models.IntegerField(default=0)),
                ('cinder_gb', models.IntegerField(default=0)),
                ('cinder_volumes', models.IntegerField(default=0)),
                ('swift_gb', models.IntegerField(default=0)),
                ('swift_objects', models.IntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='QuotaTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('cpu_cores', models.IntegerField(default=0)),
                ('ram_gb', models.IntegerField(default=0)),
                ('cinder_gb', models.IntegerField(default=0)),
                ('cinder_volumes', models.IntegerField(default=0)),
                ('swift_gb', models.IntegerField(default=0)),
                ('swift_objects', models.IntegerField(default=0)),
                ('name', models.CharField(max_length=50)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('default', models.BooleanField(default=False)),
                ('project', models.ForeignKey(null=True, default=None, to='cloudadmin.Project')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Token',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('cpu_cores', models.IntegerField(default=0)),
                ('ram_gb', models.IntegerField(default=0)),
                ('cinder_gb', models.IntegerField(default=0)),
                ('cinder_volumes', models.IntegerField(default=0)),
                ('swift_gb', models.IntegerField(default=0)),
                ('swift_objects', models.IntegerField(default=0)),
                ('value', models.CharField(max_length=32)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(null=True, auto_now=True)),
                ('expiry', models.DateTimeField()),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Usage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('cpu_cores', models.IntegerField(default=0)),
                ('ram_gb', models.IntegerField(default=0)),
                ('cinder_gb', models.IntegerField(default=0)),
                ('cinder_volumes', models.IntegerField(default=0)),
                ('swift_gb', models.IntegerField(default=0)),
                ('swift_objects', models.IntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='project',
            name='quota',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='cloudadmin.Quota'),
        ),
        migrations.AddField(
            model_name='project',
            name='usage',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='cloudadmin.Usage'),
        ),
    ]
