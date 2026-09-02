# 📞 Maya — Nepanglish AI Phone Order Taker

A **local AI voice agent that answers a restaurant's phone**, takes food orders in
**"Nepanglish"** (Nepali + English), and replies in a **human voice** — including
**cloning your own voice** with OmniVoice.

Built from open-source components. Works fully offline (with a local LLM + local
voice), or with DeepSeek for the best conversation quality.

---

## ✨ Features

- **Phone-order-taker personality** — menu-centric, concise, non-irritating questions.
- **Human Nepali voice** — [OmniVoice](https://github.com/k2-fsa/OmniVoice) (600+ languages, incl. Nepali) running on GPU, with **zero-shot voice cloning**.
- **Real order tracking** — adds, quantity changes, removals, and landmark addresses ("पछाडि / अगाडि / नजिकै") all tracked exactly across the call.
- **Barge-in / interruption** — interrupt Maya by talking, like a real call.
- **Streaming + low time-to-first-audio** — she starts speaking before the full reply finishes.
- **Cash on Delivery only**, landmark-based delivery addresses.
- **Dashboard** — menu CRUD, live orders, call logs.

## 🏗️ Architecture

| Stage | Technology | Where |
|-------|-----------|-------|
| Voice Activity Detection | Silero VAD (inside faster-whisper) | local |
| Speech → Text | faster-whisper (`small`) | local |
| Language model | DeepSeek (cloud, optional) **or** Qwen2.5 7B via Ollama (local) | your choice |
| Menu grounding | SQLite menu injected into the prompt (RAG) | local |
| Voice | **OmniVoice** (GPU) · edge-tts · Piper | local/cloud |
| UI | Next.js 16 + Tailwind | local |

```
mic → Silero VAD → Whisper ASR → LLM (DeepSeek/Ollama) → TTS (OmniVoice) → speaker
```

## 📁 Layout

```
maya-agent/
├── backend/main.py       # FastAPI: turn/stream, menu, orders, voice clone, settings
├── maya/                 # AI core (asr, llm, tts, agent, prompts, db, config)
├── frontend/             # Next.js app (Talk / Menu / Orders / Settings)
├── docs/                 # project plan + research PDFs
├── data/                 # SQLite + downloaded models (created at first run)
├── .env.example          # template for your DeepSeek key (optional)
└── requirements.txt
```

---

## 🚀 Setup (Windows, NVIDIA GPU)

### 1. Prerequisites
- **Python 3.12–3.14**
- **Node.js 20+**
- **Ollama** (optional — only for the local LLM): https://ollama.com
- **NVIDIA GPU** (for the human OmniVoice; without it, use edge-tts/Piper voice instead)

### 2. Clone & create environment

```bash
git clone https://github.com/sushant-me/AI-phone.git
cd AI-phone

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. (Optional) DeepSeek key for the best conversation

```bash
copy .env.example .env
# then edit .env and paste your DeepSeek key (get one at platform.deepseek.com)
```

If you skip this, Maya automatically uses the **local Ollama LLM** — just run
`ollama pull qwen2.5:7b` first.

### 4. Install the human voice (OmniVoice, GPU)

```bash
# CUDA-enabled PyTorch (matches OmniVoice)
pip install torch==2.11.0+cu128 torchaudio==2.11.0+cu128 torchvision==0.26.0+cu128 --extra-index-url https://download.pytorch.org/whl/cu128

# OmniVoice + the transformers version that has its tokenizer
pip install omnivoice
pip install "transformers==5.8.1"
```

> On first use it downloads the OmniVoice model (~2.5 GB) + audio tokenizer (~0.8 GB)
> from HuggingFace. On first switch to OmniVoice the backend loads it (~40 s), then it's
> fast.

> **No GPU?** Skip step 4. The app still works — set Voice engine to "Natural"
> (edge-tts, needs internet) or "Local" (Piper, offline) in Settings.

### 5. Frontend

```bash
cd frontend
npm install
```

### 6. Run (two terminals)

```bash
# Terminal 1 — backend  (http://localhost:8000)
cd AI-phone
.venv\Scripts\python -m uvicorn backend.main:app --port 8000

# Terminal 2 — frontend  (http://localhost:3000)
cd AI-phone\frontend
npm run dev
```

Open **http://localhost:3000**.

---

## 🎙️ Clone your voice

1. Settings → **Voice engine = OmniVoice**.
2. Scroll to **"Clone your voice"** → tap 🎤, record ~5 seconds, tap ⏹.
3. Type **exactly what you said** in the box.
4. Maya now speaks in your voice.

---

## ✅ Quick test

1. **Talk to Maya** → tap 🎤, speak: *"दुई chicken momo र एक cold coffee"*.
2. *"Actually tinta momo banau"* → order updates.
3. *"Cold coffee remove"* → item removed.
4. *"Deliver, Baneshwor Eyeplex ko पछाडि"* → address captured.
5. *"rota cha?"* → "यो मेनुमा छैन" (not on menu).
6. Confirm in the **Live order** panel → lands in **Orders & calls**.

## 🛠️ Settings

- **AI engine** — DeepSeek (cloud, best) or Local (Ollama, offline).
- **Voice engine** — OmniVoice (human/clone) · Natural (edge-tts) · Local (Piper).
- **Speech recognition** — `small` (fast) … `large-v3` (best Nepali, slow).
- **Restaurant name / city** — drives the prompt and menu.

---

## 📝 Notes

- The DeepSeek key lives in a local `.env` (never committed). See `.env.example`.
- `data/` (SQLite + downloaded models) is git-ignored and recreated automatically.
- OmniVoice is licensed **CC-BY-NC** — do not use it for commercial voice cloning, and
  never clone someone's voice without their consent.
