# 🐛 Real Multi-Agent AI Bug Fixer

An AI-driven code debugging tool built with **Streamlit**, **LangGraph**, and the **Groq API**. Unlike a simple prompt-and-respond tool, this system uses a real multi-agent architecture: an LLM supervisor dynamically decides which specialized agent should act next, and fixes are verified by **actually compiling and executing the code** in a resource-limited sandbox — not just an LLM's guess that it works.

🔗 **Live Demo:** https://agenticai-bugfixer.streamlit.app/

---

## 🤖 How It Works

This isn't a fixed pipeline that always runs the same steps in the same order. A **supervisor node** (itself an LLM call) looks at the current state after every step and decides what happens next — including looping back to the debugger if execution proves a fix didn't actually work.

| Node | Role |
|------|------|
| 🧭 **Supervisor** | Decides which agent runs next, based on the current state — real dynamic routing, not a hardcoded sequence |
| 🔍 **Analyzer** | Detects syntax, logical, and runtime bugs |
| 🛠️ **Debugger** | Generates a corrected version of the code |
| 🧪 **Executor** | Actually compiles/runs the fixed code in a sandbox and captures real stdout/stderr — this is the ground truth the reviewer uses |
| 🔎 **Reviewer** | Approves or rejects the fix based on the real execution result, not just re-reading the code |
| 📖 **Explainer** | Breaks down the bugs and fix in beginner-friendly terms |
| ⚡ **Optimizer** | Suggests performance, readability, and style improvements |

If the reviewer rejects a fix, the supervisor routes back to the debugger (up to a configurable number of rounds) with the real error output included — so each retry is grounded in what actually happened, not another blind guess.

---

## 🚀 Features

- 🧠 LLM-driven supervisor routing via **LangGraph** — the control flow is decided at runtime, not hardcoded
- 🧪 Real code execution as a tool, not just LLM self-assessment — fixes are verified by actually running them
- 🔒 Sandboxed execution: CPU time, memory, file size, and process limits per run, plus a pre-execution check that blocks dangerous system/file/network calls
- ⏱️ Per-session rate limiting to protect the shared API key on the public demo
- ⚡ Ultra-fast inference via the Groq API, using **Llama 3.3 70B**
- 📊 Tab-based UI showing bugs, the fix, real execution output, review verdict, explanation, and the supervisor's routing trace
- 🌐 Multi-language support with real compilers/interpreters, not just static analysis

---

## 🌐 Supported Languages

Execution is real (actually compiled/run), not simulated, for:

- Python
- JavaScript
- TypeScript
- Java
- C++

---

## 🛠️ Run Locally

### 1️⃣ Clone the repository
```bash
git clone https://github.com/sreeayshwarya07/agentic_ai_bug_fixer.git
cd agentic_ai_bug_fixer
```

### 2️⃣ Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Install language runtimes (for real multi-language execution)
```bash
sudo apt-get install -y g++ default-jdk-headless nodejs npm
npm install -g typescript
```
(These are listed in `packages.txt` for automatic install on Streamlit Community Cloud.)

### 4️⃣ Add your Groq API key
Create `.streamlit/secrets.toml`:
```toml
Bug = "gsk_your_key_here"
```

### 5️⃣ Run the app
```bash
streamlit run app_bug.py
```

## 🧠 Tech Stack

- **Orchestration:** LangGraph (`StateGraph` with conditional routing)
- **LLM:** Groq API — Llama 3.3 70B
- **Frontend/UI:** Streamlit
- **Execution sandbox:** Python `subprocess` + `resource` (rlimits) for CPU/memory/process caps, plus a static pre-execution safety check
- **Backend:** Python

---

## ⚠️ Known Limitations

Being upfront about this rather than overselling it:

- Sandboxing uses OS-level resource limits (CPU time, memory, process count), not full container/VM isolation — it stops runaway loops, memory bombs, and common dangerous calls, but is not a substitute for something like Docker/gVisor-based isolation in a production system.
- TypeScript execution compiles via `npx tsc` at runtime, so the first run after a deploy is slower while the compiler installs.
- The public demo has a per-session rate limit to protect the shared API key.
## 📁 Project Structure
```
agentic_ai_bug_fixer/
│
├── app_bug.py           # Main Streamlit app: LangGraph graph, sandboxed executor, and UI
├── requirements.txt     # Python dependencies
├── packages.txt         # System-level dependencies for Streamlit Community Cloud (g++, JDK, Node)
└── README.md            # Documentation
```
