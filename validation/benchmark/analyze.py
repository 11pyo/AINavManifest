# -*- coding: utf-8 -*-
"""
실험 결과 분석 및 논문용 도표 생성

- metrics.csv 로드 후 baseline vs manifest 지표 비교
- 한글 폰트를 찾아 matplotlib에 주입
- 막대그래프(토큰 소모량, HTTP 요청 수, 성공률, 실행 시간) PNG 저장
"""
import csv
import json
import logging
import os
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ROOT = Path(__file__).resolve().parent.parent
RESULT_DIR = ROOT / "results"

# [SECURE] 화이트리스트 폰트 경로 - Path Traversal 방지 (Category 1)
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\gulim.ttc",
]
font_path = next((p for p in FONT_CANDIDATES if os.path.isfile(p)), None)
if font_path is None:
    raise FileNotFoundError("한글 폰트를 찾을 수 없습니다.")
FP = FontProperties(fname=font_path, size=11)
FP_TITLE = FontProperties(fname=font_path, size=13)

def _load():
    with open(RESULT_DIR / "metrics.json", "r", encoding="utf-8") as f:
        return json.load(f)

def _agg(rows, agent):
    r = [x for x in rows if x["agent"] == agent]
    if not r:
        return None
    def mean(k):
        return statistics.mean([x[k] for x in r])
    def std(k):
        if len(r) < 2:
            return 0.0
        return statistics.stdev([x[k] for x in r])
    success_rate = sum(1 for x in r if x["success"]) / len(r)
    return {
        "n": len(r),
        "mean_tokens": mean("input_tokens"),
        "std_tokens":  std("input_tokens"),
        "mean_http":   mean("http_requests"),
        "mean_llm":    mean("llm_calls"),
        "mean_ms":     mean("wall_time_ms"),
        "std_ms":      std("wall_time_ms"),
        "success_rate": success_rate,
    }

def _bar(ax, labels, values, yerrs, title, ylabel, colors):
    xs = list(range(len(labels)))
    ax.bar(xs, values, yerr=yerrs, color=colors, capsize=6, width=0.55,
           edgecolor="black", linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontproperties=FP)
    ax.set_title(title, fontproperties=FP_TITLE)
    ax.set_ylabel(ylabel, fontproperties=FP)
    for i, v in enumerate(values):
        ax.text(xs[i], v, f"{v:,.1f}", ha="center", va="bottom",
                fontproperties=FP, fontsize=10)

def generate_report():
    rows = _load()
    base = _agg(rows, "baseline_dom")
    mani = _agg(rows, "manifest_aware")
    if not base or not mani:
        raise RuntimeError("두 에이전트 결과가 모두 필요합니다.")

    labels = ["종래(DOM 분석)", "본 발명(매니페스트)"]
    colors = ["#C0504D", "#4F81BD"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    _bar(axes[0, 0], labels,
         [base["mean_tokens"], mani["mean_tokens"]],
         [base["std_tokens"], mani["std_tokens"]],
         "LLM 입력 토큰 소모량 (평균 ± SD)",
         "tokens / task", colors)

    _bar(axes[0, 1], labels,
         [base["success_rate"] * 100, mani["success_rate"] * 100],
         [0, 0],
         "다단계 태스크 성공률",
         "success rate (%)", colors)
    axes[0, 1].set_ylim(0, 105)

    _bar(axes[1, 0], labels,
         [base["mean_ms"], mani["mean_ms"]],
         [base["std_ms"], mani["std_ms"]],
         "End-to-End 실행 시간 (평균 ± SD)",
         "wall-clock time (ms)", colors)

    _bar(axes[1, 1], labels,
         [base["mean_llm"], mani["mean_llm"]],
         [0, 0],
         "태스크당 LLM 호출 횟수 (평균)",
         "LLM calls / task", colors)

    token_saving = (1 - mani["mean_tokens"] / base["mean_tokens"]) * 100
    fig.suptitle(
        f"AI 매니페스트 방식 vs 종래 DOM 분석 방식 비교  "
        f"(n={base['n']}, 토큰 절감률 {token_saving:.1f}%)",
        fontproperties=FP_TITLE, y=0.99,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = RESULT_DIR / "comparison.png"
    try:
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    finally:
        # [SECURE] figure 리소스 해제 - Improper Resource Release 방지 (Category 5)
        plt.close(fig)

    summary = {
        "sample_size": base["n"],
        "baseline": base,
        "manifest": mani,
        "token_saving_percent": token_saving,
        "success_rate_lift_percent": (mani["success_rate"] - base["success_rate"]) * 100,
        "http_request_delta": mani["mean_http"] - base["mean_http"],
    }
    with open(RESULT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 콘솔 요약
    print("\n=== 실험 요약 (n={}) ===".format(base["n"]))
    print(f"  LLM 입력 토큰 소모량     : baseline {base['mean_tokens']:.0f}   manifest {mani['mean_tokens']:.0f}   (절감 {token_saving:.1f}%)")
    print(f"  다단계 태스크 성공률       : baseline {base['success_rate']*100:.1f}%   manifest {mani['success_rate']*100:.1f}%")
    print(f"  End-to-End 실행시간(ms)   : baseline {base['mean_ms']:.1f}   manifest {mani['mean_ms']:.1f}")
    print(f"  태스크당 LLM 호출 횟수     : baseline {base['mean_llm']:.2f}   manifest {mani['mean_llm']:.2f}")
    print(f"  HTTP 요청 수 (평균)        : baseline {base['mean_http']:.2f}   manifest {mani['mean_http']:.2f}")
    print("\n저장 경로:")
    print(f"  {out}")
    print(f"  {RESULT_DIR / 'summary.json'}")

if __name__ == "__main__":
    generate_report()

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Path Traversal: 폰트 경로 화이트리스트
#   - Improper Resource Release: plt.close(fig) in finally, 파일은 with 블록
# Not Applied:
#   - [WARN] 외부 입력이 없으므로 입력 검증 규칙 생략
# --------------------------------------------------
