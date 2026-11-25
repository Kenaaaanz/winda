from django.contrib import admin

from .models import UtilityDevice, UtilityReading, UtilityTariff


@admin.register(UtilityTariff)
class UtilityTariffAdmin(admin.ModelAdmin):
    list_display = (
        'utility',
        'provider',
        'unit',
        'rate_per_unit',
        'effective_from',
        'effective_until',
    )
    list_filter = ('utility', 'provider')
    search_fields = ('provider',)
    date_hierarchy = 'effective_from'


@admin.register(UtilityDevice)
class UtilityDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'unit', 'utility', 'provider', 'is_enabled')
    list_filter = ('utility', 'provider', 'is_enabled')
    search_fields = ('name', 'property__title', 'provider')
    readonly_fields = ('api_key_hash', 'created_at')


@admin.register(UtilityReading)
class UtilityReadingAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'recorded_at',
        'meter_value',
        'usage_delta',
        'rate_applied',
        'estimated_cost',
    )
    list_filter = ('device__utility', 'device__provider')
    search_fields = ('device__name', 'external_id')
    readonly_fields = tuple(field.name for field in UtilityReading._meta.fields)
    date_hierarchy = 'recorded_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
