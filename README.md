# Oro-Agente 🏖️

Servicio Python que expone, vía FastAPI, un chat de asistente de vacaciones. Este repositorio contiene **únicamente la capa de agentes**: el sistema de solicitud de vacaciones (interfaz de usuario y API REST) vive en un **repositorio aparte** (C# MVC), y este servicio se limita a consumirlo vía HTTP.

Las tareas de investigación de viajes (clima, vuelos, hoteles, actividades) no son responsabilidad de este equipo: las cubre otro equipo de desarrolladores.

## 📋 Descripción General

1. El empleado escribe en el chat algo como *"Quiero tomar vacaciones del 10 al 15 de septiembre yendo a Panamá"*.
2. Este servicio interpreta el mensaje, crea la solicitud llamando a la API externa del sistema de vacaciones (otro repositorio) o consulta su estado.
3. El orquestador devuelve la respuesta al empleado dentro del mismo chat.

## 🗂️ Repositorios relacionados

| Repositorio | Responsabilidad |
|---|---|
| Sistema de Vacaciones (C# MVC) | Interfaz del empleado, lógica de aprobación, API REST `/api/vacaciones/...` |
| **Oro-Agente (este repo, Python)** | Agentes de IA, orquestación, endpoint de chat |

Este repo **no genera** vistas, controladores ni pantallas — solo consume la API del otro sistema.

## 🤖 Agentes

### 1. Agente de Solicitudes (`agente_solicitudes`)
Gestiona la solicitud de vacaciones consumiendo la API externa del sistema C# MVC.

**Responsabilidades:**
- Crear la solicitud (días, destino, fechas) llamando a `POST /api/vacaciones/solicitar` en el sistema externo.
- Consultar el estado de la solicitud vía `GET /api/vacaciones/{id}/estado`.
- Nunca accede a datos de vacaciones directamente: todo pasa por el cliente HTTP hacia el otro repositorio.

### Orquestador
Recibe el mensaje del empleado y lo delega al Agente de Solicitudes, devolviendo el resultado al chat.

## 🔄 Flujo de Trabajo

```
Empleado (chat)
   │
   ▼
[Orquestador]
   │
   ▼
[agente_solicitudes] ── crea/consulta solicitud ──▶ API externa (repo C# MVC)
   │
   ▼
Respuesta → chat
```

## 🛠️ Tecnologías

- **Lenguaje:** Python
- **API del servicio:** FastAPI
- **Framework de agentes / modelo de IA:** smolagents (modelo con reintentos y fallback contra OpenRouter)
- **Comunicación con el sistema de vacaciones:** HTTP/JSON contra la API del otro repositorio

## 📁 Estructura del Proyecto

```
oro-agente-service/
├── app/
│   ├── main.py                      # Punto de entrada de la app FastAPI; expone POST /chat
│   ├── config.py                    # Carga de variables de entorno (.env)
│   ├── orchestrator/
│   │   └── orchestrator.py          # Orquesta el flujo de solicitudes de vacaciones
│   ├── agents/
│   │   ├── base_agent.py            # Interfaz común que deben implementar todos los agentes (run(input) -> output)
│   │   ├── llm.py                   # Modelo robusto de IA (smolagents) con reintentos y fallback
│   │   └── solicitudes/
│   │       ├── agent.py             # Definición del agente_solicitudes
│   │       ├── tools.py             # Tools del agente: crear solicitud, consultar estado (vía API externa)
│   │       └── schemas.py           # Modelos de entrada/salida de este agente
│   ├── clients/
│   │   └── vacaciones_api_client.py # Cliente HTTP que consume la API del repositorio C# MVC (no la implementa)
│   ├── models/
│   │   └── chat.py                  # Modelos del endpoint de chat: ChatRequest, ChatResponse
│   └── utils/
│       └── logger.py                # Configuración de logging compartida por agentes y orquestador
├── tests/
│   ├── test_orchestrator.py
│   └── test_agente_solicitudes.py
├── .env.example                     # Variables: BASE_URL_VACACIONES_API, MODEL_*, HOST, PORT
├── requirements.txt
├── README.md
└── .gitignore
```

## ⚙️ Instalación

```bash
git clone <url-del-repo>
cd oro-agente-service

python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## 🔑 Configuración

Crear un archivo `.env` a partir de `.env.example`:

```env
BASE_URL_VACACIONES_API=http://localhost:5000   # URL del sistema C# MVC (otro repositorio)
USE_MOCK_VACACIONES_API=true                     # true = respuestas simuladas
MODEL_API_KEY=
MODEL_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=tu-modelo
```

## ▶️ Uso

```bash
python -m app.main   # o: uvicorn app.main:app --host 0.0.0.0 --port 8001
```

El sistema C# MVC (otro repositorio) consumirá el endpoint `POST /chat` de este servicio.

## 📌 Contrato con la API externa (sistema de vacaciones)

Este servicio depende de los siguientes endpoints, expuestos por el **otro repositorio**:

```
POST /api/vacaciones/solicitar
GET  /api/vacaciones/{solicitudId}/estado
```

> ⚠️ Si esos endpoints cambian de forma o de ruta en el otro repositorio, hay que actualizar `vacaciones_api_client.py` en consecuencia.