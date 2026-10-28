"""Posts a run summary to Discord, parsed from run_all_scrapers.py's [runner]
log lines and cleaning.py's reconciliation/write output."""

import os
import sys

import requests


def main() -> None:
    scrape_exit_code, run_date, log_file = sys.argv[1:4]
    clean_exit_code = sys.argv[4] if len(sys.argv) > 4 else None

    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("[notify] DISCORD_WEBHOOK_URL not set, skipping notification")
        return

    with open(log_file, errors="replace") as f:
        all_lines = list(f)

    # run_all_scrapers.py prints each scraper's status twice: once live as it
    # finishes, and once more in the final summary table after the
    # "[runner] Summary" line. Only count the final table to avoid double-counting.
    summary_idx = next((i for i, line in enumerate(all_lines) if line.startswith("[runner] Summary")), None)
    summary_line = all_lines[summary_idx].strip() if summary_idx is not None else ""
    final_lines = all_lines[summary_idx + 1 :] if summary_idx is not None else []

    ok = [line for line in final_lines if line.startswith("[runner] OK")]
    # A killed/timed-out scraper prints "[runner] TIMEOUT", not "FAILED" —
    # it still produced no data and must count as a failure, not vanish from
    # both tallies (see 2026-08-18: africanandeastern timed out and was
    # silently dropped from this report).
    failed = [
        line
        for line in final_lines
        if line.startswith("[runner] FAILED") or line.startswith("[runner] TIMEOUT")
    ]

    scrape_status = "✅ Success" if scrape_exit_code == "0" else "⚠️ Completed with failures"
    lines = [
        f"**Price Scraper run — {run_date}**",
        f"Scrape status: {scrape_status} (exit code {scrape_exit_code})",
        summary_line.removeprefix("[runner] ").strip(),
        f"Succeeded: {len(ok)}  Failed: {len(failed)}",
    ]
    if failed:
        lines.append("Failed scrapers:")
        lines.extend(
            "- " + line.removeprefix("[runner] FAILED").removeprefix("[runner] TIMEOUT").strip()
            for line in failed
        )

    if clean_exit_code is not None:
        corrected_lines = [line.strip() for line in all_lines if "row(s) corrected from source of truth" in line]
        matched_line = next((line.strip() for line in all_lines if "rows matched a link in products_source" in line), "")
        wrote_line = next((line.strip() for line in all_lines if line.startswith("Wrote ") and "plaformsV2" in line), "")

        clean_status = "✅ Success" if clean_exit_code == "0" else "⚠️ Failed"
        lines.append("")
        lines.append(f"Cleaning/DB push status: {clean_status} (exit code {clean_exit_code})")
        if matched_line:
            lines.append(matched_line)
        if corrected_lines:
            lines.append("Corrected from source of truth:")
            lines.extend("- " + line for line in corrected_lines)
        if wrote_line:
            lines.append(wrote_line)

    content = "\n".join(line for line in lines if line)[:1900]

    try:
        resp = requests.post(webhook, json={"content": content}, timeout=10)
        print(f"[notify] discord webhook responded {resp.status_code}")
    except requests.RequestException as e:
        print(f"[notify] failed to send discord webhook: {e}")


if __name__ == "__main__":
    main()
