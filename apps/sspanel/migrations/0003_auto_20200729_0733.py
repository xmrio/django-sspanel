# Generated by Django 3.0.8 on 2020-07-28 23:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sspanel", "0002_auto_20200728_0821"),
    ]

    operations = [
        migrations.AddField(
            model_name="ssnode",
            name="enable_ehco_lb",
            field=models.BooleanField(
                db_index=True, default=True, verbose_name="是否负载均衡"
            ),
        ),
        migrations.AddField(
            model_name="vmessnode",
            name="enable_ehco_lb",
            field=models.BooleanField(
                db_index=True, default=True, verbose_name="是否负载均衡"
            ),
        ),
    ]
