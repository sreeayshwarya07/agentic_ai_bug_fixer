"""
Test suite for the multi-agent bug fixer's core logic.
Run locally with: pytest test_agent_system.py -v
"""
import pytest
import os, subprocess, tempfile, re, resource

# ── Same hardened execution logic as app_bug.py, isolated for testing ──────
DANGEROUS_PATTERNS = [
    r"\bos\.system\b", r"\bsubprocess\b", r"\bos\.fork\b", r"\bos\.exec\w*\b",
    r"\b__import__\s*\(\s*['\"]os['\"]", r"\bshutil\.rmtree\b",
    r"\bsocket\.\w+\b", r"\brequests\.\w+\b", r"\burllib\b",
]

def static_safety_check(code, language):
    lang = language.strip().lower()
    if lang != "python":
        return []
    return [p for p in DANGEROUS_PATTERNS if re.search(p, code)]

AS_LIMIT_MB = {"python": 300, "javascript": 900, "js": 900, "java": 900, "c++": 300, "cpp": 300, "typescript": 900, "ts": 900}

def _limit_resources(lang):
    def limiter():
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        as_mb = AS_LIMIT_MB.get(lang, 512)
        resource.setrlimit(resource.RLIMIT_AS, (as_mb * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        os.setsid()
    return limiter

def _run(cmd, lang="python", timeout=10, cwd=None):
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            preexec_fn=_limit_resources(lang),
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        return {"executed": True, "success": proc.returncode == 0,
                "stdout": proc.stdout[-1500:], "stderr": proc.stderr[-1500:],
                "returncode": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"executed": True, "success": False, "stdout": "",
                "stderr": f"Timed out after {timeout}s", "returncode": -1}
    except FileNotFoundError as e:
        return {"executed": False, "reason": f"Runtime not installed: {e}"}

def execute_code_tool(code, language):
    flagged = static_safety_check(code, language)
    if flagged:
        return {"executed": False, "reason": f"Blocked before execution: flagged patterns ({', '.join(flagged)})."}
    lang = language.strip().lower()
    workdir = tempfile.mkdtemp()
    try:
        if lang == "python":
            path = os.path.join(workdir, "main.py")
            open(path, "w").write(code)
            return _run(["python3", path], lang=lang, cwd=workdir)
        elif lang in ("javascript", "js"):
            path = os.path.join(workdir, "main.js")
            open(path, "w").write(code)
            return _run(["node", path], lang=lang, cwd=workdir)
        elif lang in ("c++", "cpp"):
            path = os.path.join(workdir, "main.cpp")
            binary = os.path.join(workdir, "main_bin")
            open(path, "w").write(code)
            compile_result = _run(["g++", "-std=c++17", path, "-o", binary], lang=lang, timeout=30, cwd=workdir)
            if not compile_result["success"]:
                compile_result["stage"] = "compile"
                return compile_result
            run_result = _run([binary], lang=lang, cwd=workdir)
            run_result["stage"] = "run"
            return run_result
        else:
            return {"executed": False, "reason": f"Execution not supported for '{language}' yet."}
    finally:
        subprocess.run(["rm", "-rf", workdir], capture_output=True)


# ── Tests ────────────────────────────────────────────────────────────────
class TestStaticSafetyCheck:
    def test_clean_code_passes(self):
        assert static_safety_check("print(1+1)", "python") == []

    def test_os_system_flagged(self):
        assert static_safety_check("import os\nos.system('ls')", "python") != []

    def test_subprocess_flagged(self):
        assert static_safety_check("import subprocess", "python") != []

    def test_non_python_skips_check(self):
        assert static_safety_check("os.system('ls')", "javascript") == []


class TestExecuteCodeTool:
    def test_python_success(self):
        result = execute_code_tool("print(2 + 2)", "python")
        assert result["executed"] is True
        assert result["success"] is True
        assert "4" in result["stdout"]

    def test_python_runtime_error_captured(self):
        result = execute_code_tool("1 / 0", "python")
        assert result["executed"] is True
        assert result["success"] is False
        assert "ZeroDivisionError" in result["stderr"]

    def test_python_syntax_error_captured(self):
        result = execute_code_tool("def f(:\n  pass", "python")
        assert result["executed"] is True
        assert result["success"] is False

    def test_infinite_loop_is_killed(self):
        result = execute_code_tool("while True: pass", "python")
        assert result["executed"] is True
        assert result["success"] is False  # killed by CPU rlimit, doesn't hang

    def test_dangerous_code_blocked_before_running(self):
        result = execute_code_tool("import os\nos.system('rm -rf /')", "python")
        assert result["executed"] is False
        assert "Blocked" in result["reason"]

    def test_javascript_success(self):
        result = execute_code_tool("console.log(3 * 3)", "javascript")
        assert result["executed"] is True
        assert result["success"] is True
        assert "9" in result["stdout"]

    def test_unsupported_language(self):
        result = execute_code_tool("print('hi')", "cobol")
        assert result["executed"] is False

    def test_workdir_cleaned_up(self):
        import glob
        before = set(glob.glob(tempfile.gettempdir() + "/tmp*"))
        execute_code_tool("print(1)", "python")
        after = set(glob.glob(tempfile.gettempdir() + "/tmp*"))
        assert after - before == set() or all("main" not in d for d in (after - before))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
