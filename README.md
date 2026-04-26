# MS4 - Orquestador de Senales

Servicio que combina precios, sentimiento de noticias e IA opcional para generar senales de trading y respuestas conversacionales.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenRouter-Compatible-412991?style=for-the-badge&logo=openai&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-20232A?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

## Responsabilidad

- Consultar precios recientes desde MS2.
- Consultar sentimiento agregado desde MS3.
- Generar una senal: `Compra`, `Venta`, `Mantener` o `Sin datos suficientes`.
- Responder consultas de chat financiero usando contexto y datos recientes.
- **FinBot (chat):** Groq si `GROQ_API_KEY` esta definida; si no, OpenRouter con `OPENROUTER_API_KEY`.
- **Señales IA:** OpenRouter; si no hay key, fallback por reglas.

## Requisitos

- Python 3.11+
- pip
- MS2 Historial de Precios disponible
- MS3 Feed de Noticias disponible
- API key de Groq para FinBot (opcional) y/o OpenRouter para Señales IA (opcional)

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Variables de entorno

```env
MS2_URL=http://localhost:5002
MS3_URL=http://localhost:5003
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_groq_model
OPENROUTER_API_KEY=your_openrouter_api_key
```

- Sin `GROQ_API_KEY`, el chat usa OpenRouter si hay `OPENROUTER_API_KEY`.
- Sin ninguna key de chat, FinBot responde con un mensaje de no configurado.
- Sin `OPENROUTER_API_KEY`, Señales IA usa solo el fallback basado en reglas.

## Ejecutar en desarrollo

```bash
python app/main.py
```

El servicio queda disponible en:

```text
http://localhost:5004
```

## Endpoints principales

| Metodo | Ruta | Descripcion |
| ------ | ---- | ----------- |
| GET | `/health` | Health check del servicio |
| GET | `/api/senales/:simbolo` | Genera senal para un simbolo |
| POST | `/api/chat` | Chat financiero con contexto |

## Ejemplo de senal

```bash
curl http://localhost:5004/api/senales/AAPL
```

Respuesta esperada:

```json
{
  "simbolo": "AAPL",
  "precios_disponibles": 10,
  "senal": "Compra",
  "confianza": 72,
  "mensaje": "Noticias optimistas y tendencia alcista confirmada",
  "sentimiento": "Bullish",
  "variacion_precio": 1.24
}
```

## Docker

```bash
docker build -t fintrend-ms4-senales .
docker run --env-file .env -p 5004:5004 fintrend-ms4-senales
```

## Estructura

```text
.
├── app/
│   └── main.py
├── requirements.txt
├── Dockerfile
├── .gitignore
└── .env.example
```
