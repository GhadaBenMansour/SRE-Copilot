"""
kubectl tools for the SRE Agent.

Design notes:
- _run_kubectl: low-level wrapper, handles both in-cluster (SA token) and local (kubeconfig) auth.
- resolve_pod_name: resolves partial pod names (deployment prefix) to exact running pod names.
- Read-only tools (get_*, describe_*, find_*) are exposed as LangChain @tools.
- Write tools (restart_deployment, scale_deployment) are plain functions — not decorated,
  so they can only be called explicitly by Python code (not by an LLM via ReAct).
"""
import subprocess
import logging
import os
from langchain.tools import tool

logger = logging.getLogger(__name__)

# In-cluster service account paths (mounted automatically by Kubernetes)
_SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
_SA_CA_PATH    = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
_K8S_SERVER    = "https://kubernetes.default.svc"


def _clean(value: str) -> str:
    """Strip surrounding quotes and whitespace that LLMs sometimes add."""
    return value.strip().strip("'\"")


def _run_kubectl(args: list[str], timeout: int = 30) -> str:
    """
    Run a kubectl command and return stdout as a string.
    Automatically selects auth method:
      - Inside a pod: uses ServiceAccount token (in-cluster config).
      - Outside a pod: uses the default kubeconfig (~/.kube/config).
    """
    if os.path.exists(_SA_TOKEN_PATH):
        with open(_SA_TOKEN_PATH) as f:
            token = f.read().strip()
        cmd = [
            "kubectl",
            f"--server={_K8S_SERVER}",
            f"--token={token}",
            f"--certificate-authority={_SA_CA_PATH}",
        ] + args
    else:
        cmd = ["kubectl"] + args

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return f"ERROR: {result.stderr.strip()}"
        return result.stdout.strip() or "(empty output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: kubectl timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: kubectl not found in PATH"
    except Exception as exc:
        return f"ERROR: {exc}"


def resolve_pod_name(namespace: str, pod_prefix: str) -> str:
    """
    Resolve a partial pod name (e.g. 'crash-app') to the exact running pod name
    (e.g. 'crash-app-6d9dcddc79-zfkl9').

    Matches pods whose name equals pod_prefix exactly or starts with pod_prefix + '-'.
    Returns pod_prefix unchanged if no match is found (safe fallback).
    """
    out = _run_kubectl([
        "get", "pods", "-n", namespace,
        "--no-headers",
        "-o", "custom-columns=NAME:.metadata.name",
    ])
    if "ERROR" in out:
        logger.warning(f"resolve_pod_name: could not list pods in {namespace}: {out}")
        return pod_prefix

    for line in out.splitlines():
        name = line.strip()
        if name == pod_prefix or name.startswith(pod_prefix + "-"):
            logger.debug(f"resolve_pod_name: '{pod_prefix}' → '{name}'")
            return name

    logger.warning(f"resolve_pod_name: no pod matching '{pod_prefix}' in {namespace}")
    return pod_prefix


# Keep private alias for backward compatibility with agent.py import
_resolve_pod_name = resolve_pod_name


# ── Read-only investigation tools (safe to expose to LLM) ─────────────────────

@tool
def get_pod_logs(input: str) -> str:
    """
    Get the last 50 lines of logs from a pod (previous container if available).
    Input format: 'namespace/pod_name' or 'namespace/pod_name/container_name'
    Partial pod names (e.g. 'demo/crash-app') are resolved automatically.
    """
    parts = _clean(input).split("/")
    if len(parts) < 2:
        return "ERROR: expected 'namespace/pod_name'"
    namespace = parts[0]
    pod       = resolve_pod_name(namespace, parts[1])

    args = ["logs", pod, "-n", namespace, "--tail=50", "--previous"]
    if len(parts) == 3:
        args += ["-c", parts[2]]

    result = _run_kubectl(args)
    if "ERROR" in result:
        # Retry without --previous (pod may not have restarted yet)
        args_live = [a for a in args if a != "--previous"]
        result = _run_kubectl(args_live)
    return result


@tool
def get_pod_status(input: str) -> str:
    """
    List all pods in a namespace with their status and node.
    Input: namespace name, e.g. 'demo'
    """
    return _run_kubectl(["get", "pods", "-n", _clean(input), "-o", "wide"])


@tool
def describe_pod(input: str) -> str:
    """
    Describe a pod to get events, conditions, and resource details.
    Input format: 'namespace/pod_name' — partial names are resolved automatically.
    """
    parts = _clean(input).split("/")
    if len(parts) < 2:
        return "ERROR: expected 'namespace/pod_name'"
    namespace = parts[0]
    pod       = resolve_pod_name(namespace, parts[1])
    return _run_kubectl(["describe", "pod", pod, "-n", namespace])


@tool
def get_deployment_status(input: str) -> str:
    """
    Get deployment status in a namespace.
    Input: 'namespace' to list all, or 'namespace/deployment_name' for one.
    """
    parts = _clean(input).split("/")
    namespace = parts[0]
    if len(parts) == 2:
        return _run_kubectl(["get", "deployment", parts[1], "-n", namespace, "-o", "yaml"])
    return _run_kubectl(["get", "deployments", "-n", namespace, "-o", "wide"])


@tool
def get_namespace_events(input: str) -> str:
    """
    Get recent warning events in a namespace, sorted by timestamp.
    Input: namespace name, e.g. 'demo'
    """
    return _run_kubectl([
        "get", "events", "-n", _clean(input),
        "--sort-by=.lastTimestamp",
        "--field-selector=type!=Normal",
    ])


@tool
def get_pod_resource_usage(input: str) -> str:
    """
    Get CPU and memory usage for pods in a namespace (requires metrics-server).
    Input: namespace name, e.g. 'demo'
    """
    return _run_kubectl(["top", "pods", "-n", _clean(input)])


@tool
def find_crashing_pods(input: str) -> str:
    """
    Find all pods in non-Running state (CrashLoopBackOff, Error, Pending, etc.).
    Input: namespace name, or 'all' for all namespaces.
    """
    ns = _clean(input)
    if ns == "all":
        return _run_kubectl(["get", "pods", "--all-namespaces",
                             "--field-selector=status.phase!=Running"])
    return _run_kubectl(["get", "pods", "-n", ns,
                         "--field-selector=status.phase!=Running"])


# ── Write operations (not decorated — only callable from Python, not from LLM) ─

def restart_deployment(namespace: str, deployment: str) -> str:
    """
    Restart a deployment via rollout restart.
    Not exposed as a LangChain tool — must be called explicitly from Python.
    """
    logger.warning(f"restart_deployment called: {namespace}/{deployment}")
    return _run_kubectl(["rollout", "restart", "deployment", deployment, "-n", namespace])


def scale_deployment(namespace: str, deployment: str, replicas: int) -> str:
    """
    Scale a deployment to N replicas.
    Not exposed as a LangChain tool — must be called explicitly from Python.
    """
    logger.warning(f"scale_deployment called: {namespace}/{deployment} → {replicas}")
    return _run_kubectl([
        "scale", "deployment", deployment,
        "-n", namespace,
        f"--replicas={replicas}",
    ])
