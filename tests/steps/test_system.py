from hookd.steps.system import generate_env_file, generate_service_file, detect_service_manager


def test_generate_env_file(tmp_path):
    path = tmp_path / ".env"
    generate_env_file(path, secret="s3cret", github_token="ghp_xxx", port=9876)
    content = path.read_text()
    assert "HOOKD_SECRET=s3cret" in content
    assert "HOOKD_GITHUB_TOKEN=ghp_xxx" in content
    assert "HOOKD_PORT=9876" in content
    assert "HOOKD_TUNNEL=tailscale" in content


def test_generate_env_file_with_tunnel(tmp_path):
    path = tmp_path / ".env"
    generate_env_file(path, secret="s", github_token="t", port=1234, tunnel="none")
    content = path.read_text()
    assert "HOOKD_TUNNEL=none" in content


def test_detect_service_manager():
    mgr = detect_service_manager()
    assert mgr in ("systemd", "launchd", None)


def test_generate_systemd_service():
    svc = generate_service_file("systemd", workdir="/opt/hookd", port=9876)
    assert "ExecStart=" in svc
    assert "WorkingDirectory=/opt/hookd" in svc
    assert "9876" in svc
    assert "tailscaled.service" in svc
    assert "EnvironmentFile=-/opt/hookd" in svc  # dash prefix for optional


def test_generate_systemd_service_no_tailscale():
    svc = generate_service_file("systemd", workdir="/opt/hookd", port=9876, tunnel="none")
    assert "tailscaled.service" not in svc
    assert "network.target" in svc


def test_generate_systemd_service_cloudflare():
    svc = generate_service_file("systemd", workdir="/opt/hookd", port=9876, tunnel="cloudflare")
    assert "tailscaled.service" not in svc


def test_generate_launchd_plist():
    svc = generate_service_file("launchd", workdir="/opt/hookd", port=9876)
    assert "<plist" in svc
    assert "hookd" in svc
    assert "/opt/hookd" in svc
