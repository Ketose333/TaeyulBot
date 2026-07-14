import os

from langchain_core.tools import tool

WORKSPACE_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "workspace")
)
MAX_READ_BYTES = 200_000
MAX_WRITE_BYTES = 200_000


def _resolve_safe_path(relative_path: str) -> str:
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    candidate = os.path.realpath(os.path.join(WORKSPACE_ROOT, relative_path))
    if candidate != WORKSPACE_ROOT and not candidate.startswith(WORKSPACE_ROOT + os.sep):
        raise ValueError(f"경로가 워크스페이스 루트({WORKSPACE_ROOT}) 밖을 가리킵니다: {relative_path}")
    return candidate


@tool
def read_file(relative_path: str) -> str:
    """워크스페이스 루트(data/workspace) 안의 파일을 읽어 텍스트로 반환한다. relative_path는 워크스페이스 루트 기준 상대 경로."""
    path = _resolve_safe_path(relative_path)
    if not os.path.isfile(path):
        return f"파일이 존재하지 않습니다: {relative_path}"
    if os.path.getsize(path) > MAX_READ_BYTES:
        return f"파일이 너무 큽니다({MAX_READ_BYTES} bytes 초과): {relative_path}"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


@tool
def write_file(relative_path: str, content: str) -> str:
    """워크스페이스 루트(data/workspace) 안에 파일을 새로 쓰거나 덮어쓴다. 상위 디렉토리가 없으면 생성한다."""
    if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
        return f"내용이 너무 큽니다({MAX_WRITE_BYTES} bytes 초과)."
    path = _resolve_safe_path(relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"저장 완료: {relative_path}"


@tool
def edit_file(relative_path: str, old_string: str, new_string: str) -> str:
    """워크스페이스 루트 안 파일에서 old_string을 new_string으로 1회 치환한다. old_string은 파일 내 고유해야 한다."""
    path = _resolve_safe_path(relative_path)
    if not os.path.isfile(path):
        return f"파일이 존재하지 않습니다: {relative_path}"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    count = text.count(old_string)
    if count == 0:
        return f"old_string을 찾지 못했습니다: {relative_path}"
    if count > 1:
        return f"old_string이 파일 내에서 고유하지 않습니다({count}회 발견): {relative_path}"
    text = text.replace(old_string, new_string, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return f"수정 완료: {relative_path}"


@tool
def list_workspace_files() -> str:
    """워크스페이스 루트(data/workspace) 안의 파일 목록을 상대 경로로 반환한다."""
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    entries = []
    for root, _dirs, files in os.walk(WORKSPACE_ROOT):
        for name in files:
            full = os.path.join(root, name)
            entries.append(os.path.relpath(full, WORKSPACE_ROOT))
    if not entries:
        return "워크스페이스가 비어 있습니다."
    return "\n".join(sorted(entries))


FS_TOOLS = [read_file, write_file, edit_file, list_workspace_files]
