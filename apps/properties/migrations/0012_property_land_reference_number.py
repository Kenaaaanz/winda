from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('properties', '0011_alter_property_bathrooms_alter_property_bedrooms_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='land_reference_number',
            field=models.CharField(
                blank=True,
                help_text='Land reference number (L.R. No.) from the land registrar.',
                max_length=100,
                null=True,
            ),
        ),
    ]