from io import BytesIO
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.transforms import blended_transform_factory

# Discord 다크 모드 팔레트 (임베드 배경과 자연스럽게 블렌딩)
BG        = "#2b2d31"   # 바깥 배경 = Discord 임베드 배경색
PANEL     = "#1e1f22"   # 플롯 영역 (한 단계 더 어둡게 — 깊이감)
LINE      = "#c4b5fd"   # 메인 라인 (밝은 퍼플 — 어두운 패널 위 가시성↑)
GRID      = "#3a3d44"   # 중성 그레이 그리드
TEXT      = "#f2f3f5"   # Discord 본문 텍스트색
SUBTEXT   = "#b5bac1"   # Discord 보조 텍스트색
GOOD      = "#57f287"   # Discord 브랜드 그린 (상위, 밝게)
BAD       = "#ed4245"   # Discord 브랜드 레드 (하위)
AVERAGE   = "#fee75c"   # Discord 브랜드 옐로 (평균선)


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

    fig, ax = plt.subplots(figsize=(8.6, 4.6), constrained_layout=True)
    # 그림 가장자리 여백을 넉넉하게 (실서비스 차트 톤에 맞춤)
    fig.set_constrained_layout_pads(w_pad=0.18, h_pad=0.18, wspace=0, hspace=0)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    # 영역 채우기
    ax.fill_between(x, ranks, 12.5, alpha=0.22, color=LINE)

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

    # X축 범위 (데이터가 패널 전체에 균등하게 차도록 명시)
    ax.set_xlim(-0.4, (len(x) - 1) + 0.4)

    # Y축
    ax.set_ylim(13.2, 0.2)
    ax.set_yticks(range(1, 13))
    ax.set_yticklabels([f"{i}위" for i in range(1, 13)], color=TEXT, fontsize=8)

    # X축
    step = max(1, len(dates) // 7)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([dates[i][5:] for i in range(0, len(dates), step)],
                       color=SUBTEXT, fontsize=8)

    # 타이틀 없음 — Discord 임베드 제목이 맥락 제공 (sign 인자는 시그니처 유지용)

    # 그리드 & 테두리
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.9)
    ax.grid(axis="x", color=GRID, linewidth=0.5, alpha=0.4, linestyle=":")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.tick_params(colors=GRID, length=0)

    # 평균 라벨 (패널 안쪽 오른쪽 끝에 고정 — x는 축 비율, y는 데이터 좌표)
    label_trans = blended_transform_factory(ax.transAxes, ax.transData)
    ax.text(0.985, avg - 0.3, f"평균 {avg:.1f}위",
            transform=label_trans, color=AVERAGE, fontsize=7.5,
            ha="right", va="bottom", alpha=0.85, zorder=5)

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf
