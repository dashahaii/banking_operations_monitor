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
from bson import ObjectId
from datetime import datetime
from bson.json_util import dumps, loads

# Import our PyMongo model managers
from .models import (
    ResourceManager, 
    ServiceManager, 
    DependencyManager, 
    PricingManager, 
    UsageHistoryManager, 
    AlertManager
)
from .services import (
    consolidate_resource_reports,
    generate_dependency_chain,
    get_service_list,
    fetch_pricing_for_all_resources,
    export_prometheus_metrics
)

logger = logging.getLogger(__name__)

# Helper function to serialize MongoDB documents
def serialize_document(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
        
    # Handle ObjectId
    if '_id' in doc:
        doc['id'] = str(doc['_id'])
        del doc['_id']
    
    # Handle datetime objects
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, ObjectId):
            doc[key] = str(value)
    
    return doc

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
    
    resources = ResourceManager.find_all(category=category)
    
    data = []
    for resource in resources:
        resource_dict = serialize_document(resource)
        # Add utilization percentage
        resource_dict['utilization_pct'] = ResourceManager.utilization_percentage(resource)
        data.append(resource_dict)
    
    return Response(data)

@api_view(['GET'])
def resource_detail(request, pk):
    """
    Get detailed information about a specific resource
    """
    try:
        resource = ResourceManager.find_by_id(pk)
        if not resource:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        # Get pricing information if available
        pricing = PricingManager.find_by_resource(resource['_id'])
        pricing_data = serialize_document(pricing) if pricing else None
        
        # Get dependent services
        dependencies = DependencyManager.find_by_resource(resource['_id'])
        service_data = []
        
        for dep in dependencies:
            service = ServiceManager.find_by_id(dep['service_id'])
            if service:
                service_data.append({
                    'service_id': str(service['_id']),
                    'service_name': service['name'],
                    'quantity_required': dep['quantity_required'],
                    'is_critical': dep['is_critical'],
                    'service_criticality': service.get('criticality', 'MEDIUM')
                })
        
        # Serialize the resource
        data = serialize_document(resource)
        
        # Add utilization percentage
        data['utilization_pct'] = ResourceManager.utilization_percentage(resource)
        
        # Add related data
        data['pricing'] = pricing_data
        data['dependent_services'] = service_data
        
        return Response(data)
    except Exception as e:
        logger.error(f"Error retrieving resource details: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            resource_name = row['Resource']
            
            # Check if resource exists
            existing_resource = ResourceManager.find_by_name(resource_name)
            
            if existing_resource:
                # Update existing resource
                ResourceManager.update(
                    existing_resource['_id'],
                    resource_id=row.get('Resource_ID', None),
                    category=row.get('Category', 'OTHER'),
                    current_utilization=row.get('Utilization', 0),
                    total_capacity=row.get('Capacity', 0),
                    unit=row.get('Unit', 'count')
                )
                resources_updated += 1
            else:
                # Create new resource
                ResourceManager.create(
                    name=resource_name,
                    resource_id=row.get('Resource_ID', None),
                    category=row.get('Category', 'OTHER'),
                    current_utilization=row.get('Utilization', 0),
                    total_capacity=row.get('Capacity', 0),
                    unit=row.get('Unit', 'count')
                )
                resources_created += 1
        
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
    
    services = ServiceManager.find_all(criticality=criticality)
    
    data = [serialize_document(service) for service in services]
    
    return Response(data)

@api_view(['GET'])
def service_detail(request, pk):
    """
    Get detailed information about a specific service
    """
    try:
        service = ServiceManager.find_by_id(pk)
        if not service:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        # Get resource dependencies
        dependencies = DependencyManager.find_by_service(service['_id'])
        resource_data = []
        
        for dep in dependencies:
            resource = ResourceManager.find_by_id(dep['resource_id'])
            if resource:
                resource_data.append({
                    'resource_id': str(resource['_id']),
                    'resource_name': resource['name'],
                    'resource_category': resource.get('category', 'OTHER'),
                    'quantity_required': dep['quantity_required'],
                    'is_critical': dep['is_critical'],
                    'utilization': resource.get('current_utilization', 0),
                    'capacity': resource.get('total_capacity', 0)
                })
        
        # Get active alerts for this service
        alerts = AlertManager.find_by_service(service['_id'], resolved=False)
        alert_data = [serialize_document(alert) for alert in alerts]
        
        # Serialize the service
        data = serialize_document(service)
        
        # Add related data
        data['resource_dependencies'] = resource_data
        data['active_alerts'] = alert_data
        
        return Response(data)
    except Exception as e:
        logger.error(f"Error retrieving service details: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            service_name = row['Service']
            
            # Check if service exists
            existing_service = ServiceManager.find_by_name(service_name)
            
            if existing_service:
                # Update existing service
                ServiceManager.update(
                    existing_service['_id'],
                    criticality=row.get('Criticality', 'MEDIUM'),
                    status='OPERATIONAL'
                )
                service_id = existing_service['_id']
                services_updated += 1
            else:
                # Create new service
                service_id = ServiceManager.create(
                    name=service_name,
                    criticality=row.get('Criticality', 'MEDIUM'),
                    status='OPERATIONAL'
                )
                services_created += 1
            
            # Process dependencies
            for i in range(1, 10, 2):  # Assuming dependency columns are in pairs
                dep_col = f'Dependency{i}'
                qty_col = f'Quantity{i}'
                
                if dep_col in row and qty_col in row and pd.notna(row[dep_col]):
                    resource_name = row[dep_col]
                    quantity = float(row[qty_col]) if pd.notna(row[qty_col]) else 1.0
                    
                    # Find resource by name
                    resource = ResourceManager.find_by_name(resource_name)
                    
                    if resource:
                        # Create dependency
                        DependencyManager.create(
                            service_id=service_id,
                            resource_id=resource['_id'],
                            quantity_required=quantity,
                            is_critical=row.get('Criticality', 'MEDIUM') == 'CRITICAL'
                        )
                        dependencies_created += 1
                    else:
                        logger.warning(f"Resource '{resource_name}' not found for service '{service_name}'")
        
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

# Pricing and cost analysis endpoints
@api_view(['GET'])
def pricing_list(request):
    """
    List pricing information for all resources
    """
    resource_category = request.query_params.get('category', None)
    
    pricing_data = PricingManager.find_all()
    data = []
    
    for pricing in pricing_data:
        resource = ResourceManager.find_by_id(pricing['resource_id'])
        if resource:
            # Skip if category filter is applied and doesn't match
            if resource_category and resource.get('category') != resource_category:
                continue
                
            pricing_entry = serialize_document(pricing)
            pricing_entry['resource_name'] = resource['name']
            pricing_entry['category'] = resource.get('category', 'OTHER')
            data.append(pricing_entry)
    
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
        service = ServiceManager.find_by_id(pk)
        if not service:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        # Get resource dependencies
        dependencies = DependencyManager.find_by_service(service['_id'])
        
        total_cost = 0
        resource_costs = []
        
        for dep in dependencies:
            resource = ResourceManager.find_by_id(dep['resource_id'])
            if not resource:
                continue
                
            pricing = PricingManager.find_by_resource(resource['_id'])
            
            if pricing:
                if pricing.get('negotiated_price') is not None:
                    resource_price = float(pricing['negotiated_price'])
                elif pricing.get('recent_purchase_price') is not None:
                    resource_price = float(pricing['recent_purchase_price'])
                elif pricing.get('list_price') is not None:
                    resource_price = float(pricing['list_price'])
                else:
                    resource_price = 0
                    
                cost = resource_price * dep['quantity_required']
                total_cost += cost
                
                resource_costs.append({
                    'resource_name': resource['name'],
                    'resource_category': resource.get('category', 'OTHER'),
                    'quantity_required': dep['quantity_required'],
                    'unit_price': resource_price,
                    'total_cost': cost,
                    'vendor': pricing.get('vendor', 'Unknown'),
                    'contract_expiry': pricing.get('contract_expiry')
                })
            else:
                resource_costs.append({
                    'resource_name': resource['name'],
                    'resource_category': resource.get('category', 'OTHER'),
                    'quantity_required': dep['quantity_required'],
                    'unit_price': 'Unknown',
                    'total_cost': 'Unknown',
                    'vendor': 'Unknown',
                    'contract_expiry': None
                })
        
        data = {
            'service_name': service['name'],
            'service_criticality': service.get('criticality', 'MEDIUM'),
            'total_cost': total_cost,
            'resource_costs': resource_costs
        }
        
        return Response(data)
    except Exception as e:
        logger.error(f"Error calculating service cost: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    
    alerts = AlertManager.find_all(resolved=resolved, severity=severity)
    
    data = []
    for alert in alerts:
        alert_dict = serialize_document(alert)
        
        # Add resource/service names
        if alert.get('resource_id'):
            resource = ResourceManager.find_by_id(alert['resource_id'])
            if resource:
                alert_dict['resource_name'] = resource['name']
        
        if alert.get('service_id'):
            service = ServiceManager.find_by_id(alert['service_id'])
            if service:
                alert_dict['service_name'] = service['name']
                
        data.append(alert_dict)
    
    return Response(data)

@api_view(['POST'])
def resolve_alert(request, pk):
    """
    Mark an alert as resolved
    """
    try:
        alert = AlertManager.find_by_id(pk)
        if not alert:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        AlertManager.resolve(pk)
        
        # Fetch updated alert
        updated_alert = AlertManager.find_by_id(pk)
        
        return Response({
            'message': f'Alert "{alert["title"]}" marked as resolved',
            'resolved_at': updated_alert.get('resolved_at')
        })
    except Exception as e:
        logger.error(f"Error resolving alert: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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