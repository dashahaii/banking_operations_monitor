import psutil
import os
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse

class PrometheusMetrics:
    # Request Metrics
    REQUESTS = Counter(
        'django_http_requests_total', 
        'Total HTTP Requests', 
        ['method', 'endpoint', 'status']
    )

    REQUEST_LATENCY = Histogram(
        'django_http_request_duration_seconds', 
        'HTTP request latency',
        ['method', 'endpoint']
    )

    # Database Metrics
    DB_CONNECTIONS = Gauge(
        'django_db_connections', 
        'Number of active database connections'
    )

    # System Resource Metrics
    SYSTEM_RESOURCES = {
        'cpu_usage': Gauge(
            'django_process_cpu_usage', 
            'Current CPU usage of the Django process'
        ),
        'memory_usage': Gauge(
            'django_process_memory_usage_bytes', 
            'Current memory usage of the Django process'
        )
    }

    @classmethod
    def track_request_metrics(cls, request, response=None, exception=None):
        """
        Track request-related metrics
        """
        method = request.method
        path = request.path

        # Count total requests
        status_code = getattr(response, 'status_code', 500) if response else 500
        cls.REQUESTS.labels(
            method=method, 
            endpoint=path, 
            status=status_code
        ).inc()

        return response

    @classmethod
    def update_system_metrics(cls):
        """
        Update system resource metrics
        """
        try:
            # Get current process
            process = psutil.Process(os.getpid())
            
            # Update CPU and Memory usage
            cls.SYSTEM_RESOURCES['cpu_usage'].set(process.cpu_percent())
            cls.SYSTEM_RESOURCES['memory_usage'].set(process.memory_info().rss)
        except Exception as e:
            print(f"Error updating system metrics: {e}")

    @classmethod
    def metrics_view(cls, request):
        """
        Endpoint to expose Prometheus metrics
        """
        # Update system resource metrics before generating
        cls.update_system_metrics()

        # Generate and return metrics
        return HttpResponse(
            generate_latest(), 
            content_type=CONTENT_TYPE_LATEST
        )