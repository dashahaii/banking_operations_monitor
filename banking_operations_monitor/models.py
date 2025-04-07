from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, ASCENDING
import os
from decimal import Decimal

# MongoDB connection settings
MONGODB_HOST = os.environ.get('MONGODB_HOST', 'mongodb')
MONGODB_PORT = int(os.environ.get('MONGODB_PORT', 27017))
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'banking_operations_monitor')
MONGODB_USERNAME = os.environ.get('MONGODB_USERNAME', '')
MONGODB_PASSWORD = os.environ.get('MONGODB_PASSWORD', '')

# Establish MongoDB connection
client = MongoClient(
    host=MONGODB_HOST,
    port=MONGODB_PORT,
    username=MONGODB_USERNAME or None,
    password=MONGODB_PASSWORD or None,
    authSource='admin' if MONGODB_USERNAME else None
)

# Get database
db = client[MONGODB_DATABASE]

# Define collections
resources_collection = db.resources
services_collection = db.services
dependencies_collection = db.dependencies
pricing_collection = db.pricing
usage_history_collection = db.usage_history
alerts_collection = db.alerts

# Create indexes
resources_collection.create_index([("name", ASCENDING)], unique=True)
services_collection.create_index([("name", ASCENDING)], unique=True)
dependencies_collection.create_index([("service_id", ASCENDING), ("resource_id", ASCENDING)], unique=True)

# Resource Management
class ResourceManager:
    CATEGORY_CHOICES = [
        'COMPUTE', 'STORAGE', 'NETWORK', 'LICENSE', 'SERVICE', 'OTHER'
    ]
    
    @staticmethod
    def create(name, category, resource_id=None, location=None, 
              current_utilization=0, total_capacity=0, unit='count'):
        """Create a new resource"""
        if category not in ResourceManager.CATEGORY_CHOICES:
            raise ValueError(f"Category must be one of {ResourceManager.CATEGORY_CHOICES}")
            
        resource = {
            'name': name,
            'resource_id': resource_id,
            'category': category,
            'location': location,
            'current_utilization': float(current_utilization),
            'total_capacity': float(total_capacity),
            'unit': unit,
            'last_updated': datetime.now()
        }
        return resources_collection.insert_one(resource).inserted_id
    
    @staticmethod
    def find_by_id(resource_id):
        """Find resource by ID"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        return resources_collection.find_one({'_id': resource_id})
    
    @staticmethod
    def find_by_name(name):
        """Find resource by name"""
        return resources_collection.find_one({'name': name})
    
    @staticmethod
    def find_all(category=None, limit=100, skip=0):
        """Find all resources, optionally filtered by category"""
        query = {'category': category} if category else {}
        return list(resources_collection.find(query).skip(skip).limit(limit))
    
    @staticmethod
    def update(resource_id, **kwargs):
        """Update resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        # Add last_updated timestamp
        kwargs['last_updated'] = datetime.now()
        
        # Convert numeric values to float
        for key in ['current_utilization', 'total_capacity']:
            if key in kwargs:
                kwargs[key] = float(kwargs[key])
        
        return resources_collection.update_one(
            {'_id': resource_id},
            {'$set': kwargs}
        )
    
    @staticmethod
    def delete(resource_id):
        """Delete resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        # Delete related data
        dependencies_collection.delete_many({'resource_id': resource_id})
        pricing_collection.delete_many({'resource_id': resource_id})
        usage_history_collection.delete_many({'resource_id': resource_id})
        alerts_collection.delete_many({'resource_id': resource_id})
        
        return resources_collection.delete_one({'_id': resource_id})
    
    @staticmethod
    def utilization_percentage(resource):
        """Calculate utilization percentage"""
        if resource.get('total_capacity', 0) > 0:
            return (resource.get('current_utilization', 0) / resource['total_capacity']) * 100
        return 0

# Service Management
class ServiceManager:
    STATUS_CHOICES = [
        'OPERATIONAL', 'DEGRADED', 'PARTIAL_OUTAGE', 'MAJOR_OUTAGE', 'MAINTENANCE'
    ]
    
    CRITICALITY_CHOICES = [
        'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    ]
    
    @staticmethod
    def create(name, service_id=None, description=None, status='OPERATIONAL', criticality='MEDIUM'):
        """Create a new service"""
        if status not in ServiceManager.STATUS_CHOICES:
            raise ValueError(f"Status must be one of {ServiceManager.STATUS_CHOICES}")
            
        if criticality not in ServiceManager.CRITICALITY_CHOICES:
            raise ValueError(f"Criticality must be one of {ServiceManager.CRITICALITY_CHOICES}")
            
        service = {
            'name': name,
            'service_id': service_id,
            'description': description,
            'status': status,
            'criticality': criticality,
            'last_updated': datetime.now()
        }
        return services_collection.insert_one(service).inserted_id
    
    @staticmethod
    def find_by_id(service_id):
        """Find service by ID"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return None
        return services_collection.find_one({'_id': service_id})
    
    @staticmethod
    def find_by_name(name):
        """Find service by name"""
        return services_collection.find_one({'name': name})
    
    @staticmethod
    def find_all(criticality=None, status=None, limit=100, skip=0):
        """Find all services, optionally filtered"""
        query = {}
        if criticality:
            query['criticality'] = criticality
        if status:
            query['status'] = status
            
        return list(services_collection.find(query).skip(skip).limit(limit))
    
    @staticmethod
    def update(service_id, **kwargs):
        """Update service"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return None
        
        # Add last_updated timestamp
        kwargs['last_updated'] = datetime.now()
        
        return services_collection.update_one(
            {'_id': service_id},
            {'$set': kwargs}
        )
    
    @staticmethod
    def delete(service_id):
        """Delete service"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return None
        
        # Delete related data
        dependencies_collection.delete_many({'service_id': service_id})
        alerts_collection.delete_many({'service_id': service_id})
        
        return services_collection.delete_one({'_id': service_id})

