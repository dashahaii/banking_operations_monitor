from django.db import models
from django.utils import timezone

class Resource(models.Model):
    """Model representing a computing or IT resource"""
    name = models.CharField(max_length=200, unique=True)
    resource_id = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=50, choices=[
        ('COMPUTE', 'Computing Resource'),
        ('STORAGE', 'Storage Resource'),
        ('NETWORK', 'Network Resource'),
        ('LICENSE', 'Software License'),
        ('SERVICE', 'Service'),
        ('OTHER', 'Other Resource')
    ])
    location = models.CharField(max_length=200, blank=True, null=True)
    current_utilization = models.FloatField(default=0)
    total_capacity = models.FloatField(default=0)
    unit = models.CharField(max_length=20, default='count')
    last_updated = models.DateTimeField(default=timezone.now)
    
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.total_capacity > 0:
            return (self.current_utilization / self.total_capacity) * 100
        return 0
    
    def __str__(self):
        return self.name

class Service(models.Model):
    """Model representing a banking service that depends on resources"""
    name = models.CharField(max_length=200, unique=True)
    service_id = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=[
        ('OPERATIONAL', 'Operational'),
        ('DEGRADED', 'Degraded Performance'),
        ('PARTIAL_OUTAGE', 'Partial Outage'),
        ('MAJOR_OUTAGE', 'Major Outage'),
        ('MAINTENANCE', 'Under Maintenance')
    ], default='OPERATIONAL')
    resources = models.ManyToManyField(Resource, through='ServiceResourceDependency')
    criticality = models.CharField(max_length=20, choices=[
        ('CRITICAL', 'Business Critical'),
        ('HIGH', 'High Importance'),
        ('MEDIUM', 'Medium Importance'),
        ('LOW', 'Low Importance')
    ], default='MEDIUM')
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.name

class ServiceResourceDependency(models.Model):
    """Model representing the dependency of a service on a resource"""
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    quantity_required = models.FloatField(default=1.0)
    is_critical = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('service', 'resource')
        verbose_name_plural = 'Service Resource Dependencies'
    
    def __str__(self):
        return f"{self.service} - {self.resource} ({self.quantity_required})"

class ResourcePricing(models.Model):
    """Model representing pricing data for resources"""
    resource = models.OneToOneField(Resource, on_delete=models.CASCADE)
    list_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    negotiated_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    recent_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    recent_quote_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    average_market_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monthly_usage_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_price_update = models.DateTimeField(default=timezone.now)
    vendor = models.CharField(max_length=100, blank=True, null=True)
    contract_expiry = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Pricing for {self.resource}"

class ResourceUsageHistory(models.Model):
    """Model for tracking resource usage over time"""
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    utilization = models.FloatField()
    
    class Meta:
        indexes = [
            models.Index(fields=['resource', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.resource} - {self.timestamp}"

class Alert(models.Model):
    """Model for resource and service alerts"""
    ALERT_TYPES = [
        ('CAPACITY', 'Capacity Warning'),
        ('PERFORMANCE', 'Performance Issue'),
        ('OUTAGE', 'Service Outage'),
        ('PRICING', 'Pricing Change'),
        ('SECURITY', 'Security Alert'),
        ('OTHER', 'Other Alert')
    ]
    
    SEVERITY_LEVELS = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
        ('INFO', 'Informational')
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title
    
    def resolve(self):
        """Mark alert as resolved"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.save()