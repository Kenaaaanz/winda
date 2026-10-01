from django.db import migrations, models
import django.db.models.deletion


def assign_existing_charges_to_creation_month(apps, schema_editor):
    BuildingSubscriptionCharge = apps.get_model('payments', 'BuildingSubscriptionCharge')
    for charge in BuildingSubscriptionCharge.objects.all().iterator():
        charge.billing_month = charge.created_at.strftime('%Y-%m')
        charge.save(update_fields=['billing_month'])


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0010_alter_buildingsubscriptioncharge_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='buildingsubscriptioncharge',
            name='billing_month',
            field=models.CharField(max_length=7, null=True),
        ),
        migrations.RunPython(assign_existing_charges_to_creation_month, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='buildingsubscriptioncharge',
            name='billing_month',
            field=models.CharField(max_length=7),
        ),
        migrations.AlterField(
            model_name='buildingsubscriptioncharge',
            name='property',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='building_subscription_charges',
                to='properties.property',
            ),
        ),
        migrations.AddConstraint(
            model_name='buildingsubscriptioncharge',
            constraint=models.UniqueConstraint(
                fields=('property', 'billing_month'),
                name='unique_property_building_charge_month',
            ),
        ),
        migrations.AlterModelOptions(
            name='buildingsubscriptioncharge',
            options={'ordering': ['-billing_month']},
        ),
    ]