# Service Resource Dependency Management
class DependencyManager:
    @staticmethod
    def create(service_id, resource_id, quantity_required=1.0, is_critical=False):
        """Create a new dependency"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return None
                
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        dependency = {
            'service_id': service_id,
            'resource_id': resource_id,
            'quantity_required': float(quantity_required),
            'is_critical': bool(is_critical)
        }
        
        # Upsert to handle potential duplicates
        result = dependencies_collection.update_one(
            {'service_id': service_id, 'resource_id': resource_id},
            {'$set': dependency},
            upsert=True
        )
        
        if result.upserted_id:
            return result.upserted_id
        return None
    
    @staticmethod
    def find_by_service(service_id):
        """Find all dependencies for a service"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return []
                
        return list(dependencies_collection.find({'service_id': service_id}))
    
    @staticmethod
    def find_by_resource(resource_id):
        """Find all dependencies for a resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return []
                
        return list(dependencies_collection.find({'resource_id': resource_id}))
    
    @staticmethod
    def update(service_id, resource_id, **kwargs):
        """Update dependency"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return None
                
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        # Convert quantity to float
        if 'quantity_required' in kwargs:
            kwargs['quantity_required'] = float(kwargs['quantity_required'])
            
        return dependencies_collection.update_one(
            {'service_id': service_id, 'resource_id': resource_id},
            {'$set': kwargs}
        )
    
    @staticmethod
    def delete(service_id, resource_id):
        """Delete dependency"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return None
                
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
                
        return dependencies_collection.delete_one(
            {'service_id': service_id, 'resource_id': resource_id}
        )

# Resource Pricing Management
class PricingManager:
    @staticmethod
    def create(resource_id, list_price=None, negotiated_price=None, 
              recent_purchase_price=None, recent_quote_price=None,
              average_market_price=None, monthly_usage_cost=None,
              vendor=None, contract_expiry=None):
        """Create pricing data for a resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        # Convert decimal values
        pricing = {
            'resource_id': resource_id,
            'list_price': float(list_price) if list_price is not None else None,
            'negotiated_price': float(negotiated_price) if negotiated_price is not None else None,
            'recent_purchase_price': float(recent_purchase_price) if recent_purchase_price is not None else None,
            'recent_quote_price': float(recent_quote_price) if recent_quote_price is not None else None,
            'average_market_price': float(average_market_price) if average_market_price is not None else None,
            'monthly_usage_cost': float(monthly_usage_cost) if monthly_usage_cost is not None else None,
            'vendor': vendor,
            'contract_expiry': contract_expiry,
            'last_price_update': datetime.now()
        }
        
        # Upsert to handle potential duplicates
        result = pricing_collection.update_one(
            {'resource_id': resource_id},
            {'$set': pricing},
            upsert=True
        )
        
        if result.upserted_id:
            return result.upserted_id
        return None
    
    @staticmethod
    def find_by_resource(resource_id):
        """Find pricing data for a resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
                
        return pricing_collection.find_one({'resource_id': resource_id})
    
    @staticmethod
    def find_all(limit=100, skip=0):
        """Find all pricing data"""
        return list(pricing_collection.find().skip(skip).limit(limit))
    
    @staticmethod
    def update(resource_id, **kwargs):
        """Update pricing data"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        # Add last_price_update timestamp
        kwargs['last_price_update'] = datetime.now()
        
        # Convert decimal values
        for key in ['list_price', 'negotiated_price', 'recent_purchase_price', 
                   'recent_quote_price', 'average_market_price', 'monthly_usage_cost']:
            if key in kwargs and kwargs[key] is not None:
                kwargs[key] = float(kwargs[key])
        
        return pricing_collection.update_one(
            {'resource_id': resource_id},
            {'$set': kwargs}
        )
    
    @staticmethod
    def delete(resource_id):
        """Delete pricing data"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
                
        return pricing_collection.delete_one({'resource_id': resource_id})

# Resource Usage History Management
class UsageHistoryManager:
    @staticmethod
    def create(resource_id, utilization, timestamp=None):
        """Create usage history entry"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return None
        
        if timestamp is None:
            timestamp = datetime.now()
            
        history = {
            'resource_id': resource_id,
            'utilization': float(utilization),
            'timestamp': timestamp
        }
        
        return usage_history_collection.insert_one(history).inserted_id
    
    @staticmethod
    def find_by_resource(resource_id, start_time=None, end_time=None, limit=100):
        """Find usage history for a resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return []
                
        query = {'resource_id': resource_id}
        
        if start_time or end_time:
            query['timestamp'] = {}
            
        if start_time:
            query['timestamp']['$gte'] = start_time
            
        if end_time:
            query['timestamp']['$lte'] = end_time
            
        return list(usage_history_collection.find(query).sort('timestamp', -1).limit(limit))
    
    @staticmethod
    def delete_old_entries(days_to_keep=90):
        """Delete entries older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        return usage_history_collection.delete_many({'timestamp': {'$lt': cutoff_date}})

