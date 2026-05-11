app_code = '''
import streamlit as st
import requests

st.set_page_config(page_title="🐛 Multi-Agent AI Bug Fixer", layout="wide")
st.title("🐛 Multi-Agent AI Bug Fixer")
st.caption("Powered by Groq · Four AI agents analyze, fix, explain, and optimize your code.")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        api_key = st.text_input("🔑 Groq API Key", type="password", placeholder="gsk_...")
    st.caption("Get your free key at [console.groq.com](https://console.groq.com)")
    language = st.selectbox("🌐 Language", [
        "Python", "JavaScript", "Java", "C++", "C",
        "TypeScript", "PHP", "Go", "Rust", "Swift", "Kotlin", "R", "SQL"
    ])

st.subheader("📂 Input Your Code")
input_method = st.radio("Input method", ["📋 Paste Code", "📁 Upload File"], horizontal=True)

code = ""
if input_method == "📋 Paste Code":
    code = st.text_area("Paste your buggy code here...", height=250)
else:
    uploaded_file = st.file_uploader("Upload your code file",
        type=["py","js","java","cpp","c","ts","php","go","rs","swift","kt","r","sql","txt"])
    if uploaded_file:
        code = uploaded_file.read().decode("utf-8")
        st.success(f"📄 Loaded: {uploaded_file.name}")
        st.code(code, language=language.lower())

def call_groq(api_key, system_prompt, user_prompt):
    response = requests.post(
        "https://api.groqcom/openai/v1/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ]
        }
    )
    if not response.ok:
        err = response.json()
        raise Exception(err.get("error", {}).get("message", f"Groq API error {response.status_code}"))
    return response.json()["choices"][0]["message"]["content"]

run = st.button("🤖 Run All 4 Agents", type="primary", disabled=not (api_key and code.strip()))

if run:
    results = {}
    progress = st.progress(0)
    col1, col2, col3, col4 = st.columns(4)

    try:
        with col1:
            with st.status("🔍 Analyzing...", expanded=False) as s:
                results["bugs"] = call_groq(api_key,
                    f"You are an expert {language} bug analyzer. Detect all bugs. Be specific and concise. Number each bug.",
                    f"Analyze this {language} code and list ALL bugs (syntax, logical, runtime):\\n\\n```{language}\\n{code}\\n```")
                s.update(label="🔍 Analyzer ✅", state="complete")
        progress.progress(28)

        with col2:
            with st.status("🛠️ Fixing...", expanded=False) as s:
                results["fix"] = call_groq(api_key,
                    f"You are an expert {language} debugger. Return ONLY the complete corrected code inside a code block. No extra text.",
                    f"Fix this buggy {language} code.\\n\\nBugs:\\n{results[\'bugs\']}\\n\\nOriginal:\\n```{language}\\n{code}\\n```")
                s.update(label="🛠️ Debugger ✅", state="complete")
        progress.progress(55)

        with col3:
            with st.status("📖 Explaining...", expanded=False) as s:
                results["explain"] = call_groq(api_key,
                    f"You are a friendly {language} teacher. Explain bugs and fixes in simple beginner-friendly language.",
                    f"Explain these bugs and fixes.\\n\\nCode:\\n{code}\\n\\nBugs:\\n{results[\'bugs\']}\\n\\nFix:\\n{results[\'fix\']}")
                s.update(label="📖 Explainer ✅", state="complete")
        progress.progress(78)

        with col4:
            with st.status("⚡ Optimizing...", expanded=False) as s:
                results["optimize"] = call_groq(api_key,
                    f"You are an expert {language} optimizer. Suggest improvements. Number each suggestion.",
                    f"Suggest optimizations for this {language} code:\\n\\n```{language}\\n{code}\\n```")
                s.update(label="⚡ Optimizer ✅", state="complete")
        progress.progress(100)

        st.subheader("📊 Results")
        tab1, tab2, tab3, tab4 = st.tabs(["🐛 Bugs Found", "✅ Fixed Code", "📖 Explanation", "⚡ Optimizations"])
        with tab1:
            st.markdown(results["bugs"])
        with tab2:
            st.markdown(results["fix"])
        with tab3:
            st.markdown(results["explain"])
        with tab4:
            st.markdown(results["optimize"])

    except Exception as e:
        st.error(f"⚠️ Error: {e}")
        progress.progress(0)
'''

with open("app_bug.py", "w") as f:
    f.write(app_code)

print("✅ app_bug.py saved!")
