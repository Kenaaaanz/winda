from django.urls import path, re_path
from . import views

app_name = 'seo'

urlpatterns = [
    # Sitemaps
    path('sitemap.xml', views.sitemap_xml, name='sitemap'),
    path('sitemap-index.xml', views.sitemap_index, name='sitemap_index'),
    re_path(r'^sitemap-properties-(\d+)\.xml$', views.property_sitemap, name='property_sitemap'),
    
    # Robots
    path('robots.txt', views.robots_txt, name='robots'),
    
    ]