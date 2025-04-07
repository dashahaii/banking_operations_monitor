from .metrics import PrometheusMetrics
import time

class PrometheusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Start timing the request
        start_time = time.time()

        # Process the request
        response = self.get_response(request)

        # Track request metrics
        PrometheusMetrics.track_request_metrics(request, response)

        # Record request latency
        method = request.method
        path = request.path
        latency = time.time() - start_time
        PrometheusMetrics.REQUEST_LATENCY.labels(
            method=method, 
            endpoint=path
        ).observe(latency)

        return response

    def process_exception(self, request, exception):
        # Track metrics for exceptions
        PrometheusMetrics.track_request_metrics(request, exception=exception)
        return None