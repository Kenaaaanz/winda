from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class SeoMeta(models.Model):
    """SEO Meta data for pages"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Page identification
    url_path = models.CharField(max_length=500, unique=True, help_text='URL path (e.g., /properties/)')
    page_title = models.CharField(max_length=200, help_text='Browser tab title')
    meta_title = models.CharField(max_length=70, help_text='SEO Title (max 60-70 chars)')
    meta_description = models.CharField(max_length=160, help_text='SEO Description (max 160 chars)')
    meta_keywords = models.CharField(max_length=255, blank=True, help_text='Comma separated keywords')
    
    # Social Media (Open Graph)
    og_title = models.CharField(max_length=200, blank=True)
    og_description = models.CharField(max_length=200, blank=True)
    og_image = models.URLField(blank=True, null=True)
    og_type = models.CharField(max_length=50, default='website')
    
    # Twitter Card
    twitter_card = models.CharField(max_length=50, default='summary_large_image')
    twitter_title = models.CharField(max_length=200, blank=True)
    twitter_description = models.CharField(max_length=200, blank=True)
    twitter_image = models.URLField(blank=True, null=True)
    
    # Additional SEO
    canonical_url = models.URLField(blank=True, null=True)
    robots = models.CharField(max_length=100, default='index, follow')
    
    # Schema.org structured data
    structured_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seo_meta'
        verbose_name = 'SEO Meta'
        verbose_name_plural = 'SEO Meta'
    
    def __str__(self):
        return self.url_path


class SeoRobots(models.Model):
    """Robots.txt configuration"""
    user_agent = models.CharField(max_length=100, default='*')
    allow = models.TextField(blank=True)
    disallow = models.TextField(blank=True)
    sitemap = models.URLField(blank=True, null=True)
    crawl_delay = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seo_robots'
        verbose_name = 'Robots.txt'
        verbose_name_plural = 'Robots.txt'
    
    def __str__(self):
        return f"User-agent: {self.user_agent}"


class SeoSitemap(models.Model):
    """Sitemap configuration"""
    name = models.CharField(max_length=100)
    url = models.URLField()
    priority = models.DecimalField(max_digits=3, decimal_places=2, default=0.5)
    changefreq = models.CharField(
        max_length=20,
        choices=[
            ('always', 'Always'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
            ('never', 'Never'),
        ],
        default='weekly'
    )
    is_active = models.BooleanField(default=True)
    last_modified = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seo_sitemap'
    
    def __str__(self):
        return self.name


class SeoRedirect(models.Model):
    """URL redirects for SEO"""
    REDIRECT_TYPES = (
        ('301', 'Moved Permanently'),
        ('302', 'Found (Temporary)'),
    )
    
    old_path = models.CharField(max_length=500, unique=True)
    new_path = models.CharField(max_length=500)
    redirect_type = models.CharField(max_length=3, choices=REDIRECT_TYPES, default='301')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seo_redirects'
    
    def __str__(self):
        return f"{self.old_path} → {self.new_path}"