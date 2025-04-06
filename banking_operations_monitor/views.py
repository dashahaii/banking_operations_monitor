from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from django.views.decorators.http import require_GET
import pandas as pd
import json
import logging

from .models import Resource, Service, ResourcePricing, Alert, ServiceResourceDependency
from .services import (
    consolidate_resource_reports,
    generate_dependency_chain,
    get_service_list,
    fetch_pricing_for_all_resources,
    export_prometheus_metrics
)

logger = logging.getLogger(__name__)

@api_view(['GET'])
def api_root(request):
    """
    API root with links to available endpoints
    """
    return Response({
        'resources': '/api/v1/resources/',
        'services': '/api/v1/services/',
        'dependencies': '/api/v1/dependencies/',
        'alerts': '/api/v1/alerts/',
        'pricing': '/api/v1/pricing/',
        'metrics': '/api/v1/metrics/',
        'docs': '/api/docs/'
    })

# Resource management endpoints
@api_view(['GET'])
def resource_list(request):
    """
    List all resources or filter by category
    """
    category = request.query_params.get('category', None)
    
    if category:
        resources = Resource.objects.filter(category=category)
    else:
        resources = Resource.objects.all()
    
    data = [{
        'id': resource.id,
        'name': resource.name,
        'resource_id': resource.resource_id,
        'category': resource.category,
        'location': resource.location,
        'utilization': resource.current_utilization,
        'capacity': resource.total_capacity,
        'utilization_pct': resource.utilization_percentage(),
        'unit': resource.unit,
        'last_updated': resource.last_updated
    } for resource in resources]
    
    return Response(data)

# Pricing and cost analysis endpoints
@api_view(['GET'])
def pricing_list(request):
    """
    List pricing information for all resources
    """
    resource_category = request.query_params.get('category', None)
    
    if resource_category:
        pricing_data = ResourcePricing.objects.filter(resource__category=resource_category)
    else:
        pricing_data = ResourcePricing.objects.all()
    
    data = [{
        'resource_id': pricing.resource.id,
        'resource_name': pricing.resource.name,
        'category': pricing.resource.category,
        'list_price': pricing.list_price,
        'negotiated_price': pricing.negotiated_price,
        'recent_purchase_price': pricing.recent_purchase_price,
        'monthly_usage_cost': pricing.monthly_usage_cost,
        'vendor': pricing.vendor,
        'contract_expiry': pricing.contract_expiry
    } for pricing in pricing_data]
    
    return Response(data)

