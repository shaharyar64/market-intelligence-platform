#!/bin/bash
set -uo pipefail

# Escape hatch for ad hoc ops runs (e.g. ECS RunTask --overrides with a
# containerOverrides.command): if a command is given, run it directly instead
# of the default weekly pipeline below. No effect on the scheduled run, which
# invokes the container with no command override.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

RUN_DATE="${RUN_DATE:-$(date -u +%F)}"
LOG_FILE="$(mktemp)"

echo "[entrypoint] run date: $RUN_DATE"
python run_all_scrapers.py --date "$RUN_DATE" --extract-after 2>&1 | tee "$LOG_FILE"
SCRAPE_EXIT_CODE=${PIPESTATUS[0]}

echo "[entrypoint] running cleaning.py for $RUN_DATE" | tee -a "$LOG_FILE"
python cleaning.py --date "$RUN_DATE" 2>&1 | tee -a "$LOG_FILE"
CLEAN_EXIT_CODE=${PIPESTATUS[0]}

if [ "$CLEAN_EXIT_CODE" -eq 0 ]; then
  echo "[entrypoint] running generate_weekly_report.py for $RUN_DATE" | tee -a "$LOG_FILE"
  python generate_weekly_report.py --date "$RUN_DATE" 2>&1 | tee -a "$LOG_FILE"
  REPORT_EXIT_CODE=${PIPESTATUS[0]}
  if [ "$REPORT_EXIT_CODE" -ne 0 ]; then
    echo "[entrypoint] WARNING: weekly report generation/email failed (exit=$REPORT_EXIT_CODE), continuing anyway" | tee -a "$LOG_FILE"
  fi
else
  echo "[entrypoint] skipping weekly report: cleaning.py failed" | tee -a "$LOG_FILE"
fi

FINAL_EXIT_CODE=$SCRAPE_EXIT_CODE
if [ "$CLEAN_EXIT_CODE" -ne 0 ]; then
  FINAL_EXIT_CODE=$CLEAN_EXIT_CODE
fi

python3 /app/notify_discord.py "$SCRAPE_EXIT_CODE" "$RUN_DATE" "$LOG_FILE" "$CLEAN_EXIT_CODE"

exit "$FINAL_EXIT_CODE"
