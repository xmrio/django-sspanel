# Generated by Django 3.0.6 on 2020-06-22 23:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sspanel", "0050_auto_20200621_1813"),
    ]

    operations = [
        migrations.RemoveField(model_name="relaynode", name="ehco_listen_host",),
        migrations.RemoveField(model_name="relaynode", name="ehco_listen_port",),
        migrations.RemoveField(model_name="relaynode", name="ehco_listen_type",),
        migrations.RemoveField(model_name="relaynode", name="ehco_transport_type",),
        migrations.RemoveField(model_name="relaynode", name="enlarge_scale",),
        migrations.RemoveField(model_name="relaynode", name="info",),
        migrations.RemoveField(model_name="relaynode", name="level",),
    ]
