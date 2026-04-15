"""
SRE Copilot — FastAPI service.

Endpoints:
  POST /alert          — Receives Alertmanager webhook payload
  POST /analyze        — Analyze a single alert (for testing)
  GET  /health         — Health check
  GET  /status         — Agent + Ollama status
"""
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models import AlertManagerPayload, Alert, AgentResponse
from agent import run_sre_investigation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SRE Copilot starting up...")
    logger.info(f"Ollama URL: {OLLAMA_BASE_URL} | Model: {OLLAMA_MODEL}")
    yield
    logger.info("SRE Copilot shutting down.")


app = FastAPI(
    title="SRE Copilot",
    description="AI-powered SRE agent for GitOps remediation",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sre-copilot"}


@app.get("/status")
async def status():
    """Check if Ollama is reachable and the model is available."""
    ollama_ok = False
    model_available = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
                models = [m["name"] for m in resp.json().get("models", [])]
                model_available = any(OLLAMA_MODEL in m for m in models)
                return {
                    "status": "ok",
                    "ollama": "reachable",
                    "model": OLLAMA_MODEL,
                    "model_available": model_available,
                    "available_models": models,
                }
    except Exception as e:
        return {
            "status": "degraded",
            "ollama": "unreachable",
            "error": str(e),
            "hint": f"Make sure Ollama is running and {OLLAMA_MODEL} is pulled: ollama pull {OLLAMA_MODEL}",
        }


@app.post("/alert", response_model=dict)
async def receive_alertmanager_webhook(
    payload: AlertManagerPayload,
    background_tasks: BackgroundTasks,
):
    """
    Main webhook endpoint for Alertmanager.
    Processes all firing alerts in the payload.
    """
    logger.info(
        f"Received alertmanager webhook: {len(payload.alerts)} alert(s), status={payload.status}"
    )

    firing_alerts = [a for a in payload.alerts if a.status == "firing"]
    if not firing_alerts:
        return {"message": "No firing alerts, nothing to do.", "count": 0}

    # Process alerts (can be done async for large batches)
    results = []
    for alert in firing_alerts:
        logger.info(f"Processing alert: {alert.labels.alertname} in {alert.labels.namespace}")
        response = await run_sre_investigation(alert)
        results.append(response.model_dump())

    return {
        "message": f"Processed {len(results)} alert(s)",
        "results": results,
    }


@app.post("/analyze", response_model=AgentResponse)
async def analyze_alert(alert: Alert):
    """
    Analyze a single alert. Used for testing and direct integrations.
    """
    logger.info(f"Direct analysis request for: {alert.labels.alertname}")
    response = await run_sre_investigation(alert)
    return response


@app.post("/test-crash-loop")
async def test_crash_loop():
    """
    Convenience endpoint to simulate a CrashLoopBackOff alert for testing.
    """
    test_alert = Alert(
        status="firing",
        labels={
            "alertname": "PodRestartingTooMuch",
            "namespace": "demo",
            "pod": "crash-app",
            "severity": "critical",
        },
        annotations={
            "summary": "Pod restarting frequently",
            "description": "Pod crash-app in namespace demo is restarting too often.",
        },
    )
    response = await run_sre_investigation(test_alert)
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
