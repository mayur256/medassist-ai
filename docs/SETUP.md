# MedAssist-CDSS — Setup Guide

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- Docker (for PostgreSQL)

---

## 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Create Virtual Environment

```bash
cd medassist-ai
uv venv
```

This creates a `.venv` directory using Python 3.12.

---

## 3. Install Dependencies

```bash
uv pip install ".[dev]"
```

---

## 4. Environment Variables

Copy the example env file:

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
API_KEY=<your-api-key>
HF_API_TOKEN=<your-huggingface-token>
GROQ_API_KEY=<your-groq-api-key>
HF_HUB_DISABLE_SSL_VERIFY=1
```

---

## 5. Start PostgreSQL

```bash
docker-compose up -d
```

This starts PostgreSQL on port `5437`.

---

## 6. Run Database Seeder

```bash
uv run python scripts/seed.py
```

---

## 7. Start the Server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

---

## 8. Verify

```bash
curl http://localhost:8000/health
```

Expected response: `{"status": "ok"}`

---

## 9. Run Tests

```bash
uv run pytest
```

---

## SSL Issues (Corporate Proxy)

If you're behind a corporate proxy with self-signed certificates, ensure your `.env` has:

```env
HF_HUB_DISABLE_SSL_VERIFY=1
```

This allows HuggingFace model downloads to bypass SSL verification.
