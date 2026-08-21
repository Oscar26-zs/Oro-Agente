# Oro-Agente

Servicio de agentes de IA (smolagents) expuesto como API FastAPI, consumido por
el sistema de vacaciones C# MVC para dar soporte a un chat de empleados.

## Arquitectura

- `agente_solicitudes`: crea y consulta solicitudes de vacaciones contra la API
  del sistema C# MVC (`VACACIONES_API_URL`).
- `agente_viaje`: si la solicitud está aprobada, investiga vuelos, hoteles,
  clima y actividades del destino usando búsqueda web y wttr.in.
- La orquestación es determinística en Python (`app/orchestrator`): siempre se
  ejecuta primero `agente_solicitudes` y solo se llama a `agente_viaje` si el
  estado es "aprobada". Sin LLM orquestador: menos pasos y menos tokens.

Modelo LLM: cadena de respaldo entre proveedores con API compatible con
OpenAI — Gemini > Groq > Cerebras > OpenRouter (modelos ":free") — configurada
en `app/config.py` vía las variables `GEMINI_API_KEY`, `GROQ_API_KEY`,
`CEREBRAS_API_KEY`, `OPENROUTER_API_KEY` (y `HF_TOKEN` como última opción).
Si un proveedor agota su cuota gratuita (429), la petición salta al siguiente
de la cadena al instante.

## Cómo levantar el servicio

1. Crear y activar el entorno virtual:

   ```
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Linux/Mac
   ```

2. Instalar dependencias:

   ```
   pip install -r requirements.txt
   ```

3. Copiar `.env.example` a `.env` y completar `HF_TOKEN` con un token válido
   de HuggingFace (https://huggingface.co/settings/tokens).

4. Levantar el servicio:

   ```
   uvicorn app.main:app --reload --port 8001
   ```

5. Probar el endpoint:

   ```
   curl -X POST http://localhost:8001/chat \
     -H "Content-Type: application/json" \
     -d "{\"mensaje\": \"Quiero vacaciones en Panama del 10 al 15 de septiembre\", \"empleadoId\": 1}"
   ```

## Pruebas

```
pytest
```

Las pruebas usan mocks sobre las llamadas de red (API de vacaciones y
wttr.in) y no requieren `HF_TOKEN` ni el sistema C# MVC corriendo, porque no
ejecutan el modelo LLM real. Las pruebas de integración end-to-end contra el
sistema C# MVC real (Fase 8 de `TAREAS.md`) sí lo requieren.
