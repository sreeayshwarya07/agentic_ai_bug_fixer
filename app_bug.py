import streamlit as st
import os, json, subprocess, tempfile, textwrap, re, resource, time
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

API_KEY = st.secrets.get("Bug", os.environ.get("Bug", ""))
if not API_KEY:
    st.error("⚠️ API key not found. Add `Bug = \"your_groq_key\"` in Streamlit Cloud → Settings → Secrets.")
    st.stop()

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=API_KEY, temperature=0.2, max_tokens=1500)
llm_json = llm.bind(response_format={"type": "json_object"})  # real structured output, not prompt-and-hope

class BugFixState(TypedDict):
    code: str
    language: str
    bugs: List[dict]
    severity: str
    fixed_code: str
    changes: List[dict]
    execution_result: dict
    review: dict
    explanation: str
    optimizations: dict
    round_num: int
    max_rounds: int
    history: List[str]
    next_step: str

# ── Hardened sandbox: resource limits + pre-execution danger checks ────────
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
                "stderr": f"Timed out after {timeout}s (resource limits enforced)", "returncode": -1}
    except FileNotFoundError as e:
        return {"executed": False, "reason": f"Runtime not installed: {e}"}

def execute_code_tool(code, language):
    flagged = static_safety_check(code, language)
    if flagged:
        return {"executed": False,
                "reason": f"Blocked before execution: flagged patterns ({', '.join(flagged)}). "
                          f"Only pure computation is permitted, not system/network/file access."}
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
        elif lang in ("typescript", "ts"):
            path = os.path.join(workdir, "main.ts")
            open(path, "w").write(code)
            compile_result = _run(["npx", "--yes", "tsc", "--target", "es2019", path], lang=lang, timeout=30, cwd=workdir)
            if not compile_result["success"]:
                compile_result["stage"] = "compile"
                return compile_result
            run_result = _run(["node", path.replace(".ts", ".js")], lang=lang, cwd=workdir)
            run_result["stage"] = "run"
            return run_result
        elif lang == "java":
            match = re.search(r"public\s+class\s+(\w+)", code)
            class_name = match.group(1) if match else "Main"
            path = os.path.join(workdir, f"{class_name}.java")
            open(path, "w").write(code)
            compile_result = _run(["javac", path], lang=lang, timeout=30, cwd=workdir)
            if not compile_result["success"]:
                compile_result["stage"] = "compile"
                return compile_result
            run_result = _run(["java", "-cp", workdir, class_name], lang=lang, cwd=workdir)
            run_result["stage"] = "run"
            return run_result
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

# ── LLM calls: real JSON mode instead of prompt-and-parse ──────────────────
def _ask_json(system, user):
    resp = llm_json.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    try:
        return json.loads(resp.content)
    except json.JSONDecodeError:
        return {"raw": resp.content}

def analyzer_node(state):
    system = textwrap.dedent(f"""
        You are a senior {state['language']} code reviewer. Respond only in JSON.
        Identify ALL bugs (syntax, logic, runtime, edge-cases).
        JSON shape: {{"bug_count": <int>, "severity": "low|medium|high|critical",
          "bugs": [{{"id": 1, "type": "<type>", "description": "<desc>"}}]}}
    """)
    result = _ask_json(system, f"Analyze this {state['language']} code:\n```{state['language']}\n{state['code']}\n```")
    return {"bugs": result.get("bugs", []), "severity": result.get("severity", "unknown"),
            "history": state["history"] + [f"analyzer: found {len(result.get('bugs', []))} bug(s)"]}

def debugger_node(state):
    system = textwrap.dedent(f"""
        You are an expert {state['language']} debugger. Respond only in JSON.
        Fix ALL reported bugs.
        JSON shape: {{"fixed_code": "<complete corrected code>",
          "changes": [{{"bug_id": 1, "fix_summary": "<what changed>"}}]}}
    """)
    extra = ""
    if state.get("execution_result", {}).get("executed") and not state["execution_result"].get("success", True):
        extra = f"\n\nThe previous fix FAILED when actually executed:\nstderr:\n{state['execution_result'].get('stderr','')}"
    if state.get("review", {}).get("remaining_issues"):
        extra += f"\n\nReviewer flagged remaining issues: {state['review']['remaining_issues']}"
    result = _ask_json(system,
        f"Bug report:\n{json.dumps(state['bugs'], indent=2)}\n\n"
        f"Original code:\n```{state['language']}\n{state['code']}\n```{extra}")
    return {"fixed_code": result.get("fixed_code", state["code"]), "changes": result.get("changes", []),
            "round_num": state["round_num"] + 1,
            "history": state["history"] + [f"debugger: round {state['round_num'] + 1} fix proposed"]}