# Alert Management
class AlertManager:
    ALERT_TYPES = [
        'CAPACITY', 'PERFORMANCE', 'OUTAGE', 'PRICING', 'SECURITY', 'OTHER'
    ]
    
    SEVERITY_LEVELS = [
        'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    ]
    
    @staticmethod
    def create(title, description, alert_type, severity, 
              resource_id=None, service_id=None):
        """Create a new alert"""
        if alert_type not in AlertManager.ALERT_TYPES:
            raise ValueError(f"Alert type must be one of {AlertManager.ALERT_TYPES}")
            
        if severity not in AlertManager.SEVERITY_LEVELS:
            raise ValueError(f"Severity must be one of {AlertManager.SEVERITY_LEVELS}")
        
        # Convert IDs to ObjectId if provided
        if resource_id and not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                resource_id = None
                
        if service_id and not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                service_id = None
        
        alert = {
            'title': title,
            'description': description,
            'alert_type': alert_type,
            'severity': severity,
            'resource_id': resource_id,
            'service_id': service_id,
            'created_at': datetime.now(),
            'is_resolved': False,
            'resolved_at': None
        }
        
        return alerts_collection.insert_one(alert).inserted_id
    
    @staticmethod
    def find_by_id(alert_id):
        """Find alert by ID"""
        if not isinstance(alert_id, ObjectId):
            try:
                alert_id = ObjectId(alert_id)
            except:
                return None
                
        return alerts_collection.find_one({'_id': alert_id})
    
    @staticmethod
    def find_all(resolved=None, severity=None, alert_type=None, limit=100, skip=0):
        """Find all alerts, optionally filtered"""
        query = {}
        
        if resolved is not None:
            query['is_resolved'] = resolved
            
        if severity:
            query['severity'] = severity
            
        if alert_type:
            query['alert_type'] = alert_type
            
        return list(alerts_collection.find(query).sort('created_at', -1).skip(skip).limit(limit))
    
    @staticmethod
    def find_by_resource(resource_id, resolved=None):
        """Find alerts for a resource"""
        if not isinstance(resource_id, ObjectId):
            try:
                resource_id = ObjectId(resource_id)
            except:
                return []
                
        query = {'resource_id': resource_id}
        
        if resolved is not None:
            query['is_resolved'] = resolved
            
        return list(alerts_collection.find(query).sort('created_at', -1))
    
    @staticmethod
    def find_by_service(service_id, resolved=None):
        """Find alerts for a service"""
        if not isinstance(service_id, ObjectId):
            try:
                service_id = ObjectId(service_id)
            except:
                return []
                
        query = {'service_id': service_id}
        
        if resolved is not None:
            query['is_resolved'] = resolved
            
        return list(alerts_collection.find(query).sort('created_at', -1))
    
    @staticmethod
    def resolve(alert_id):
        """Mark alert as resolved"""
        if not isinstance(alert_id, ObjectId):
            try:
                alert_id = ObjectId(alert_id)
            except:
                return None
                
        return alerts_collection.update_one(
            {'_id': alert_id},
            {
                '$set': {
                    'is_resolved': True,
                    'resolved_at': datetime.now()
                }
            }
        )
    
    @staticmethod
    def delete(alert_id):
        """Delete alert"""
        if not isinstance(alert_id, ObjectId):
            try:
                alert_id = ObjectId(alert_id)
            except:
                return None
                
        return alerts_collection.delete_one({'_id': alert_id})