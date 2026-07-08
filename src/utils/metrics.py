from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response, Request, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
import time


Request_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
Request_LATENCY = Histogram('http_request_duration_seconds', 'HTTP Request Latency', ['method', 'endpoint'])

# ------ OCR Metrics ------
OCR_CALLS_TOTAL = Counter(
    'ocr_calls_total',
    'Total OCR API calls made during PDF processing',
    ['provider', 'status']  # status: 'success' | 'failure'
)
OCR_BLOCKS_TOTAL = Counter(
    'ocr_blocks_processed_total',
    'Total PDF blocks processed (native text vs OCR image)',
    ['block_type']  # block_type: 'text' | 'image'
)
OCR_LATENCY = Histogram(
    'ocr_call_duration_seconds',
    'Latency of individual OCR provider API calls',
    ['provider']
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        start_time = time.time()

        response = await call_next(request)
        
        latency = time.time() - start_time
        
        Request_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
        Request_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(latency)

        return response
    

def setup_metrics(app: FastAPI):
    
    app.add_middleware(PrometheusMiddleware)

    @app.get("/TrhBVe_m5gg5df5_Adafljn", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
