from django.contrib import admin
from .models import SeoMeta, SeoRobots, SeoSitemap, SeoRedirect

@admin.register(SeoMeta)
class SeoMetaAdmin(admin.ModelAdmin):
    list_display = ['url_path', 'meta_title', 'meta_description']
    search_fields = ['url_path', 'meta_title']
    list_filter = ['created_at']
    fieldsets = (
        ('Page Information', {
            'fields': ('url_path', 'page_title')
        }),
        ('SEO Meta', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords')
        }),
        ('Social Media', {
            'fields': ('og_title', 'og_description', 'og_image', 'og_type')
        }),
        ('Twitter Card', {
            'fields': ('twitter_card', 'twitter_title', 'twitter_description', 'twitter_image')
        }),
        ('Advanced', {
            'fields': ('canonical_url', 'robots', 'structured_data')
        }),
    )

@admin.register(SeoRobots)
class SeoRobotsAdmin(admin.ModelAdmin):
    list_display = ['user_agent', 'is_active', 'created_at']

@admin.register(SeoSitemap)
class SeoSitemapAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'priority', 'changefreq', 'is_active']

@admin.register(SeoRedirect)
class SeoRedirectAdmin(admin.ModelAdmin):
    list_display = ['old_path', 'new_path', 'redirect_type', 'is_active']
    search_fields = ['old_path', 'new_path']