@api_view(['POST'])
def update_pricing(request):
    """
    Update pricing from vendor API
    """
    try:
        # Path parameters can be customized based on actual file locations
        result = fetch_pricing_for_all_resources(
            'data/resource_dependencies.csv',
            'data/services_list.csv',
            'data/resource_ids.json',
            'data/pricing_output.csv',
            datacenter=request.data.get('datacenter', 'PRIMARY')
        )
        
        if result is not None:
            return Response({
                'message': 'Pricing data updated successfully',
                'resources_updated': len(result)
            })
        else:
            return Response({
                'message': 'Pricing update failed or no data found',
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error updating pricing: {str(e)}")
        return Response({
            'error': f'Update failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def service_cost_analysis(request, pk):
    """
    Calculate the total cost of running a service
    """
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    # Get resource dependencies
    dependencies = ServiceResourceDependency.objects.filter(service=service)
    
    total_cost = 0
    resource_costs = []
    
    for dep in dependencies:
        try:
            pricing = ResourcePricing.objects.get(resource=dep.resource)
            if pricing.negotiated_price is not None:
                resource_price = float(pricing.negotiated_price)
            elif pricing.recent_purchase_price is not None:
                resource_price = float(pricing.recent_purchase_price)
            elif pricing.list_price is not None:
                resource_price = float(pricing.list_price)
            else:
                resource_price = 0
                
            cost = resource_price * dep.quantity_required
            total_cost += cost
            
            resource_costs.append({
                'resource_name': dep.resource.name,
                'resource_category': dep.resource.category,
                'quantity_required': dep.quantity_required,
                'unit_price': resource_price,
                'total_cost': cost,
                'vendor': pricing.vendor if pricing.vendor else 'Unknown',
                'contract_expiry': pricing.contract_expiry
            })
        except ResourcePricing.DoesNotExist:
            resource_costs.append({
                'resource_name': dep.resource.name,
                'resource_category': dep.resource.category,
                'quantity_required': dep.quantity_required,
                'unit_price': 'Unknown',
                'total_cost': 'Unknown',
                'vendor': 'Unknown',
                'contract_expiry': None
            })
    
    data = {
        'service_name': service.name,
        'service_criticality': service.criticality,
        'total_cost': total_cost,
        'resource_costs': resource_costs
    }
    
    return Response(data)

# Metrics and monitoring endpoints
@api_view(['GET'])
def export_metrics(request):
    """
    Export metrics for Prometheus
    """
    try:
        metrics = export_prometheus_metrics()
        return Response({
            'message': 'Metrics exported successfully',
            'metrics_count': len(metrics),
            'sample_metrics': metrics[:5] if metrics else []
        })
    except Exception as e:
        logger.error(f"Error exporting metrics: {str(e)}")
        return Response({
            'error': f'Export failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def alerts_list(request):
    """
    List all active alerts
    """
    severity = request.query_params.get('severity', None)
    resolved = request.query_params.get('resolved', 'false').lower() == 'true'
    
    alerts = Alert.objects.filter(is_resolved=resolved)
    
    if severity:
        alerts = alerts.filter(severity=severity)
    
    data = [{
        'id': alert.id,
        'title': alert.title,
        'description': alert.description,
        'alert_type': alert.alert_type,
        'severity': alert.severity,
        'resource_name': alert.resource.name if alert.resource else None,
        'service_name': alert.service.name if alert.service else None,
        'created_at': alert.created_at,
        'resolved_at': alert.resolved_at
    } for alert in alerts]
    
    return Response(data)

@api_view(['POST'])
def resolve_alert(request, pk):
    """
    Mark an alert as resolved
    """
    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    alert.resolve()
    
    return Response({
        'message': f'Alert "{alert.title}" marked as resolved',
        'resolved_at': alert.resolved_at
    })

@api_view(['GET'])
def resource_detail(request, pk):
    """
    Get detailed information about a specific resource
    """
    try:
        resource = Resource.objects.get(pk=pk)
    except Resource.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    # Get pricing information if available
    try:
        pricing = ResourcePricing.objects.get(resource=resource)
        pricing_data = {
            'list_price': pricing.list_price,
            'negotiated_price': pricing.negotiated_price,
            'recent_purchase_price': pricing.recent_purchase_price,
            'recent_quote_price': pricing.recent_quote_price,
            'average_market_price': pricing.average_market_price,
            'monthly_usage_cost': pricing.monthly_usage_cost,
            'last_price_update': pricing.last_price_update,
            'vendor': pricing.vendor,
            'contract_expiry': pricing.contract_expiry
        }
    except ResourcePricing.DoesNotExist:
        pricing_data = None
    
    # Get dependent services
    dependent_services = ServiceResourceDependency.objects.filter(resource=resource)
    service_data = [{
        'service_id': dep.service.id,
        'service_name': dep.service.name,
        'quantity_required': dep.quantity_required,
        'is_critical': dep.is_critical,
        'service_criticality': dep.service.criticality
    } for dep in dependent_services]
    
    data = {
        'id': resource.id,
        'name': resource.name,
        'resource_id': resource.resource_id,
        'category': resource.category,
        'location': resource.location,
        'utilization': resource.current_utilization,
        'capacity': resource.total_capacity,
        'utilization_pct': resource.utilization_percentage(),
        'unit': resource.unit,
        'last_updated': resource.last_updated,
        'pricing': pricing_data,
        'dependent_services': service_data
    }
    
    return Response(data)

@api_view(['POST'])
@csrf_exempt
def import_resources(request):
    """
    Import resources from CSV file
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']
    
    try:
        # Read the CSV file
        df = pd.read_csv(file)
        
        # Process the data
        resources_created = 0
        resources_updated = 0
        
        for _, row in df.iterrows():
            resource, created = Resource.objects.update_or_create(
                name=row['Resource'],
                defaults={
                    'resource_id': row.get('Resource_ID', None),
                    'category': row.get('Category', 'OTHER'),
                    'current_utilization': row.get('Utilization', 0),
                    'total_capacity': row.get('Capacity', 0),
                    'unit': row.get('Unit', 'count')
                }
            )
            
            if created:
                resources_created += 1
            else:
                resources_updated += 1
        
        return Response({
            'message': f'Import successful. Created {resources_created} new resources and updated {resources_updated} existing resources.',
            'created': resources_created,
            'updated': resources_updated
        })
        
    except Exception as e:
        logger.error(f"Error importing resources: {str(e)}")
        return Response({'error': f'Import failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def process_resource_reports(request):
    """
    Trigger processing of resource utilization reports
    """
    try:
        result = consolidate_resource_reports()
        if result is not None:
            return Response({
                'message': 'Resource reports processed successfully',
                'resources_processed': len(result)
            })
        else:
            return Response({
                'message': 'No resource reports found or processing failed',
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error processing resource reports: {str(e)}")
        return Response({
            'error': f'Processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Service management endpoints
@api_view(['GET'])
def service_list(request):
    """
    List all services or filter by criticality
    """
    criticality = request.query_params.get('criticality', None)
    
    if criticality:
        services = Service.objects.filter(criticality=criticality)
    else:
        services = Service.objects.all()
    
    data = [{
        'id': service.id,
        'name': service.name,
        'service_id': service.service_id,
        'description': service.description,
        'status': service.status,
        'criticality': service.criticality,
        'last_updated': service.last_updated
    } for service in services]
    
    return Response(data)

@api_view(['POST'])
def import_services(request):
    """
    Import services from CSV file
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']
    
    try:
        # Read the CSV file
        df = pd.read_csv(file)
        
        # Process the data
        services_created = 0
        services_updated = 0
        dependencies_created = 0
        
        for _, row in df.iterrows():
            service, created = Service.objects.update_or_create(
                name=row['Service'],
                defaults={
                    'criticality': row.get('Criticality', 'MEDIUM'),
                    'status': 'OPERATIONAL'
                }
            )
            
            if created:
                services_created += 1
            else:
                services_updated += 1
            
            # Process dependencies
            for i in range(1, 10, 2):  # Assuming dependency columns are in pairs
                dep_col = f'Dependency{i}'
                qty_col = f'Quantity{i}'
                
                if dep_col in row and qty_col in row and pd.notna(row[dep_col]):
                    resource_name = row[dep_col]
                    quantity = float(row[qty_col]) if pd.notna(row[qty_col]) else 1.0
                    
                    try:
                        resource = Resource.objects.get(name=resource_name)
                        
                        # Create or update the dependency
                        dep, dep_created = ServiceResourceDependency.objects.update_or_create(
                            service=service,
                            resource=resource,
                            defaults={
                                'quantity_required': quantity,
                                'is_critical': service.criticality == 'CRITICAL'
                            }
                        )
                        
                        if dep_created:
                            dependencies_created += 1
                            
                    except Resource.DoesNotExist:
                        logger.warning(f"Resource '{resource_name}' not found for service '{service.name}'")
        
        return Response({
            'message': f'Import successful. Created {services_created} new services, updated {services_updated} existing services, and created {dependencies_created} dependencies.',
            'services_created': services_created,
            'services_updated': services_updated,
            'dependencies_created': dependencies_created
        })
        
    except Exception as e:
        logger.error(f"Error importing services: {str(e)}")
        return Response({'error': f'Import failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def analyze_dependencies(request):
    """
    Trigger dependency chain analysis
    """
    try:
        # Path parameters can be customized based on actual file locations
        result = generate_dependency_chain(
            'data/total_services_dependencies.csv',
            'data/dependency_book.csv',
            'data/resource_location.csv',
            'data/output_dependencies.csv'
        )
        
        if result is not None:
            return Response({
                'message': 'Dependency analysis completed successfully',
                'resources_analyzed': len(result)
            })
        else:
            return Response({
                'message': 'Dependency analysis failed or no data found',
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error in dependency analysis: {str(e)}")
        return Response({
            'error': f'Analysis failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def service_detail(request, pk):
    """
    Get detailed information about a specific service
    """
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    # Get resource dependencies
    dependencies = ServiceResourceDependency.objects.filter(service=service)
    resource_data = [{
        'resource_id': dep.resource.id,
        'resource_name': dep.resource.name,
        'resource_category': dep.resource.category,
        'quantity_required': dep.quantity_required,
        'is_critical': dep.is_critical,
        'utilization': dep.resource.current_utilization,
        'capacity': dep.resource.total_capacity
    } for dep in dependencies]
    
    # Get active alerts for this service
    alerts = Alert.objects.filter(service=service, is_resolved=False)
    alert_data = [{
        'id': alert.id,
        'title': alert.title,
        'description': alert.description,
        'alert_type': alert.alert_type,
        'severity': alert.severity,
        'created_at': alert.created_at
    } for alert in alerts]
    
    data = {
        'id': service.id,
        'name': service.name,
        'service_id': service.service_id,
        'description': service.description,
        'status': service.status,
        'criticality': service.criticality,
        'last_updated': service.last_updated,
        'resource_dependencies': resource_data,
        'active_alerts': alert_data
    }
    
    return Response(data)


@require_GET
def prometheus_metrics(request):
    """
    Endpoint that exposes Django app metrics for Prometheus
    """
    metrics_page = generate_latest()
    return HttpResponse(
        metrics_page,
        content_type=CONTENT_TYPE_LATEST
    )

@require_GET
def health_check(request):
    """
    Simple health check endpoint for container orchestration systems
    """
    return HttpResponse(
        "OK",
        content_type="text/plain"
    )