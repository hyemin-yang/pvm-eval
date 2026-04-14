"""
judge_results.json을 파싱해 verdict 분포와 혼동행렬을 출력한다.

Usage (CLI):
    pvm eval results --run-dir .pvm/prompts/{id}/versions/{ver}/judge/{hash}

Usage (직접 실행):
    python -m pvm.eval_pipeline.show_results \
        --run-dir .pvm/prompts/{id}/versions/{ver}/judge/{hash}
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def show_results(run_dir: Path) -> None:
    results_path = run_dir / "judge_results.json"
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)

    traces = data["results"]
    total = len(traces)
    judge_type = data.get("judge_type", "pointwise")

    # ── verdict 분포 ──────────────────────────────────────────────────────────
    verdict_counts = Counter(t["judge_verdict"] for t in traces)

    verdict_table = Table(box=box.ROUNDED, show_footer=True, footer_style="bold")
    verdict_table.add_column("Verdict", footer="합계")
    verdict_table.add_column("Count", justify="right", footer=str(total))
    verdict_table.add_column("Ratio", justify="right", footer="100.0%")

    if judge_type == "pairwise":
        verdicts_order = ["A", "B", "SAME", "PARSE_ERROR"]
        styles = {"A": "cyan", "B": "magenta", "SAME": "blue", "PARSE_ERROR": "yellow"}
    else:
        verdicts_order = ["Pass", "Fail", "PARSE_ERROR"]
        styles = {"Pass": "green", "Fail": "red", "PARSE_ERROR": "yellow"}

    for verdict in verdicts_order:
        c = verdict_counts.get(verdict, 0)
        if c > 0:
            style = styles.get(verdict, "white")
            verdict_table.add_row(
                Text(verdict, style=style),
                str(c),
                f"{c / total * 100:.1f}%",
            )

    console.print(Panel(verdict_table, title="[bold]Judge 평가 결과[/bold]", border_style="blue"))

    # ── 혼동행렬 ──────────────────────────────────────────────────────────────
    labeled = [t for t in traces if t.get("human_label") and not t.get("excluded_from_metrics")]
    if not labeled:
        console.print("[yellow]라벨 있는 트레이스 없음 — 혼동행렬 생략[/yellow]")
        return

    n = len(labeled)

    if judge_type == "pairwise":
        correct = sum(1 for t in labeled if t["judge_verdict"] == t["human_label"])
        accuracy = correct / n * 100 if n else 0.0
        metrics_text = (
            f"[bold]Accuracy[/bold] {accuracy:.1f}%"
            f"   [dim](라벨 있는 {n}건 기준, {correct}건 정답)[/dim]"
        )
        console.print(metrics_text)
    else:
        tp = sum(1 for t in labeled if t["judge_verdict"] == "Pass" and t["human_label"].lower() == "pass")
        tn = sum(1 for t in labeled if t["judge_verdict"] == "Fail" and t["human_label"].lower() == "fail")
        fp = sum(1 for t in labeled if t["judge_verdict"] == "Pass" and t["human_label"].lower() == "fail")
        fn = sum(1 for t in labeled if t["judge_verdict"] == "Fail" and t["human_label"].lower() == "pass")

        cm_table = Table(box=box.ROUNDED, show_header=True)
        cm_table.add_column("Judge \\ Human", style="bold")
        cm_table.add_column("Human: Pass", justify="center")
        cm_table.add_column("Human: Fail", justify="center")
        cm_table.add_row(
            Text("Judge: Pass", style="green"),
            Text(f"{tp}  (TP)", style="green"),
            Text(f"{fp}  (FP)", style="red"),
        )
        cm_table.add_row(
            Text("Judge: Fail", style="red"),
            Text(f"{fn}  (FN)", style="yellow"),
            Text(f"{tn}  (TN)", style="green"),
        )

        acc  = (tp + tn) / n * 100 if n else 0.0
        prec = tp / (tp + fp) * 100 if (tp + fp) else 0.0
        rec  = tp / (tp + fn) * 100 if (tp + fn) else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

        metrics_text = (
            f"[bold]Accuracy[/bold] {acc:.1f}%   "
            f"[bold]Precision[/bold] {prec:.1f}%   "
            f"[bold]Recall[/bold] {rec:.1f}%   "
            f"[bold]F1[/bold] {f1:.1f}%"
            f"   [dim](라벨 있는 {n}건 기준)[/dim]"
        )
        console.print(
            Panel(cm_table, title="[bold]혼동행렬  Judge 예측 vs Human 정답[/bold]", border_style="blue")
        )
        console.print(metrics_text)

        # ── FP / FN 케이스 상세 ───────────────────────────────────────────────
        fp_cases = [t for t in labeled if t["judge_verdict"] == "Pass" and t["human_label"].lower() == "fail"]
        fn_cases = [t for t in labeled if t["judge_verdict"] == "Fail" and t["human_label"].lower() == "pass"]

        if fp_cases:
            fp_table = Table(box=box.SIMPLE, show_header=False)
            fp_table.add_column("trace_id", style="red")
            for t in fp_cases:
                fp_table.add_row(t["trace_id"])
            console.print(
                Panel(
                    fp_table,
                    title=f"[bold red]FP  {len(fp_cases)}건  Judge=Pass / Human=Fail[/bold red]",
                    border_style="red",
                )
            )

        if fn_cases:
            fn_table = Table(box=box.SIMPLE, show_header=False)
            fn_table.add_column("trace_id", style="yellow")
            for t in fn_cases:
                fn_table.add_row(t["trace_id"])
            console.print(
                Panel(
                    fn_table,
                    title=f"[bold yellow]FN  {len(fn_cases)}건  Judge=Fail / Human=Pass[/bold yellow]",
                    border_style="yellow",
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, help="pipeline HASH_DIR 경로")
    args = parser.parse_args()
    show_results(Path(args.run_dir))
