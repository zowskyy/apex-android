"""Device-adaptive limits for on-device APEX."""

from apex.device_profile import configure_device_profile, detect_tier, limits


def test_detect_tier_from_ram():
    assert detect_tier(ram_mb=3000) == "low"
    assert detect_tier(ram_mb=6000) == "medium"
    assert detect_tier(ram_mb=12000, cpu_cores=8) == "high"


def test_configure_on_device_patches_analysis():
    profile = configure_device_profile(ram_mb=4096, cpu_cores=4, engine_mode="on_device")
    assert profile["engine_mode"] == "on_device"
    assert profile["tier"] in {"low", "medium", "high"}
    from apex import analysis

    assert analysis.MAX_ENTRY_SIZE == profile["max_entry_size"]
    assert limits()["max_upload_bytes"] == profile["max_upload_bytes"]


def test_standalone_cli_help():
    from apex.cli import build_parser

    parser = build_parser()
    assert "standalone" in parser.format_help()
