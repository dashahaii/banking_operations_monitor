from django.urls import path
from django.contrib import admin
from rest_framework.documentation import include_docs_urls
from . import views

# API URL patterns
api_patterns = [
    # Root endpoint
    path('', views.api_root, name='api-root'),
    
    # Resource management endpoints
    path('resources/', views.resource_list, name='resource-list'),
    path('resources/<int:pk>/', views.resource_detail, name='resource-detail'),
    path('resources/import/', views.import_resources, name='import-resources'),
    path('resources/process-reports/', views.process_resource_reports, name='process-resource-reports'),
    
    # Service management endpoints
    path('services/', views.service_list, name='service-list'),
    path('services/<int:pk>/', views.service_detail, name='service-detail'),
    path('services/import/', views.import_services, name='import-services'),
    path('services/analyze-dependencies/', views.analyze_dependencies, name='analyze-dependencies'),
    
    # Pricing and cost analysis endpoints
    path('pricing/', views.pricing_list, name='pricing-list'),
    path('pricing/update/', views.update_pricing, name='update-pricing'),
    path('services/<int:pk>/cost-analysis/', views.service_cost_analysis, name='service-cost-analysis'),
    
    # Metrics and monitoring endpoints
    path('metrics/export/', views.export_metrics, name='export-metrics'),
    path('alerts/', views.alerts_list, name='alerts-list'),
    path('alerts/<int:pk>/resolve/', views.resolve_alert, name='resolve-alert'),
]

urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),
    
    # API endpoints (v1)
    path('api/v1/', include(api_patterns)),
    
    # API documentation
    path('api/docs/', include_docs_urls(title='Banking IT Ops API', public=True)),
    
    # Prometheus metrics endpoint (for Django app metrics)
    path('metrics/', views.prometheus_metrics, name='prometheus-metrics'),
    
    # Healthcheck endpoint
    path('health/', views.health_check, name='health-check'),
]