def executor_node(state):
    result = execute_code_tool(state["fixed_code"], state["language"])
    tag = "ran clean" if result.get("success") else "raised an error" if result.get("executed") else "blocked/not executed"
    return {"execution_result": result, "history": state["history"] + [f"executor: fixed code {tag}"]}

def reviewer_node(state):
    system = textwrap.dedent(f"""
        You are a strict {state['language']} code reviewer. Respond only in JSON.
        You are given the original bugs AND the REAL output of actually running the fixed code.
        Trust the execution evidence over your own guesses.
        JSON shape: {{"approved": true|false, "remaining_issues": ["<issue>"], "confidence_score": <0-100>}}
    """)
    result = _ask_json(system,
        f"Known bugs:\n{json.dumps(state['bugs'], indent=2)}\n\n"
        f"Fixed code:\n```{state['language']}\n{state['fixed_code']}\n```\n\n"
        f"Real execution result:\n{json.dumps(state['execution_result'], indent=2)}\n\nApprove this fix?")
    return {"review": result, "history": state["history"] + [f"reviewer: approved={result.get('approved')}"]}

def explainer_node(state):
    system = f"You are a friendly {state['language']} teacher. Explain bugs and fixes simply with analogies. Be encouraging."
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=
        f"Original code:\n{state['code']}\n\nBugs:\n{json.dumps(state['bugs'], indent=2)}\n\n"
        f"Fix changes:\n{json.dumps(state['changes'], indent=2)}\n\nExplain to a beginner.")])
    return {"explanation": resp.content, "history": state["history"] + ["explainer: wrote explanation"]}

def optimizer_node(state):
    system = textwrap.dedent(f"""
        You are an expert {state['language']} performance and style optimizer. Respond only in JSON.
        JSON shape: {{"suggestions": [{{"id": 1, "category": "performance|readability|security|style",
          "description": "<suggestion>", "priority": "low|medium|high"}}],
          "optimized_code": "<full optimized code>"}}
    """)
    result = _ask_json(system, f"Optimize this {state['language']} code:\n```{state['language']}\n{state['fixed_code']}\n```")
    return {"optimizations": result, "history": state["history"] + ["optimizer: suggestions ready"]}

VALID_NEXT = ["analyzer", "debugger", "executor", "reviewer", "explainer", "optimizer", "end"]

def supervisor_node(state):
    system = textwrap.dedent(f"""
        You are the supervisor of a bug-fixing multi-agent system. Respond only in JSON.
        Given the current state, decide which agent should act next. Choose exactly one:
        - "analyzer": no bug report yet
        - "debugger": bugs exist but no fixed_code yet, OR the last review was not approved
          and round_num < max_rounds
        - "executor": fixed_code exists but hasn't been executed for this round yet
        - "reviewer": fixed_code has been executed but not yet reviewed this round
        - "explainer": review is approved (or rounds exhausted) and no explanation yet
        - "optimizer": explanation exists but no optimizations yet
        - "end": optimizations exist — everything is done
        JSON shape: {{"next": "<one of the choices above>", "reason": "<short reason>"}}
    """)
    summary = {
        "has_bugs": bool(state["bugs"]), "has_fixed_code": bool(state["fixed_code"]),
        "execution_done_this_round": bool(state["execution_result"]),
        "has_review": bool(state["review"]), "review_approved": state["review"].get("approved", False),
        "round_num": state["round_num"], "max_rounds": state["max_rounds"],
        "has_explanation": bool(state["explanation"]), "has_optimizations": bool(state["optimizations"]),
        "history": state["history"][-6:],
    }
    result = _ask_json(system, f"Current state:\n{json.dumps(summary, indent=2)}\n\nWhat's next?")
    nxt = result.get("next", "").strip().lower()
    if nxt not in VALID_NEXT:
        nxt = "end"
    return {"next_step": nxt, "history": state["history"] + [f"supervisor: routed to {nxt} ({result.get('reason','')})"]}

def route(state):
    return state["next_step"]

