# 🐛 Multi-Agent AI Bug Fixer

A powerful **AI-driven code debugging tool** built with Streamlit and Groq API.  
It uses a **multi-agent system** where four specialized AI agents collaborate to analyze, fix, explain, and optimize your code instantly.

🔗 **Live Demo:**  
https://agenticai-bugfixer.streamlit.app/

---

## 🤖 How It Works

Your code is processed through **four intelligent AI agents** sequentially:

| Agent | Role |
|------|------|
| 🔍 **Analyzer** | Detects syntax, logical, and runtime errors |
| 🛠️ **Debugger** | Generates fully corrected code |
| 📖 **Explainer** | Breaks down bugs in beginner-friendly terms |
| ⚡ **Optimizer** | Suggests improvements for cleaner & faster code |

---

## 🚀 Features

- ✏️ Paste code or upload files directly  
- 🌐 Supports **13+ programming languages**  
- ⚡ Ultra-fast inference using Groq API  
- 🧠 Powered by **LLaMA 3.3 70B model**  
- 📊 Clean tab-based UI for results  
- 🧩 Beginner-friendly explanations  

---

## 🌐 Supported Languages

- Python  
- JavaScript  
- Java  
- C++  
- C  
- TypeScript  
- PHP  
- Go  
- Rust  
- Swift  
- Kotlin  
- R  
- SQL  

---

## 🛠️ Run Locally

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/ai-bug-fixer.git
cd ai-bug-fixer
```

### 2️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Add Your Groq API Key

Create the file:

```
.streamlit/secrets.toml
```

Add your API key:

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

### 4️⃣ Run the App
```bash
streamlit run app_bug.py
```

---

## 📁 Project Structure

```
ai-bug-fixer/
│
├── app_bug.py              # Main Streamlit application
├── requirements.txt        # Project dependencies
├── README.md               # Documentation
```

---

## 🧠 Tech Stack

- **Frontend/UI:** Streamlit  
- **Backend:** Python  
- **AI Engine:** Groq API  
- **Model:** LLaMA 3.3 70B  
