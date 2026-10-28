"""
Run site scrapers with limited parallelism.

Default concurrency is 3 to avoid putting too much load on browser/API-backed
collectors at the same time.
"""

import argparse
import asyncio
import contextlib
import os
import shlex
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent

# A single hung scraper (e.g. a site whose browser pages keep crashing) must
# not be able to block the rest of the run and the post-run notification
# indefinitely. Longest observed scraper under normal conditions is ~18min.
DEFAULT_SCRAPER_TIMEOUT_SECONDS = 30 * 60

SCRAPERS = {
    "africanandeastern": "sites/africanandeastern.py",
    "africaneasternonline_auh": "sites/africaneasternonline_.py --store auh",
    "bdutyfree": "sites/bdutyfree.py",
    "bmmishops": "sites/bmmishops.py",
    "centaurusint": "sites/centaurusint.py",
    "citydrinks": "sites/citydrinks.py",
    "dubaidutyfree": "sites/dubaidutyfree.py",
    "gbiexpress": "sites/gbiexpress.py",
    "gmp": "sites/gmp.py",
    "highspiritsuae": "sites/highspiritsuae.py",
    "jmkcellars": "sites/jmkcellars.py",
    "africaneasternonline_rak": "sites/africaneasternonline_.py --store rak",
    "mmihomedelivery_dubai": "sites/mmihomedelivery_dubai.py",
    "mmihomedelivery_rak": "sites/mmihomedelivery_rak.py",
    "nhsc": "sites/nhsc.py",
    "premiumcellars": "sites/premiumcellars.py",
    "royalspirit": "sites/royalspirit.py",
    "spinneysauh": "sites/spinneysauh.py",
    "supercellar": "sites/supercellar.py",
    "thebottlestoredelivery": "sites/thebottlestoredelivery.py",
    "unisatgt": "sites/unisatgt.py",
    "africaneasternonline_dubai": "sites/africaneasternonline_.py --store dubai",
    "windmillgt": "sites/windmillgt.py",
}

EXTRACT_SITE_BY_SCRAPER = {
    "africanandeastern": "africanandeastern",
    "africaneasternonline_auh": "africaneastern_auh",
    "africaneasternonline_dubai": "africaneastern_dubai",
    "africaneasternonline_rak": "africaneastern_rak",
    "bdutyfree": "bdutyfree",
    "bmmishops": "bmmishops",
    "centaurusint": "centaurusint",
    "citydrinks": "citydrinks",
    "dubaidutyfree": "dubaidutyfree",
    "gbiexpress": "gbiexpress",
    "gmp": "gmp",
    "highspiritsuae": "highspiritsuae",
    "jmkcellars": "jmkcellars",
    "mmihomedelivery_dubai": "mmihomedelivery_dubai",
    "mmihomedelivery_rak": "mmihomedelivery_rak",
    "nhsc": "nhsc",
    "premiumcellars": "premiumcellars",
    "royalspirit": "royalspirit",
    "spinneysauh": "spinneysauh",
    "supercellar": "supercellar",
    "thebottlestoredelivery": "thebottlestore",
    "unisatgt": "unisatgt",
    "windmillgt": "windmillgt",
}


def _parse_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _command_parts(command: str) -> list[str]:
    return shlex.split(command)


def _script_path(command: str) -> Path:
    parts = _command_parts(command)
    if not parts:
        raise SystemExit("Empty scraper command configured.")
    return ROOT_DIR / parts[0]


def _format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _select_scrapers(only: str, exclude: str) -> list[tuple[str, str]]:
    names = list(SCRAPERS)

    if only:
        requested = _parse_csv(only)
        unknown = requested - set(SCRAPERS)
        if unknown:
            raise SystemExit(f"Unknown scraper(s): {', '.join(sorted(unknown))}")
        names = [name for name in names if name in requested]

    if exclude:
        excluded = _parse_csv(exclude)
        unknown = excluded - set(SCRAPERS)
        if unknown:
            raise SystemExit(f"Unknown scraper(s): {', '.join(sorted(unknown))}")
        names = [name for name in names if name not in excluded]

    return [(name, SCRAPERS[name]) for name in names]


async def _pipe_output(stream: asyncio.StreamReader, prefix: str) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        print(f"[{prefix}] {line.decode(errors='replace').rstrip()}", flush=True)


