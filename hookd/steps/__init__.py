from hookd.steps.detect import detect_git_context, GitContext
from hookd.steps.preflight import check_dependencies, check_tailscale, PreflightResult, TailscaleStatus
from hookd.steps.github import validate_token, create_webhook, list_webhooks, delete_webhook, update_webhook_secret
from hookd.steps.system import detect_service_manager, generate_service_file, generate_env_file, install_service
from hookd.steps.funnel import get_tailscale_hostname, get_funnel_url, enable_funnel, disable_funnel

__all__ = [
    "detect_git_context", "GitContext",
    "check_dependencies", "check_tailscale", "PreflightResult", "TailscaleStatus",
    "validate_token", "create_webhook", "list_webhooks", "delete_webhook", "update_webhook_secret",
    "detect_service_manager", "generate_service_file", "generate_env_file", "install_service",
    "get_tailscale_hostname", "get_funnel_url", "enable_funnel", "disable_funnel",
]
