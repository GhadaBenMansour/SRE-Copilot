"""
Tool registry for SRE Copilot.

Read-only LangChain tools (safe for LLM access):
  kubectl: get_pod_logs, get_pod_status, describe_pod, get_deployment_status,
           get_namespace_events, get_pod_resource_usage, find_crashing_pods

Write operations are plain Python functions (not decorated):
  kubectl: restart_deployment, scale_deployment — call explicitly from agent code only.

GitOps and ArgoCD tools are available for future GitOps remediation workflows.
"""
from .kubectl_tools import (
    # Read-only tools
    get_pod_logs,
    get_pod_status,
    describe_pod,
    get_deployment_status,
    get_namespace_events,
    get_pod_resource_usage,
    find_crashing_pods,
    # Write operations (not decorated — not in ALL_TOOLS)
    restart_deployment,
    scale_deployment,
    # Utility
    resolve_pod_name,
)
from .git_tools import (
    list_gitops_files,
    read_gitops_file,
    create_fix_pr,
    get_git_log,
)
from .argocd_tools import (
    list_argocd_apps,
    get_argocd_app_status,
    sync_argocd_app,
    rollback_argocd_app,
)

# Read-only tools safe for LLM access (used by any future ReAct or tool-calling agent)
READONLY_TOOLS = [
    get_pod_logs,
    get_pod_status,
    describe_pod,
    get_deployment_status,
    get_namespace_events,
    get_pod_resource_usage,
    find_crashing_pods,
    list_gitops_files,
    read_gitops_file,
    get_git_log,
    list_argocd_apps,
    get_argocd_app_status,
]

# Full tool set including write operations (use only with explicit authorization)
ALL_TOOLS = READONLY_TOOLS + [
    create_fix_pr,
    sync_argocd_app,
    rollback_argocd_app,
]