async def _run_scraper(
    name: str, command: str, date: str, semaphore: asyncio.Semaphore, timeout: float
) -> dict:
    async with semaphore:
        started = time.monotonic()
        parts = _command_parts(command)
        script = ROOT_DIR / parts[0]
        script_args = parts[1:]

        script_args.extend(["--date", date])

        print(f"[runner] START {name}: {command} --date {date}", flush=True)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            *script_args,
            cwd=str(ROOT_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=True,  # own process group, so a hung browser's
            # child processes (e.g. Chromium) can be killed alongside it
        )

        pipe_task = asyncio.gather(
            _pipe_output(process.stdout, name),
            _pipe_output(process.stderr, f"{name}:err"),
        )

        timed_out = False
        try:
            await asyncio.wait_for(asyncio.shield(pipe_task), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            print(
                f"[runner] TIMEOUT {name} exceeded {int(timeout)}s, killing process group",
                flush=True,
            )
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            # give the killed process a moment to close its pipes so
            # _pipe_output can drain and exit cleanly
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(pipe_task, timeout=10)

        return_code = await process.wait()
        elapsed = round(time.monotonic() - started, 2)
        status = "TIMEOUT" if timed_out else ("OK" if return_code == 0 else "FAILED")
        print(f"[runner] {status} {name} exit={return_code} seconds={elapsed}", flush=True)

        return {
            "name": name,
            "command": command,
            "return_code": return_code,
            "elapsed": elapsed,
            "timed_out": timed_out,
        }


async def _run_all(
    selected: list[tuple[str, str]], concurrency: int, date: str, scraper_timeout: float
) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)
    total = len(selected)
    completed = 0
    results = []
    started = time.monotonic()
    tasks = [
        asyncio.create_task(_run_scraper(name, script, date, semaphore, scraper_timeout))
        for name, script in selected
    ]

    print(f"[runner] Progress: completed=0 remaining={total}", flush=True)

    for task in asyncio.as_completed(tasks):
        result = await task
        completed += 1
        remaining = total - completed
        results.append(result)
        failed = sum(1 for item in results if item["return_code"] != 0)
        elapsed = _format_duration(time.monotonic() - started)
        print(
            f"[runner] Progress: completed={completed}/{total} "
            f"remaining={remaining} failed={failed} elapsed={elapsed}",
            flush=True,
        )

    return results


async def _run_extraction(site_names: list[str], date: str) -> int:
    command = [
        sys.executable,
        str(ROOT_DIR / "extract_from_html_manifests.py"),
        "--date",
        date,
        "--only",
        ",".join(site_names),
    ]

    print(f"[runner] START extraction: {' '.join(command)}", flush=True)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(ROOT_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    await asyncio.gather(
        _pipe_output(process.stdout, "extract"),
        _pipe_output(process.stderr, "extract:err"),
    )

    return_code = await process.wait()
    status = "OK" if return_code == 0 else "FAILED"
    print(f"[runner] {status} extraction exit={return_code}", flush=True)
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all scraper scripts with limited concurrency."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Maximum scrapers to run at once. Default: 3.",
    )
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used by scrapers and extraction. Default: today UTC.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated scraper names to run.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated scraper names to skip.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scraper names and exit.",
    )
    parser.add_argument(
        "--extract-after",
        action="store_true",
        help="Run extract_from_html_manifests.py for successful scrapers after raw collection.",
    )
    parser.add_argument(
        "--scraper-timeout",
        type=float,
        default=DEFAULT_SCRAPER_TIMEOUT_SECONDS,
        help=(
            "Max seconds a single scraper may run before it is killed and "
            f"marked as a timeout. Default: {DEFAULT_SCRAPER_TIMEOUT_SECONDS}s."
        ),
    )
    args = parser.parse_args()

    if args.list:
        for name in SCRAPERS:
            print(name)
        return 0

    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")
    if args.concurrency > 3:
        raise SystemExit("Do not use --concurrency above 3; it can overload browser/API-backed collectors.")

    selected = _select_scrapers(args.only, args.exclude)
    if not selected:
        raise SystemExit("No scrapers selected.")

    missing = [(name, _script_path(command)) for name, command in selected if not _script_path(command).exists()]
    if missing:
        missing_names = ", ".join(f"{name} ({script})" for name, script in missing)
        raise SystemExit(f"Missing scraper file(s): {missing_names}")

    print(
        f"[runner] Running {len(selected)} scraper(s) with concurrency={args.concurrency}",
        flush=True,
    )
    started = time.monotonic()
    results = asyncio.run(
        _run_all(selected, args.concurrency, args.date, args.scraper_timeout)
    )
    total_elapsed = time.monotonic() - started

    failed = [result for result in results if result["return_code"] != 0]
    extraction_return_code = 0

    if args.extract_after:
        successful_scrapers = [
            result["name"]
            for result in results
            if result["return_code"] == 0
        ]
        extract_sites = [
            EXTRACT_SITE_BY_SCRAPER[name]
            for name in successful_scrapers
            if name in EXTRACT_SITE_BY_SCRAPER
        ]

        if extract_sites:
            extraction_return_code = asyncio.run(_run_extraction(extract_sites, args.date))
        else:
            print("[runner] No successful scraper manifests to extract.", flush=True)

    print(
        f"[runner] Summary total_time={_format_duration(total_elapsed)} "
        f"seconds={round(total_elapsed, 2)}",
        flush=True,
    )
    for result in results:
        if result.get("timed_out"):
            status = "TIMEOUT"
        elif result["return_code"] == 0:
            status = "OK"
        else:
            status = "FAILED"
        print(
            f"[runner] {status:<7} {result['name']:<28} "
            f"exit={result['return_code']} seconds={result['elapsed']}",
            flush=True,
        )

    return 1 if failed or extraction_return_code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
