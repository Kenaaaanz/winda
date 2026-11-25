import builtins
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class UtilityTariff(models.Model):
    UTILITY_TYPES = (
        ('WATER', 'Water'),
        ('SEWERAGE', 'Sewerage'),
        ('ELECTRICITY', 'Electricity'),
    )

    utility = models.CharField(max_length=20, choices=UTILITY_TYPES)
    provider = models.CharField(max_length=150)
    unit = models.CharField(max_length=10)
    rate_per_unit = models.DecimalField(max_digits=12, decimal_places=4)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    reference_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['utility', 'provider', '-effective_from']
        constraints = [
            models.UniqueConstraint(
                fields=['utility', 'provider', 'effective_from'],
                name='unique_utility_tariff_start',
            ),
        ]

    def clean(self):
        super().clean()
        if self.rate_per_unit is not None and self.rate_per_unit < 0:
            raise ValidationError({'rate_per_unit': 'The rate cannot be negative.'})
        if (
            self.effective_from
            and self.effective_until
            and self.effective_until <= self.effective_from
        ):
            raise ValidationError({
                'effective_until': 'The end date must be after the start date.'
            })

        if self.utility == 'ELECTRICITY' and self.unit != 'kWh':
            raise ValidationError({'unit': 'Electricity tariffs must use kWh.'})
        if self.utility in {'WATER', 'SEWERAGE'} and self.unit != 'm3':
            raise ValidationError({'unit': 'Water and sewerage tariffs must use m3.'})

        overlaps = UtilityTariff.objects.filter(
            utility=self.utility,
            provider=self.provider,
        ).exclude(pk=self.pk)
        if self.effective_until:
            overlaps = overlaps.filter(effective_from__lt=self.effective_until)
        if self.effective_from:
            overlaps = overlaps.filter(
                Q(effective_until__isnull=True)
                | Q(effective_until__gt=self.effective_from)
            )
        if overlaps.exists():
            raise ValidationError(
                'Tariff periods for the same utility and provider cannot overlap.'
            )

    def __str__(self):
        return f'{self.provider} {self.get_utility_display()} ({self.effective_from:%Y-%m-%d})'


class UtilityDevice(models.Model):
    UTILITY_TYPES = UtilityTariff.UTILITY_TYPES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='utility_devices',
    )
    unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.CASCADE,
        related_name='utility_devices',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    utility = models.CharField(max_length=20, choices=UTILITY_TYPES)
    provider = models.CharField(max_length=150)
    initial_reading = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    api_key_hash = models.CharField(max_length=64, editable=False)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['property__title', 'name']

    @builtins.property
    def unit_of_measure(self):
        return 'kWh' if self.utility == 'ELECTRICITY' else 'm3'

    def clean(self):
        super().clean()
        if self.unit_id and self.property_id and self.unit.property_obj_id != self.property_id:
            raise ValidationError({'unit': 'The selected unit must belong to this property.'})
        if self.initial_reading is not None and self.initial_reading < 0:
            raise ValidationError({'initial_reading': 'The initial reading cannot be negative.'})

    def __str__(self):
        return f'{self.name} - {self.property}'


class UtilityReading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        UtilityDevice,
        on_delete=models.CASCADE,
        related_name='readings',
    )
    external_id = models.CharField(max_length=100)
    meter_value = models.DecimalField(max_digits=18, decimal_places=3)
    usage_delta = models.DecimalField(max_digits=18, decimal_places=3)
    recorded_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    tariff = models.ForeignKey(
        UtilityTariff,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='readings',
    )
    rate_applied = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['recorded_at']
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'external_id'],
                name='unique_device_reading_external_id',
            ),
        ]

    def __str__(self):
        return f'{self.device} - {self.meter_value} {self.device.unit_of_measure}'
