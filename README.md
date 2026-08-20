# Oro-Agente 🏖️

Servicio Python que expone, vía FastAPI, un chat de asistente de vacaciones impulsado por **dos agentes de IA** orquestados entre sí. Este repositorio contiene **únicamente la capa de agentes**: el sistema de solicitud de vacaciones (interfaz de usuario y API REST) vive en un **repositorio aparte** (C# MVC), y este servicio se limita a consumirlo vía HTTP.

## 📋 Descripción General

El flujo completo funciona así:

1. El empleado escribe en el chat algo como *"Quiero tomar vacaciones del 10 al 15 de septiembre yendo a Panamá"*.
2. El **Agente de Solicitudes** crea esa solicitud llamando a la API externa del sistema de vacaciones (otro repositorio) y consulta su estado.
3. El **Orquestador** solo avanza al siguiente paso si la solicitud está **aprobada**.
4. El **Agente de Viaje** busca información del destino (clima, vuelos, hoteles, actividades).
5. El orquestador devuelve un resumen consolidado al empleado dentro del mismo chat.

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

### 2. Agente de Viaje (`agente_viaje`)
Investiga información del destino una vez que la solicitud está aprobada.

**Responsabilidades:**
- Buscar clima, vuelos, hoteles y actividades para el destino y fechas indicados.
- Usa APIs externas o búsqueda web (pendiente de definir cuáles).

### Orquestador
Coordina a ambos agentes y aplica la regla de negocio central: **solo llama al Agente de Viaje si el estado de la solicitud es "aprobada"**.

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
¿Estado == "aprobada"?
   │ sí
   ▼
[agente_viaje] ── busca clima/vuelos/hoteles/actividades ──▶ APIs externas
   │
   ▼
Resumen consolidado → respuesta en el chat
```

## 🛠️ Tecnologías

- **Lenguaje:** Python
- **API del servicio:** FastAPI
- **Framework de agentes / modelo de IA:** aún por definir (la interfaz de cada agente queda desacoplada para poder conectar cualquier framework después, ej. smolagents, LangChain, CrewAI)
- **Comunicación con el sistema de vacaciones:** HTTP/JSON contra la API del otro repositorio

## 📁 Estructura del Proyecto

```
oro-agente-service/
├── app/
│   ├── main.py                      # Punto de entrada de la app FastAPI; expone POST /chat
│   ├── config.py                    # Carga de variables de entorno (.env)
│   ├── orchestrator/
│   │   └── orchestrator.py          # Orquesta agente_solicitudes y agente_viaje; aplica la regla de "solo si está aprobada"
│   ├── agents/
│   │   ├── base_agent.py            # Interfaz común que deben implementar todos los agentes (run(input) -> output)
│   │   ├── solicitudes/
│   │   │   ├── agent.py             # Definición del agente_solicitudes
│   │   │   ├── tools.py             # Tools del agente: crear solicitud, consultar estado (vía API externa)
│   │   │   └── schemas.py           # Modelos de entrada/salida de este agente
│   │   └── viaje/
│   │       ├── agent.py             # Definición del agente_viaje
│   │       ├── tools.py             # Tools del agente: buscar clima, vuelos, hoteles, actividades
│   │       └── schemas.py           # Modelos de entrada/salida de este agente
│   ├── clients/
│   │   └── vacaciones_api_client.py # Cliente HTTP que consume la API del repositorio C# MVC (no la implementa)
│   ├── models/
│   │   └── chat.py                  # Modelos del endpoint de chat: ChatRequest, ChatResponse
│   └── utils/
│       └── logger.py                # Configuración de logging compartida por agentes y orquestador
├── tests/
│   ├── test_orchestrator.py
│   ├── test_agente_solicitudes.py
│   └── test_agente_viaje.py
├── .env.example                     # Variables: BASE_URL_VACACIONES_API, MODEL_PROVIDER, WEATHER_API_KEY, etc.
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
MODEL_PROVIDER=                                   # Pendiente de definir
MODEL_API_KEY=
WEATHER_API_KEY=
```

## ▶️ Uso

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

El sistema C# MVC (otro repositorio) consumirá el endpoint `POST /chat` de este servicio.

## 📌 Contrato con la API externa (sistema de vacaciones)

Este servicio depende de los siguientes endpoints, expuestos por el **otro repositorio**:

```
POST /api/vacaciones/solicitar
GET  /api/vacaciones/{solicitudId}/estado
```

> ⚠️ Si esos endpoints cambian de forma o de ruta en el otro repositorio, hay que actualizar `vacaciones_api_client.py` en consecuencia.

## 🗺️ Pendientes / Decisiones abiertas

- Definir el framework de agentes a usar (smolagents, LangChain, CrewAI, u otro).
- Definir el modelo de IA a usar.
- Definir las APIs externas de clima/vuelos/hoteles.
- Decidir estrategia de espera por aprobación (polling vs. webhook).

## 📄 Licencia

Este proyecto se distribuye bajo la licencia que definas (MIT, Apache 2.0, etc.).
