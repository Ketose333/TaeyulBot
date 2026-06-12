from io import BytesIO
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

BG        = "#0f0e17"
PANEL     = "#16213e"
LINE      = "#c084fc"
GRID      = "#2a2a4a"
TEXT      = "#e2e8f0"
SUBTEXT   = "#94a3b8"
GOOD      = "#4ade80"
BAD       = "#f87171"
AVERAGE   = "#f9c74f"


def _setup_korean_font() -> None:
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/nanum/NanumGothic.otf",
        "C:/Windows/Fonts/malgun.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            plt.rcParams["font.family"] = prop.get_name()
            return

    for name in ["NanumGothic", "Malgun Gothic", "AppleGothic"]:
        if any(name.lower() in f.name.lower() for f in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            return


def generate_rank_chart(sign: str, daily: list[tuple[str, int]]) -> BytesIO:
    _setup_korean_font()
    plt.rcParams["axes.unicode_minus"] = False

    dates = [d for d, _ in daily]
    ranks = [r for _, r in daily]
    x     = list(range(len(dates)))
    avg   = sum(ranks) / len(ranks)

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    # 영역 채우기
    ax.fill_between(x, ranks, 12.5, alpha=0.18, color=LINE)

    # 메인 라인
    ax.plot(x, ranks, color=LINE, linewidth=2.5, solid_capstyle="round", zorder=3)

    # 평균선
    ax.axhline(y=avg, color=AVERAGE, linewidth=1.2, linestyle="--", alpha=0.7, zorder=2)

    # 포인트 (순위별 색상)
    for xi, r in zip(x, ranks):
        color = GOOD if r <= 3 else (BAD if r >= 10 else LINE)
        ax.scatter(xi, r, color=color, s=55, zorder=4, edgecolors=BG, linewidths=1.2)

    # 최고/최저 순위 표시
    best, worst = min(ranks), max(ranks)
    bi, wi = ranks.index(best), ranks.index(worst)
    ax.annotate(f"{best}위", (x[bi], best),
                xytext=(0, -14), textcoords="offset points",
                color=GOOD, fontsize=8, ha="center", fontweight="bold")
    if worst != best:
        ax.annotate(f"{worst}위", (x[wi], worst),
                    xytext=(0, 10), textcoords="offset points",
                    color=BAD, fontsize=8, ha="center", fontweight="bold")

    # Y축
    ax.set_ylim(13.2, 0.2)
    ax.set_yticks(range(1, 13))
    ax.set_yticklabels([f"{i}위" for i in range(1, 13)], color=TEXT, fontsize=8)

    # X축
    step = max(1, len(dates) // 7)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([dates[i][5:] for i in range(0, len(dates), step)],
                       color=SUBTEXT, fontsize=8)

    # 타이틀
    ax.set_title(f"{sign}  ·  이달 평균 {avg:.1f}위",
                 color=TEXT, fontsize=13, fontweight="bold", pad=14)

    # 그리드 & 테두리
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.9)
    ax.grid(axis="x", color=GRID, linewidth=0.5, alpha=0.4, linestyle=":")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.tick_params(colors=GRID, length=0)

    # 평균 라벨
    ax.text(len(x) - 0.2, avg - 0.35, f"평균 {avg:.1f}위",
            color=AVERAGE, fontsize=7.5, ha="right", alpha=0.85)

    plt.tight_layout(pad=1.5)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf
