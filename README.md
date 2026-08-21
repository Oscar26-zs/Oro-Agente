# Oro-Agente 🏖️

Servicio Python que expone, vía FastAPI, un chat de asistente de vacaciones con **dos agentes de IA**: uno gestiona las solicitudes de vacaciones y otro prepara el plan de viaje cuando la solicitud es aprobada. El sistema de solicitud de vacaciones (interfaz de usuario y API REST) vive en un **repositorio aparte** (C# MVC); este servicio se limita a consumirlo vía HTTP.

## 📋 Descripción General

1. El empleado escribe en el chat algo como *"Quiero tomar vacaciones del 10 al 15 de septiembre yendo a Panamá"*.
2. El **Agente de Solicitudes** interpreta la intención, crea la solicitud llamando a la API externa o consulta su estado.
3. Cuando una solicitud queda **aprobada**, el orquestador **ofrece** preparar un plan de viaje.
4. Cuando el empleado **pide su plan**, el **Agente de Viajes** investiga clima, vuelos, hoteles y actividades, y redacta las recomendaciones.
5. El orquestador devuelve todo al empleado dentro del mismo chat.

## 🗂️ Repositorios relacionados

| Repositorio | Responsabilidad |
|---|---|
| Sistema de Vacaciones (C# MVC) | Interfaz del empleado, lógica de aprobación, API REST `/api/vacaciones/...` |
| **Oro-Agente (este repo, Python)** | Agentes de IA, orquestación, memoria de conversación, endpoint de chat |

Este repo **no genera** vistas, controladores ni pantallas — solo consume la API del otro sistema.

## 🤖 Agentes

### 1. Agente de Solicitudes (`agente_solicitudes`)
Clasifica cada mensaje en una de **cuatro intenciones** y actúa en consecuencia:

| Intención | Ejemplos | Qué hace |
|---|---|---|
| `crear` | *"Quiero vacaciones del 10 al 15 a Cancún"* | Crea la solicitud vía `POST /api/vacaciones/solicitar`. Si faltan fechas pide lo que falta |
| `consultar` | *"¿Cómo va mi solicitud?"* | Consulta estado vía `GET /api/vacaciones/{id}/estado`. **Sin GUID**: resuelve "mi solicitud" con la última registrada del empleado en el contexto |
| `plan` | *"Quiero mi plan de viaje"* | Señal para el orquestador: entrega el plan del Agente de Viajes (sin agregar texto propio) |
| `ayuda` | *"hola"*, *"gracias"* | Menú breve con lo que puede hacer |

Extras:
- Preguntas por el estado **jamás** se confunden con creación ni piden fechas.
- Errores amigables: una solicitud inexistente (404) responde con una explicación clara en vez del error crudo.
- Clasificación doble capa: LLM (smolagents/OpenRouter) con heurística de palabras clave como respaldo si el modelo falla o devuelve JSON inválido.

### 2. Agente de Viajes (`agente_viaje`)
Se activa **solo cuando el empleado pide su plan** y la solicitud está aprobada:
- Recolecta datos de referencia: clima, vuelos, hoteles y actividades del destino (`app/agents/viajes/tools.py`, actualmente fuentes simuladas).
- Redacta un plan breve y amable en español con el LLM (con resumen básico de respaldo si falla).

### Orquestador
Coordina ambos agentes y aplica las reglas de conversación:
- **Ofrecer siempre**: si una solicitud sale aprobada (al crearla o al consultarla), agrega la oferta *"—¿Quieres que te prepare tu plan de viaje?"*. Nunca entrega el plan sin permiso.
- **Entrega bajo petición**: solo entrega recomendaciones cuando el mensaje pide explícitamente el plan (señal `plan` del clasificador o palabras clave de respaldo).
- **Una sola vez**: cada plan se entrega una única vez; si se vuelve a pedir responde *"Ya te entregué tu plan de viaje…"*.
- Si el plan se pide con la solicitud pendiente/rechazada, informa la situación en lugar de callarse.
- Saludos y preguntas de estado **nunca** activan al Agente de Viaje.
- Registra cada solicitud creada/consultada en el store y **retira automáticamente** entradas que ya no existen en el sistema (404).

### Store de contexto (`ViajesStore`)
Memoria persistente en `data/viajes_store.json` (gitignored): `{solicitud_id → empleado_id, destino, fechas, recomendaciones_entregadas}`. Es lo que permite responder *"¿cómo va mi solicitud?"* sin GUID y recordar qué planes ya se entregaron.

## 💬 Flujo de conversación

```
Empleado: Quiero vacaciones del 10 al 15 de septiembre a Cancún
Bot:      Solicitud creada #GUID con estado pendiente.

(Aprobador acepta en el dashboard del MVC)

Empleado: ¿Cómo va mi solicitud?
Bot:      La solicitud #GUID figura con estado aprobada. Si quieres, te preparo
          tu plan de viaje: escribe "quiero mi plan de viaje"...

Empleado: quiero mi plan de viaje
Bot:      Buenas noticias: tu solicitud fue APROBADA... [clima + vuelos +
          hoteles + actividades] 🎯

Empleado: otra vez el plan
Bot:      Ya te entregué tu plan de viaje. Si necesitas consultarlo de nuevo...
```

```
Empleado (chat)
   │
   ▼
[Orquestador] ◀── contexto ──▶ [ViajesStore · data/viajes_store.json]
   │
   ├──▶ [agente_solicitudes] ── crea/consulta ──▶ API externa (repo C# MVC)
   │
   └──▶ [agente_viaje] ── clima/vuelos/hoteles/actividades ──▶ plan redactado
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
│   │   └── orchestrator.py          # Reglas de conversación, oferta y entrega del plan
│   ├── agents/
│   │   ├── base_agent.py            # Interfaz común de los agentes (run(input) -> output)
│   │   ├── llm.py                   # Modelo robusto de IA (smolagents) con reintentos y fallback
│   │   ├── solicitudes/
│   │   │   ├── agent.py             # Clasificador de intenciones + creación/consulta
│   │   │   ├── tools.py             # Tools: crear solicitud, consultar estado (vía API externa)
│   │   │   └── schemas.py           # Modelos de entrada/salida de este agente
│   │   └── viajes/
│   │       ├── agent.py             # Agente de Viaje: recolecta datos y redacta el plan
│   │       ├── tools.py             # Tools simuladas: clima, vuelos, hoteles, actividades
│   │       └── schemas.py           # Modelos de entrada/salida de este agente
│   ├── store/
│   │   └── viajes_store.py          # Memoria persistente del contexto (JSON local)
│   ├── clients/
│   │   └── vacaciones_api_client.py # Cliente HTTP contra la API del repo C# MVC (+ modo mock)
│   ├── models/
│   │   └── chat.py                  # Modelos del endpoint de chat: ChatRequest, ChatResponse
│   └── utils/
│       └── logger.py                # Configuración de logging compartida
├── data/
│   └── viajes_store.json            # Contexto de conversaciones (generado, gitignored)
├── tests/                           # 60 pruebas (pytest)
│   ├── test_agente_solicitudes.py
│   ├── test_agente_viajes.py
│   ├── test_orchestrator.py
│   ├── test_vacaciones_api_client.py
│   └── test_viajes_store.py
├── .env.example                     # Variables: BASE_URL_VACACIONES_API, MOCK_ESTADO, MODEL_*, HOST, PORT...
├── requirements.txt
├── PROJECT_GUIDE.md
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
BASE_URL_VACACIONES_API=http://localhost:5000    # URL del sistema C# MVC (otro repositorio)
USE_MOCK_VACACIONES_API=false                    # true = respuestas simuladas
MOCK_ESTADO=pendiente                            # estado de los mocks: pendiente | aprobada | rechazada
API_KEY_VACACIONES_API=dev-key-vacaciones-agent1 # header X-Api-Key esperado por el monolito C#
MODEL_PROVIDER=openrouter
MODEL_API_KEY=
MODEL_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=tu-modelo
MODEL_FALLBACK=                                  # modelos de respaldo separados por coma (opcional)
HOST=127.0.0.1
PORT=8001
CORS_ORIGINS=*
```

> 💡 Para probar el flujo completo sin el MVC real: `USE_MOCK_VACACIONES_API=true` + `MOCK_ESTADO=aprobada`.

## ▶️ Uso

```bash
python -m app.main   # o: uvicorn app.main:app --host 0.0.0.0 --port 8001
```

El sistema C# MVC (otro repositorio) consumirá el endpoint `POST /chat` de este servicio.

## 🧪 Pruebas

```bash
pytest -q   # 60 pruebas: agentes, orquestador, store y cliente HTTP
```

Cobertura clave: clasificación de intenciones, consulta sin GUID vía contexto, reglas de oferta/entrega del plan ("una sola vez"), retiro de solicitudes inexistentes y persistencia del store.

## 📌 Contrato con la API externa (sistema de vacaciones)

Este servicio depende de los siguientes endpoints, expuestos por el **otro repositorio**:

```
POST /api/vacaciones/solicitar
GET  /api/vacaciones/{solicitudId}/estado
```

> ⚠️ Si esos endpoints cambian de forma o de ruta en el otro repositorio, hay que actualizar `vacaciones_api_client.py` en consecuencia.
