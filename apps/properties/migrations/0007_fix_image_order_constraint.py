from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('properties', '0006_propertyimage_cloudinary_public_id_and_more'), 
    ]

    operations = [
        # Remove the unique_together constraint
        migrations.AlterUniqueTogether(
            name='propertyimage',
            unique_together=set(),
        ),
        # Add a new unique constraint with a different name
        migrations.AddConstraint(
            model_name='propertyimage',
            constraint=models.UniqueConstraint(
                fields=('property', 'order'),
                name='unique_property_image_order'
            ),
        ),
    ]