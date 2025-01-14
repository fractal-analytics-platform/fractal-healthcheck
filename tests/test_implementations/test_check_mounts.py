from fractal_healthcheck.checks.implementations import check_mounts


def test_check_mounts():
    out = check_mounts(mounts=["/tmp"])
    assert out.success
