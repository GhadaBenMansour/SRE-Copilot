from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class Severity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class AlertLabel(BaseModel):
    alertname: str
    namespace: Optional[str] = "default"
    pod: Optional[str] = None
    deployment: Optional[str] = None
    severity: Optional[str] = "warning"
    container: Optional[str] = None


class AlertAnnotation(BaseModel):
    summary: Optional[str] = ""
    description: Optional[str] = ""


class Alert(BaseModel):
    status: str  # "firing" | "resolved"
    labels: AlertLabel
    annotations: AlertAnnotation
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertManagerPayload(BaseModel):
    version: Optional[str] = "4"
    groupKey: Optional[str] = None
    status: str
    receiver: Optional[str] = None
    groupLabels: Optional[dict] = {}
    commonLabels: Optional[dict] = {}
    commonAnnotations: Optional[dict] = {}
    alerts: List[Alert]


class RemediationStep(BaseModel):
    order: int
    action: str
    command: Optional[str] = None
    description: str


class AgentResponse(BaseModel):
    alert_name: str
    namespace: str
    severity: str
    classification: str
    root_cause: str
    runbook: List[RemediationStep]
    auto_remediation_applied: bool
    remediation_details: Optional[str] = None
    git_pr_url: Optional[str] = None
    argocd_sync_triggered: bool = False
    investigation_log: List[str] = []
    timestamp: Optional[str] = None
    duration_seconds: Optional[float] = None
    pod: Optional[str] = None
