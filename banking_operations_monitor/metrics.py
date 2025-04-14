# metrics.py
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse

class PrometheusMetrics:
    # Request count metric
    REQUEST_COUNT = Counter(
        'http_requests_total',
        'Total HTTP requests count',
        ['method', 'endpoint', 'status_code']
    )
    
    # Request latency metric
    REQUEST_LATENCY = Histogram(
        'http_request_latency_seconds',
        'HTTP request latency in seconds',
        ['method', 'endpoint']
    )
    
    # Exception count metric
    EXCEPTION_COUNT = Counter(
        'http_exceptions_total',
        'Total HTTP request exceptions',
        ['method', 'endpoint', 'exception_type']
    )
    
    # Health check gauge
    HEALTH_CHECK = Gauge(
        'app_health_check_up',
        'Health check status (1=up, 0=down)',
        ['endpoint']
    )
    
    # MongoDB connection status
    MONGODB_CONNECTION = Gauge(
        'app_mongodb_connection_up',
        'MongoDB connection status (1=up, 0=down)',
        []
    )
    
    # Service dependency status
    SERVICE_DEPENDENCY = Gauge(
        'app_service_dependency_up',
        'Service dependency status (1=up, 0=down)',
        ['service']
    )
    
    # Initialize default values
    HEALTH_CHECK.labels(endpoint='health').set(1)
    MONGODB_CONNECTION.set(1)
    
    @classmethod
    def track_request_metrics(cls, request, response=None, exception=None):
        """
        Track metrics for HTTP requests
        """
        method = request.method
        path = request.path
        
        if exception:
            # Track exception
            exception_type = type(exception).__name__
            cls.EXCEPTION_COUNT.labels(
                method=method,
                endpoint=path,
                exception_type=exception_type
            ).inc()
        elif response:
            # Track request count
            cls.REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=response.status_code
            ).inc()
    
    @classmethod
    def update_health_status(cls, endpoint='health', status=True):
        """
        Update the health check status for a specific endpoint
        """
        cls.HEALTH_CHECK.labels(endpoint=endpoint).set(1 if status else 0)
    
    @classmethod
    def update_mongodb_status(cls, status=True):
        """
        Update MongoDB connection status
        """
        cls.MONGODB_CONNECTION.set(1 if status else 0)
    
    @classmethod
    def update_service_status(cls, service, status=True):
        """
        Update service dependency status
        """
        cls.SERVICE_DEPENDENCY.labels(service=service).set(1 if status else 0)
    
    @classmethod
    def metrics_view(cls, request):
        """
        Return all metrics as a Prometheus-formatted response
        """
        metrics_page = generate_latest()
        return HttpResponse(metrics_page, content_type=CONTENT_TYPE_LATEST)