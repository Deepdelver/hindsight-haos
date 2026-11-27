#!/usr/bin/env python3
"""Regression tests for cont-init provider handling (30-config.sh).

Executes the real cont-init script with a BASH_ENV stub for bashio and the
system jq, in a tempdir via HINDSIGHT_DATA_DIR / HINDSIGHT_ENV_FILE overrides.
Guards the 'custom' -> 'openai' mapping that fixes the crash-loop where the
Hindsight API rejects llm_provider=custom:

a. custom + llm_base_url, empty key  -> openai, base URL kept, placeholder
   key 'local' (never 'sk-'), exactly one provider line.
b. custom without llm_base_url       -> bashio::exit.nok, clear error.
c. simple + custom                   -> llamacpp, no base URL, no placeholder.
d. custom with a real key            -> key passed through unchanged.
e. env_vars HINDSIGHT_API_LLM_PROVIDER override -> ignored, no 'custom' leaks.
f. expert + openai without key       -> still blocked.
g. simple + openai without key       -> still keyless llamacpp (no regression).
h. expert + all four consolidation options -> exact HINDSIGHT_API_CONSOLIDATION_LLM_* mapping.
i. expert + only consolidation model -> only that one var emitted (others fall back upstream).
j. consolidation options absent      -> no consolidation var (today's behaviour).
k. simple + stored consolidation options -> ignored, no consolidation var.
l. expert + consolidation model, no cap -> max completion tokens defaults 8192.
m. expert + consolidation_max_completion_tokens -> value passed through verbatim.
n. expert without a consolidation LLM -> max completion tokens not emitted.

No third-party deps. Run: python3 hindsight/tests/test_continit_providers.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "hindsight" / "rootfs" / "etc" / "cont-init.d" / "30-config.sh"

STUB_BASHIO = """\
bashio::config() {
    if [ "$1" = "env_vars" ]; then
        printf '%s\\n' "${FAKE_ENV_VARS_JSON:-[]}"
    else
        printf '%s\\n' ""
    fi
}
bashio::log.info()    { :; }
bashio::log.warning() { printf 'WARNING: %s\\n' "$*" >&2; }
bashio::log.error()   { printf 'ERROR: %s\\n' "$*" >&2; }
bashio::exit.nok()    { exit 17; }
"""


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
        return True
    print(f"FAIL  {name}  {detail}")
    return False


def run_continit(options, env_vars=None):
    """Run the real cont-init in a tempdir; return (rc, env_lines, output)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        stub = td / "stub-bashio.sh"
        stub.write_text(STUB_BASHIO)
        data_dir = td / "data" / "hindsight"
        env_file = data_dir / "env"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "BASH_ENV": str(stub),
            "HINDSIGHT_DATA_DIR": str(data_dir),
            "HINDSIGHT_ENV_FILE": str(env_file),
            "FAKE_ENV_VARS_JSON": json.dumps(env_vars if env_vars is not None else []),
        }
        env.update(options)
        result = subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True, env=env, input=""
        )
        lines = env_file.read_text().splitlines() if env_file.exists() else []
        return result.returncode, lines, result.stdout + result.stderr


def env_dict(lines):
    """Last value wins, mirroring how services.d/hindsight/run sources the file."""
    out = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def provider_lines(lines):
    return [l for l in lines if l.startswith("HINDSIGHT_API_LLM_PROVIDER=")]


def consolidation_lines(lines):
    return [l for l in lines if l.startswith("HINDSIGHT_API_CONSOLIDATION_LLM_")]


