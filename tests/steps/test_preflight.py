from hookd.steps.preflight import check_dependencies, PreflightResult


def test_reports_missing():
    result = check_dependencies(required=["git", "nonexistent_xyz_binary"])
    assert "nonexistent_xyz_binary" in result.missing
    assert "git" in result.found
    assert not result.all_ok


def test_all_present():
    result = check_dependencies(required=["git", "bash"])
    assert result.all_ok
    assert len(result.missing) == 0


def test_empty_required():
    result = check_dependencies(required=[])
    assert result.all_ok
