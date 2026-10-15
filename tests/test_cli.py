"""main.py as a real process. None of these reach the network: each exits before the pipeline starts,
or swaps asyncio.run for a stub."""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run_main(args, env_overrides, **kwargs):
    env = {**os.environ, **env_overrides}
    return subprocess.run([sys.executable, *args], cwd=REPO, env=env, capture_output=True, timeout=60, **kwargs)


def test_missing_api_keys_exit_2_with_a_clear_message():
    # Empty, not absent: load_dotenv() never overrides a set variable, so a real .env can't make this a live run
    result = run_main(["main.py", "x"], {"GROQ_API_KEY": "", "TAVILY_API_KEY": ""}, text=True)
    assert result.returncode == 2
    assert "missing TAVILY_API_KEY and GROQ_API_KEY. Add them to a .env file" in result.stderr
    assert "Traceback" not in result.stderr


def test_blank_topic_is_rejected():
    result = run_main(["main.py", "   "], {}, text=True)
    assert result.returncode == 2 and "must not be empty" in result.stderr


def test_overlong_topic_is_rejected():
    result = run_main(["main.py", "x" * 400], {}, text=True)
    assert result.returncode == 2 and "too long" in result.stderr


def test_unicode_output_survives_a_non_utf8_console():
    # Run main.py's real __main__ block with asyncio.run replaced by a stub that prints characters cp1252 can't encode
    code = ("import asyncio, runpy, sys; sys.argv = ['main.py', 'x']; "
            "asyncio.run = lambda coro: (coro.close(), print('State‑of‑the‑art CO₂ ≈ →'), 0)[2]; "
            "runpy.run_path('main.py', run_name='__main__')")
    result = run_main(["-c", code], {"PYTHONUTF8": "0", "PYTHONIOENCODING": ""})
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert "CO₂ ≈ →".encode() in result.stdout