def main():
    ok = True
    if not SCRIPT.is_file():
        print(f"FAIL  cont-init script missing: {SCRIPT}")
        return 1
    if shutil.which("jq") is None:
        print("FAIL  jq is required to run cont-init (install jq)")
        return 1
    if shutil.which("bash") is None:
        print("FAIL  bash is required to run cont-init")
        return 1

    gw = "http://gw:20128/api/v1"

    # (a) custom + base_url, empty key -> mapped openai + placeholder 'local'.
    rc, lines, out = run_continit(
        {
            "mode": "expert",
            "llm_provider": "custom",
            "llm_base_url": gw,
            "llm_model": "combo",
        }
    )
    env = env_dict(lines)
    ok &= check("a: custom+base_url exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "a: provider mapped to openai",
        env.get("HINDSIGHT_API_LLM_PROVIDER") == "openai",
        f"env={env}",
    )
    ok &= check(
        "a: exactly one provider line",
        len(provider_lines(lines)) == 1,
        f"lines={provider_lines(lines)}",
    )
    ok &= check("a: base URL preserved", env.get("HINDSIGHT_API_LLM_BASE_URL") == gw, f"env={env}")
    ok &= check(
        "a: placeholder key 'local'", env.get("HINDSIGHT_API_LLM_API_KEY") == "local", f"env={env}"
    )
    ok &= check("a: no sk- token in env", not any("sk-" in l for l in lines), f"lines={lines}")

    # (b) custom without base_url -> fail fast with a clear message.
    rc, lines, out = run_continit({"mode": "expert", "llm_provider": "custom"})
    ok &= check("b: custom without base_url exits nok", rc == 17, f"rc={rc}")
    ok &= check("b: error mentions llm_base_url", "llm_base_url" in out, f"out={out!r}")
    ok &= check("b: no env file written", not lines, f"lines={lines}")

    # (c) simple + custom -> local llamacpp stack, no base URL, no placeholder.
    rc, lines, out = run_continit(
        {
            "mode": "simple",
            "llm_provider": "custom",
            "llm_base_url": gw,
            "llm_api_key": "leftover-key",
        }
    )
    env = env_dict(lines)
    ok &= check("c: simple+custom exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "c: provider forced to llamacpp",
        env.get("HINDSIGHT_API_LLM_PROVIDER") == "llamacpp",
        f"env={env}",
    )
    ok &= check("c: no base URL in env", "HINDSIGHT_API_LLM_BASE_URL" not in env, f"env={env}")
    ok &= check(
        "c: no API key / placeholder in env", "HINDSIGHT_API_LLM_API_KEY" not in env, f"env={env}"
    )

    # (d) custom with a real key -> key passed through unchanged.
    rc, lines, out = run_continit(
        {
            "mode": "expert",
            "llm_provider": "custom",
            "llm_base_url": gw,
            "llm_api_key": "my-gateway-secret",
        }
    )
    env = env_dict(lines)
    ok &= check("d: custom with key exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "d: provider mapped to openai",
        env.get("HINDSIGHT_API_LLM_PROVIDER") == "openai",
        f"env={env}",
    )
    ok &= check(
        "d: user key preserved",
        env.get("HINDSIGHT_API_LLM_API_KEY") == "my-gateway-secret",
        f"env={env}",
    )

    # (e) env_vars tries to override the provider -> ignored, no 'custom' leak.
    for label, env_vars in (
        ("object form", [{"name": "HINDSIGHT_API_LLM_PROVIDER", "value": "custom"}]),
        ("KEY=VALUE form", ["HINDSIGHT_API_LLM_PROVIDER=custom"]),
    ):
        rc, lines, out = run_continit(
            {"mode": "expert", "llm_provider": "custom", "llm_base_url": gw},
            env_vars=env_vars,
        )
        env = env_dict(lines)
        ok &= check(f"e ({label}): exits 0", rc == 0, f"rc={rc} out={out!r}")
        ok &= check(
            f"e ({label}): no custom provider in env",
            env.get("HINDSIGHT_API_LLM_PROVIDER") == "openai" and len(provider_lines(lines)) == 1,
            f"provider_lines={provider_lines(lines)}",
        )
        ok &= check(
            f"e ({label}): override warning logged",
            "HINDSIGHT_API_LLM_PROVIDER" in out and "ignored" in out,
            f"out={out!r}",
        )
        ok &= check(
            f"e ({label}): warning not written into env file",
            not any("WARNING" in l or "ignored" in l for l in lines),
            f"lines={lines}",
        )

    # (f) expert + openai without key -> still blocked.
    rc, lines, out = run_continit({"mode": "expert", "llm_provider": "openai"})
    ok &= check("f: expert openai without key exits nok", rc == 17, f"rc={rc}")
    ok &= check("f: error mentions llm_api_key", "llm_api_key" in out, f"out={out!r}")

    # (g) simple + openai without key -> keyless local stack (no regression).
    rc, lines, out = run_continit({"mode": "simple", "llm_provider": "openai"})
    env = env_dict(lines)
    ok &= check("g: simple+openai without key exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "g: provider forced to llamacpp",
        env.get("HINDSIGHT_API_LLM_PROVIDER") == "llamacpp",
        f"env={env}",
    )

    # --- Dedicated consolidation-LLM route (1.2.26) -------------------------
    cprovider = "openai"
    cmodel = "gpt-4o-mini"
    cbase = "http://gw:20128/api/v1"
    ckey = "consolidation-only-secret"

    # (h) expert + all four set -> exact consolidation mapping, main LLM intact.
    rc, lines, out = run_continit(
        {
            "mode": "expert",
            "llm_provider": "llamacpp",
            "llm_model": "gemma-4-e2b-it",
            "consolidation_llm_provider": cprovider,
            "consolidation_llm_model": cmodel,
            "consolidation_llm_base_url": cbase,
            "consolidation_llm_api_key": ckey,
        }
    )
    env = env_dict(lines)
    ok &= check("h: expert consolidation exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "h: all four consolidation vars emitted",
        len(consolidation_lines(lines)) == 4,
        f"lines={consolidation_lines(lines)}",
    )
    ok &= check(
        "h: provider mapped to HINDSIGHT_API_CONSOLIDATION_LLM_PROVIDER",
        env.get("HINDSIGHT_API_CONSOLIDATION_LLM_PROVIDER") == cprovider,
        f"env={env}",
    )
    ok &= check(
        "h: model mapped to HINDSIGHT_API_CONSOLIDATION_LLM_MODEL",
        env.get("HINDSIGHT_API_CONSOLIDATION_LLM_MODEL") == cmodel,
        f"env={env}",
    )
    ok &= check(
        "h: base URL mapped to HINDSIGHT_API_CONSOLIDATION_LLM_BASE_URL",
        env.get("HINDSIGHT_API_CONSOLIDATION_LLM_BASE_URL") == cbase,
        f"env={env}",
    )
    ok &= check(
        "h: key mapped verbatim to HINDSIGHT_API_CONSOLIDATION_LLM_API_KEY",
        env.get("HINDSIGHT_API_CONSOLIDATION_LLM_API_KEY") == ckey,
        f"env={env}",
    )
    ok &= check(
        "h: main LLM config untouched",
        env.get("HINDSIGHT_API_LLM_PROVIDER") == "llamacpp"
        and env.get("HINDSIGHT_API_LLM_MODEL") == "gemma-4-e2b-it"
        and "HINDSIGHT_API_LLM_API_KEY" not in env
        and "HINDSIGHT_API_LLM_BASE_URL" not in env,
        f"env={env}",
    )

    # (i) partial override -> only the set var is emitted; upstream falls back
    # to the main LLM setting for the rest.
    rc, lines, out = run_continit(
        {"mode": "expert", "llm_provider": "llamacpp", "consolidation_llm_model": cmodel}
    )
    env = env_dict(lines)
    ok &= check("i: partial consolidation exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "i: only the model override is emitted",
        consolidation_lines(lines) == [f"HINDSIGHT_API_CONSOLIDATION_LLM_MODEL={cmodel}"],
        f"lines={consolidation_lines(lines)}",
    )

    # (j) absent -> no consolidation line at all (current behaviour preserved).
    rc, lines, out = run_continit({"mode": "expert", "llm_provider": "llamacpp"})
    ok &= check("j: absent consolidation exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "j: no consolidation vars when unset",
        not consolidation_lines(lines),
        f"lines={consolidation_lines(lines)}",
    )

    # (k) simple mode ignores stored consolidation options entirely.
    rc, lines, out = run_continit(
        {
            "mode": "simple",
            "consolidation_llm_provider": cprovider,
            "consolidation_llm_model": cmodel,
            "consolidation_llm_base_url": cbase,
            "consolidation_llm_api_key": ckey,
        }
    )
    env = env_dict(lines)
    ok &= check("k: simple consolidation exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "k: simple mode emits no consolidation vars",
        not consolidation_lines(lines),
        f"lines={consolidation_lines(lines)}",
    )
    ok &= check(
        "k: simple mode still forces llamacpp",
        env.get("HINDSIGHT_API_LLM_PROVIDER") == "llamacpp",
        f"env={env}",
    )

    # --- consolidation_max_completion_tokens (1.2.28) -----------------------
    maxtok = "HINDSIGHT_API_CONSOLIDATION_MAX_COMPLETION_TOKENS"

    # (l) consolidation LLM configured, no explicit token cap -> default 8192.
    rc, lines, out = run_continit(
        {"mode": "expert", "llm_provider": "llamacpp", "consolidation_llm_model": cmodel}
    )
    env = env_dict(lines)
    ok &= check("l: consolidation token default exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "l: max completion tokens defaults to 8192",
        env.get(maxtok) == "8192",
        f"env={env}",
    )

    # (m) explicit consolidation_max_completion_tokens -> passed through verbatim.
    rc, lines, out = run_continit(
        {
            "mode": "expert",
            "llm_provider": "llamacpp",
            "consolidation_llm_model": cmodel,
            "consolidation_max_completion_tokens": "4096",
        }
    )
    env = env_dict(lines)
    ok &= check("m: explicit token cap exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "m: explicit max completion tokens honoured",
        env.get(maxtok) == "4096",
        f"env={env}",
    )

    # (n) no consolidation LLM configured -> token var not emitted at all.
    rc, lines, out = run_continit(
        {
            "mode": "expert",
            "llm_provider": "llamacpp",
            "consolidation_max_completion_tokens": "4096",
        }
    )
    env = env_dict(lines)
    ok &= check("n: no consolidation LLM exits 0", rc == 0, f"rc={rc} out={out!r}")
    ok &= check(
        "n: max completion tokens not emitted without consolidation LLM",
        maxtok not in env,
        f"env={env}",
    )

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
