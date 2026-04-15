from .kubectl_tools import (
    get_pod_logs,
    get_pod_status,
    describe_pod,
    get_deployment_status,
    get_namespace_events,
    restart_deployment,
    scale_deployment,
    get_pod_resource_usage,
    find_crashing_pods,
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

ALL_TOOLS = [
    # Kubectl investigation tools
    get_pod_logs,
    get_pod_status,
    describe_pod,
    get_deployment_status,
    get_namespace_events,
    restart_deployment,
    scale_deployment,
    get_pod_resource_usage,
    find_crashing_pods,
    # GitOps tools
    list_gitops_files,
    read_gitops_file,
    create_fix_pr,
    get_git_log,
    # ArgoCD tools
    list_argocd_apps,
    get_argocd_app_status,
    sync_argocd_app,
    rollback_argocd_app,
]
