use axum::{
    body::Body,
    extract::{Query, State},
    http::{header, Response},
    routing::get,
    Router,
};
use prometheus::{
    register_histogram_vec, register_int_counter_vec, register_int_gauge_vec, Encoder,
    HistogramVec, IntCounterVec, IntGaugeVec, TextEncoder,
};
use serde_json::json;
use std::{
    collections::HashMap,
    env,
    sync::{Arc, OnceLock},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tokio::time::sleep;

static REQUESTS_TOTAL: OnceLock<IntCounterVec> = OnceLock::new();
static REQUEST_DURATION: OnceLock<HistogramVec> = OnceLock::new();
static ACTIVE_REQUESTS: OnceLock<IntGaugeVec> = OnceLock::new();

fn init_metrics() {
    REQUESTS_TOTAL.get_or_init(|| {
        register_int_counter_vec!(
            "worker_requests_total",
            "Total HTTP requests handled, by pod, endpoint, and status.",
            &["pod", "endpoint", "status"]
        )
        .expect("register worker_requests_total")
    });
    REQUEST_DURATION.get_or_init(|| {
        register_histogram_vec!(
            "worker_request_duration_seconds",
            "HTTP request latency in seconds.",
            &["pod", "endpoint"],
            prometheus::DEFAULT_BUCKETS.to_vec()
        )
        .expect("register worker_request_duration_seconds")
    });
    ACTIVE_REQUESTS.get_or_init(|| {
        register_int_gauge_vec!(
            "worker_active_requests",
            "Number of in-flight requests per pod.",
            &["pod"]
        )
        .expect("register worker_active_requests")
    });
}

fn active_inc(pod: &str) {
    if let Some(g) = ACTIVE_REQUESTS.get() {
        g.with_label_values(&[pod]).inc();
    }
}

fn record_done(pod: &str, endpoint: &str, start: Instant) {
    if let Some(g) = ACTIVE_REQUESTS.get() {
        g.with_label_values(&[pod]).dec();
    }
    if let Some(h) = REQUEST_DURATION.get() {
        h.with_label_values(&[pod, endpoint])
            .observe(start.elapsed().as_secs_f64());
    }
    if let Some(c) = REQUESTS_TOTAL.get() {
        c.with_label_values(&[pod, endpoint, "200"]).inc();
    }
}

#[derive(Clone)]
struct AppState {
    pod_name: Arc<String>,
    base_delay_ms: u64,
}

fn unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn get_pod_name() -> String {
    env::var("POD_NAME").unwrap_or_else(|_| {
        std::fs::read_to_string("/etc/hostname")
            .map(|s| s.trim().to_owned())
            .unwrap_or_else(|_| "unknown".to_owned())
    })
}

fn json_response(pod: &str, body: serde_json::Value) -> Response<Body> {
    Response::builder()
        .header(header::CONTENT_TYPE, "application/json")
        .header("x-pod-name", pod)
        .body(Body::from(body.to_string()))
        .expect("build json response")
}

async fn handle_get(State(s): State<AppState>) -> Response<Body> {
    let start = Instant::now();
    active_inc(&s.pod_name);
    let body = json!({ "pod": *s.pod_name, "ts": unix_ms() });
    record_done(&s.pod_name, "/get", start);
    json_response(&s.pod_name, body)
}

async fn handle_work(
    State(s): State<AppState>,
    Query(params): Query<HashMap<String, String>>,
) -> Response<Body> {
    let start = Instant::now();
    active_inc(&s.pod_name);

    let extra_ms: u64 = params.get("ms").and_then(|v| v.parse().ok()).unwrap_or(0);
    let total_ms = s.base_delay_ms + extra_ms;
    if total_ms > 0 {
        sleep(Duration::from_millis(total_ms)).await;
    }

    let body = json!({ "pod": *s.pod_name, "delay_ms": total_ms, "ts": unix_ms() });
    record_done(&s.pod_name, "/work", start);
    json_response(&s.pod_name, body)
}

async fn handle_cpu(
    State(s): State<AppState>,
    Query(params): Query<HashMap<String, String>>,
) -> Response<Body> {
    let start = Instant::now();
    active_inc(&s.pod_name);

    let duration_secs: f64 = params
        .get("duration")
        .and_then(|v| v.parse().ok())
        .unwrap_or(0.1);

    let deadline = Instant::now() + Duration::from_secs_f64(duration_secs);
    let result = tokio::task::spawn_blocking(move || {
        let mut x = 1.0f64;
        while Instant::now() < deadline {
            x = (x + 1.0).sqrt();
        }
        x
    })
    .await
    .unwrap_or(0.0);

    let body = json!({ "pod": *s.pod_name, "duration": duration_secs, "result": result });
    record_done(&s.pod_name, "/cpu", start);
    json_response(&s.pod_name, body)
}

async fn handle_health() -> &'static str {
    "ok\n"
}

async fn handle_metrics() -> Response<Body> {
    let encoder = TextEncoder::new();
    let families = prometheus::gather();
    let mut buf = Vec::new();
    let _ = encoder.encode(&families, &mut buf);
    Response::builder()
        .header(header::CONTENT_TYPE, "text/plain; version=0.0.4")
        .body(Body::from(buf))
        .expect("build metrics response")
}

#[tokio::main]
async fn main() {
    init_metrics();

    let state = AppState {
        pod_name: Arc::new(get_pod_name()),
        base_delay_ms: env::var("BASE_DELAY_MS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0),
    };
    let port = env::var("PORT").unwrap_or_else(|_| "8080".to_owned());

    let app = Router::new()
        .route("/", get(handle_get))
        .route("/get", get(handle_get))
        .route("/work", get(handle_work))
        .route("/cpu", get(handle_cpu))
        .route("/health", get(handle_health))
        .route("/metrics", get(handle_metrics))
        .with_state(state);

    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .expect("bind failed");
    axum::serve(listener, app).await.expect("server failed");
}
