from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

ALLOWED_DIRS = [
    PROJECT_ROOT / "dbt" / "models",
]


def _safe_path(file_path: str) -> Path:
    path = (PROJECT_ROOT / file_path).resolve()
    if not any(path.is_relative_to(d) for d in ALLOWED_DIRS):
        raise ValueError(f"Access denied: {file_path} is outside allowed directories.")
    return path


def read_yaml_file(file_path: str) -> str:
    path = _safe_path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    return path.read_text()


def write_yaml_file(file_path: str, content: str) -> dict:
    path = _safe_path(file_path)
    path.write_text(content)
    return {"status": "ok", "file": file_path}
