# Running Kothon as a live demo

Kothon can run in fixture mode without credentials, or use Groq for real
transcription and translation when the environment is configured.

```powershell
docker build -t kothon .
docker run --rm -p 8000:8000 kothon
```

Open `http://127.0.0.1:8000/`. The API documentation is available at
`http://127.0.0.1:8000/docs`.

For real provider mode, pass credentials and model names without committing
them:

```powershell
docker run --rm -p 8000:8000 `
  -e GROQ_API_KEY="..." `
  -e GROQ_TRANSCRIPTION_MODEL="..." `
  -e GROQ_TEXT_MODEL="..." `
  kothon
```

The application labels fixture mode explicitly. It must not be presented as
real ASR accuracy in a hackathon demo.

