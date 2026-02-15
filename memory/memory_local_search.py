#!/usr/bin/env python3
import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class SearchFile:
    path: Path
    layer: str
    weight: float


def iter_files(root: Path) -> Iterable[SearchFile]:
    # 1) Long-term
    memory_md = root / "MEMORY.md"
    if memory_md.exists():
        yield SearchFile(memory_md, "long-term", 1.20)

    mem_dir = root / "memory"
    if not mem_dir.exists():
        return

    # 2) Global shared context
    global_ctx = mem_dir / "global-context.md"
    if global_ctx.exists():
        yield SearchFile(global_ctx, "global", 1.15)

    # 3) Channel-specific context
    channels_dir = mem_dir / "channels"
    if channels_dir.exists():
        for p in sorted(channels_dir.glob("*.md")):
            yield SearchFile(p, "channel", 1.10)

    # 4) Daily logs + other memory notes
    for p in sorted(mem_dir.glob("*.md")):
        # already yielded
        if p.name == "global-context.md":
            continue
        # low-signal templates are searchable but lower priority
        if "template" in p.name:
            yield SearchFile(p, "template", 0.70)
            continue
        yield SearchFile(p, "daily", 1.00)


def score_line(line: str, terms: list[str]) -> int:
    low = line.lower()
    return sum(low.count(t) for t in terms)


def channel_boost(path: Path, channel_hint: str | None) -> float:
    if not channel_hint:
        return 1.0
    name = path.name.lower()
    hint = channel_hint.lower().strip()
    return 1.35 if hint and hint in name else 1.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Local fallback search for layered memory files")
    ap.add_argument("query", help="Search query")
    ap.add_argument("--root", default=".", help="Workspace root")
    ap.add_argument("--max-results", type=int, default=20)
    ap.add_argument("--context", type=int, default=1)
    ap.add_argument("--channel", default="", help="Channel hint (id or slug) to prioritize channel memory files")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    terms = [t.lower() for t in re.findall(r"[\w가-힣]+", args.query) if len(t) >= 2]
    if not terms:
        print("No usable query terms")
        return 1

    # weighted_score, raw_score, layer, path, line_no, snippet
    hits: list[tuple[float, int, str, Path, int, str]] = []

    for sf in iter_files(root):
        try:
            lines = sf.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        for idx, line in enumerate(lines, start=1):
            raw = score_line(line, terms)
            if raw <= 0:
                continue

            w = sf.weight * channel_boost(sf.path, args.channel)
            weighted = raw * w

            start = max(1, idx - args.context)
            end = min(len(lines), idx + args.context)
            snippet = "\n".join(
                f"{sf.path.relative_to(root)}:{ln}:{lines[ln-1]}" for ln in range(start, end + 1)
            )
            hits.append((weighted, raw, sf.layer, sf.path, idx, snippet))

    hits.sort(key=lambda x: (-x[0], -x[1], str(x[3]), x[4]))
    if not hits:
        print("NO_MATCH")
        return 0

    for i, (ws, raw, layer, _, _, snippet) in enumerate(hits[: args.max_results], start=1):
        print(f"--- hit {i} | layer={layer} | score={raw} | weighted={ws:.2f} ---")
        print(snippet)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
