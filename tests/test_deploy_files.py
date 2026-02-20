from pathlib import Path


def test_vercel_config_and_entrypoint_exist() -> None:
    assert Path("vercel.json").exists()
    assert Path("api/index.py").exists()