builder = StateGraph(BugFixState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("analyzer", analyzer_node)
builder.add_node("debugger", debugger_node)
builder.add_node("executor", executor_node)
builder.add_node("reviewer", reviewer_node)
builder.add_node("explainer", explainer_node)
builder.add_node("optimizer", optimizer_node)
builder.add_edge(START, "supervisor")
for agent in ["analyzer", "debugger", "executor", "reviewer", "explainer", "optimizer"]:
    builder.add_edge(agent, "supervisor")
builder.add_conditional_edges("supervisor", route, {
    "analyzer": "analyzer", "debugger": "debugger", "executor": "executor",
    "reviewer": "reviewer", "explainer": "explainer", "optimizer": "optimizer", "end": END,
})
graph = builder.compile()

def run_bug_fixer(code, language="Python", max_rounds=2):
    initial_state = {
        "code": code, "language": language, "bugs": [], "severity": "", "fixed_code": "",
        "changes": [], "execution_result": {}, "review": {}, "explanation": "", "optimizations": {},
        "round_num": 0, "max_rounds": max_rounds, "history": [], "next_step": "",
    }
    return graph.invoke(initial_state, config={"recursion_limit": 40})

# ── Streamlit UI ──────────────────────────────────────────────────────────
st.set_page_config(page_title="Real Multi-Agent Bug Fixer", page_icon="🤖", layout="wide")
st.title("🤖 Real Multi-Agent Bug Fixer")
st.caption("LangGraph · LLM supervisor routing · sandboxed execution across Python, JS, TS, Java, C++")

# Simple per-session rate limit — protects the shared API key from abuse on a public link
if "run_timestamps" not in st.session_state:
    st.session_state.run_timestamps = []
RATE_LIMIT_RUNS = 5
RATE_LIMIT_WINDOW_SEC = 300

with st.sidebar:
    st.header("⚙️ Settings")
    language = st.selectbox("Language", ["Python", "JavaScript", "TypeScript", "Java", "C++"])
    max_rounds = st.slider("Max debug rounds", 1, 3, 2)
    st.caption(f"Limit: {RATE_LIMIT_RUNS} runs / {RATE_LIMIT_WINDOW_SEC//60} min per session")

code_input = st.text_area("Paste your buggy code here", height=220, placeholder="def my_func():\n    pass")

if st.button("🚀 Run Agent System", type="primary", use_container_width=True):
    now = time.time()
    st.session_state.run_timestamps = [t for t in st.session_state.run_timestamps if now - t < RATE_LIMIT_WINDOW_SEC]

    if not code_input.strip():
        st.warning("Please paste some code first.")
    elif len(st.session_state.run_timestamps) >= RATE_LIMIT_RUNS:
        wait = int(RATE_LIMIT_WINDOW_SEC - (now - st.session_state.run_timestamps[0]))
        st.warning(f"Rate limit reached. Try again in {wait}s.")
    else:
        st.session_state.run_timestamps.append(now)
        with st.spinner("Supervisor is routing agents..."):
            try:
                results = run_bug_fixer(code_input, language=language, max_rounds=max_rounds)
            except Exception as e:
                st.error(f"Agent pipeline failed: {e}")
                st.stop()

        st.success("✅ Done!")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            ["🐛 Bugs", "✅ Fix", "🧪 Execution", "🔎 Review", "📖 Explanation", "🗺️ Routing Trace"])

        with tab1:
            st.metric("Bugs found", len(results.get("bugs", [])))
            st.metric("Severity", results.get("severity", "?"))
            for bug in results.get("bugs", []):
                with st.expander(f"Bug #{bug.get('id')} — {bug.get('type','').upper()}"):
                    st.write(bug.get("description", ""))

        with tab2:
            st.code(results.get("fixed_code", ""), language=language.lower())
            for ch in results.get("changes", []):
                st.markdown(f"- **Bug #{ch.get('bug_id')}**: {ch.get('fix_summary','')}")

        with tab3:
            ex = results.get("execution_result", {})
            if ex.get("executed"):
                if ex.get("stage"):
                    st.caption(f"Stage: {ex['stage']}")
                st.metric("Ran successfully", "✅ Yes" if ex.get("success") else "❌ No")
                if ex.get("stdout"):
                    st.text("stdout:")
                    st.code(ex["stdout"])
                if ex.get("stderr"):
                    st.text("stderr:")
                    st.code(ex["stderr"])
            else:
                st.info(ex.get("reason", "Not executed."))

        with tab4:
            review = results.get("review", {})
            st.metric("Verdict", "✅ Approved" if review.get("approved") else "⚠️ Not approved")
            st.metric("Confidence", f"{review.get('confidence_score', 0)}%")
            for issue in review.get("remaining_issues", []):
                st.markdown(f"- {issue}")

        with tab5:
            st.markdown(results.get("explanation", ""))
            opts = results.get("optimizations", {})
            if opts.get("suggestions"):
                st.subheader("Optimizer suggestions")
                for s in opts["suggestions"]:
                    st.markdown(f"**[{s.get('priority','').upper()}] {s.get('category','')}** — {s.get('description','')}")
            if opts.get("optimized_code"):
                st.subheader("Optimized code")
                st.code(opts["optimized_code"], language=language.lower())

        with tab6:
            st.caption("This is the supervisor's real, per-run decision trail — not a fixed script.")
            for step in results.get("history", []):
                st.text(step)
