from datetime import timezone

from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.template import loader
from django.core.paginator import Paginator
from django.db.models import Q
import json

from .models import SeoSitemap, SeoRobots
from apps.properties.models import Property
from apps.tenants.models import TenantApplication

def robots_txt(request):
    """Generate robots.txt dynamically"""
    robots_data = SeoRobots.objects.filter(is_active=True)
    
    lines = []
    for rule in robots_data:
        lines.append(f"User-agent: {rule.user_agent}")
        if rule.allow:
            for allow in rule.allow.split('\n'):
                if allow.strip():
                    lines.append(f"Allow: {allow.strip()}")
        if rule.disallow:
            for disallow in rule.disallow.split('\n'):
                if disallow.strip():
                    lines.append(f"Disallow: {disallow.strip()}")
        if rule.crawl_delay:
            lines.append(f"Crawl-delay: {rule.crawl_delay}")
        if rule.sitemap:
            lines.append(f"Sitemap: {rule.sitemap}")
        lines.append("")
    
    if not lines:
        # Default robots.txt
        lines = [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /accounts/profile/",
            "Disallow: /accounts/login/",
            "Disallow: /accounts/register/",
            "Disallow: /tenants/owner/",
            "Disallow: /payments/callback/",
            f"Sitemap: https://www.winda.africa/sitemap.xml",
            "",
            "User-agent: Googlebot",
            "Allow: /",
            "Crawl-delay: 1",
            "",
            "User-agent: Bingbot",
            "Allow: /",
            "Crawl-delay: 2",
        ]
    
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    """Generate sitemap.xml dynamically"""
    # Get all active properties
    properties = Property.objects.filter(
        verification_status='VERIFIED'
    ).order_by('-created_at')
    
    property_urls = []
    for prop in properties[:500]:  # Limit to 500 for performance
        property_urls.append({
            'loc': f'/properties/{prop.id}/',
            'lastmod': prop.updated_at.isoformat(),
            'changefreq': 'daily',
            'priority': '0.8',
        })
    
    # Get static pages
    static_pages = [
        {'loc': '/', 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': '/properties/', 'changefreq': 'daily', 'priority': '0.9'},
        {'loc': '/about/', 'changefreq': 'monthly', 'priority': '0.5'},
        {'loc': '/contact/', 'changefreq': 'monthly', 'priority': '0.5'},
        {'loc': '/faq/', 'changefreq': 'monthly', 'priority': '0.4'},
        {'loc': '/how-it-works/', 'changefreq': 'monthly', 'priority': '0.6'},
    ]
    
    # Get sitemap entries from database
    db_entries = SeoSitemap.objects.filter(is_active=True)
    
    for entry in db_entries:
        static_pages.append({
            'loc': entry.url,
            'lastmod': entry.last_modified.isoformat(),
            'changefreq': entry.changefreq,
            'priority': str(entry.priority),
        })
    
    all_urls = static_pages + property_urls
    
    # Build XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for url in all_urls:
        xml += '  <url>\n'
        xml += f'    <loc>https://www.winda.africa{url["loc"]}</loc>\n'
        if 'lastmod' in url:
            xml += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
        if 'changefreq' in url:
            xml += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
        if 'priority' in url:
            xml += f'    <priority>{url["priority"]}</priority>\n'
        xml += '  </url>\n'
    
    xml += '</urlset>'
    
    return HttpResponse(xml, content_type="application/xml")


def sitemap_index(request):
    """Generate sitemap index for large sites"""
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # Main sitemap
    xml += '  <sitemap>\n'
    xml += '    <loc>https://www.winda.africa/sitemap.xml</loc>\n'
    xml += f'    <lastmod>{timezone.now().isoformat()}</lastmod>\n'
    xml += '  </sitemap>\n'
    
    # Property sitemaps (paginated)
    total_properties = Property.objects.filter(verification_status='VERIFIED').count()
    per_page = 1000
    total_pages = (total_properties // per_page) + 1
    
    for i in range(1, total_pages + 1):
        xml += '  <sitemap>\n'
        xml += f'    <loc>https://www.winda.africa/sitemap-properties-{i}.xml</loc>\n'
        xml += f'    <lastmod>{timezone.now().isoformat()}</lastmod>\n'
        xml += '  </sitemap>\n'
    
    xml += '</sitemapindex>'
    
    return HttpResponse(xml, content_type="application/xml")


def property_sitemap(request, page=1):
    """Generate property-specific sitemap pages"""
    properties = Property.objects.filter(
        verification_status='VERIFIED'
    ).order_by('-created_at')
    
    paginator = Paginator(properties, 1000)
    page_obj = paginator.get_page(page)
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for prop in page_obj:
        xml += '  <url>\n'
        xml += f'    <loc>https://www.winda.africa/properties/{prop.id}/</loc>\n'
        xml += f'    <lastmod>{prop.updated_at.isoformat()}</lastmod>\n'
        xml += '    <changefreq>daily</changefreq>\n'
        xml += '    <priority>0.8</priority>\n'
        xml += '  </url>\n'
    
    xml += '</urlset>'
    
    return HttpResponse(xml, content_type="application/xml")