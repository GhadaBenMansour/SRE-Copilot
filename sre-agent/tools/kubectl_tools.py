"""
Kubectl tools for the SRE Agent.
Each function is wrapped as a LangChain Tool so the agent can call them.
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
    """Strip surrounding quotes and whitespace that Mistral sometimes adds."""
    return value.strip().strip("'\"")


def _run_kubectl(args: list[str], timeout: int = 30) -> str:
    """
    Run a kubectl command.
    Inside a pod: uses the ServiceAccount token (in-cluster config).
    Outside: falls back to the default kubeconfig.
    """
    if os.path.exists(_SA_TOKEN_PATH):
        # Running inside a pod — use ServiceAccount token directly
        with open(_SA_TOKEN_PATH) as f:
            token = f.read().strip()
        cmd = [
            "kubectl",
            f"--server={_K8S_SERVER}",
            f"--token={token}",
            f"--certificate-authority={_SA_CA_PATH}",
        ] + args
    else:
        # Running locally (dev/test) — use default kubeconfig
        cmd = ["kubectl"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return f"ERROR: {result.stderr.strip()}"
        return result.stdout.strip() or "(empty output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: kubectl command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: kubectl not found in PATH"
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def get_pod_logs(input: str) -> str:
    """
    Get the last 50 lines of logs from a pod.
    Input format: 'namespace/pod_name' or 'namespace/pod_name/container_name'
    Example: 'demo/crash-app-abc123' or 'demo/crash-app-abc123/crash-container'
    """
    parts = _clean(input).split("/")
    if len(parts) < 2:
        return "ERROR: expected 'namespace/pod_name' or 'namespace/pod_name/container'"
    namespace, pod = parts[0], parts[1]
    args = ["logs", pod, "-n", namespace, "--tail=50", "--previous"]
    if len(parts) == 3:
        args += ["-c", parts[2]]
    result = _run_kubectl(args)
    # If --previous fails, try without it
    if "ERROR" in result:
        args_no_prev = [a for a in args if a != "--previous"]
        result = _run_kubectl(args_no_prev)
    return result


@tool
def get_pod_status(input: str) -> str:
    """
    Get all pods status in a namespace.
    Input: namespace name, e.g. 'demo' or 'monitoring'
    """
    namespace = _clean(input)
    return _run_kubectl(["get", "pods", "-n", namespace, "-o", "wide"])


@tool
def describe_pod(input: str) -> str:
    """
    Describe a pod to get events and detailed status.
    Input format: 'namespace/pod_name'
    Example: 'demo/crash-app-abc123'
    """
    parts = _clean(input).split("/")
    if len(parts) < 2:
        return "ERROR: expected 'namespace/pod_name'"
    namespace, pod = parts[0], parts[1]
    return _run_kubectl(["describe", "pod", pod, "-n", namespace])


@tool
def get_deployment_status(input: str) -> str:
    """
    Get deployment status in a namespace.
    Input format: 'namespace' or 'namespace/deployment_name'
    Example: 'demo' or 'demo/crash-app'
    """
    parts = _clean(input).split("/")
    namespace = parts[0]
    if len(parts) == 2:
        return _run_kubectl(["get", "deployment", parts[1], "-n", namespace, "-o", "yaml"])
    return _run_kubectl(["get", "deployments", "-n", namespace, "-o", "wide"])


@tool
def get_namespace_events(input: str) -> str:
    """
    Get recent events in a namespace, sorted by time.
    Input: namespace name, e.g. 'demo'
    """
    namespace = _clean(input)
    return _run_kubectl([
        "get", "events", "-n", namespace,
        "--sort-by=.lastTimestamp",
        "--field-selector=type!=Normal"
    ])


@tool
def restart_deployment(input: str) -> str:
    """
    Restart a deployment by doing a rollout restart.
    Input format: 'namespace/deployment_name'
    Example: 'demo/crash-app'
    USE WITH CAUTION - this will cause a brief downtime.
    """
    parts = _clean(input).split("/")
    if len(parts) < 2:
        return "ERROR: expected 'namespace/deployment_name'"
    namespace, deployment = parts[0], parts[1]
    return _run_kubectl(["rollout", "restart", "deployment", deployment, "-n", namespace])


@tool
def scale_deployment(input: str) -> str:
    """
    Scale a deployment to a given number of replicas.
    Input format: 'namespace/deployment_name/replicas'
    Example: 'demo/crash-app/0' to scale to 0, 'demo/crash-app/2' to scale up
    """
    parts = _clean(input).split("/")
    if len(parts) < 3:
        return "ERROR: expected 'namespace/deployment_name/replicas'"
    namespace, deployment, replicas = parts[0], parts[1], parts[2]
    return _run_kubectl([
        "scale", "deployment", deployment,
        "-n", namespace,
        f"--replicas={replicas}"
    ])


@tool
def get_pod_resource_usage(input: str) -> str:
    """
    Get CPU and memory usage for pods in a namespace.
    Input: namespace name, e.g. 'demo'
    """
    namespace = _clean(input)
    return _run_kubectl(["top", "pods", "-n", namespace])


@tool
def find_crashing_pods(input: str) -> str:
    """
    Find all pods with CrashLoopBackOff or Error status across a namespace.
    Input: namespace name, e.g. 'demo' or 'all' for all namespaces
    """
    namespace = _clean(input)
    if namespace == "all":
        return _run_kubectl(["get", "pods", "--all-namespaces", "--field-selector=status.phase!=Running"])
    return _run_kubectl([
        "get", "pods", "-n", namespace,
        "--field-selector=status.phase!=Running"
    ])
