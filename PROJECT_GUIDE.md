# Oro Agente Service - Guia del Proyecto

## Que es este proyecto?

Este proyecto es un **servicio de inteligencia artificial** que ayuda a los empleados a
gestionar sus vacaciones. El empleado le escribe por chat (como si fuera un asistente)
y el sistema hace dos cosas:

1. **Gestiona la solicitud de vacaciones**: la crea o consulta su estado, hablando
   siempre con el sistema MVC (Agente 1).
2. **Recomienda el viaje**: cuando la solicitud queda APROBADA, sugiere clima, vuelos,
   hoteles y actividades del destino (Agente 2).

Todo esto esta expuesto como un servicio web rapido (FastAPI) que corre en el puerto 8001.

---

## Importante: hay DOS repositorios

Este sistema esta dividido en **dos partes separadas** que se comunican por HTTP:

```
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│   SISTEMA MVC (C#)              │         │   SERVICIO DE AGENTES (Python)  │
│   REPOSITORIO SEPARADO          │         │   ESTE REPOSITORIO              │
│                                 │         │                                 │
│  - Interfaz de usuario (vistas) │  HTTP   │  - Recibe el chat del empleado  │
│  - API REST de vacaciones      │◄───────►│  - Orquesta agentes de IA       │
│  - Base de datos de vacaciones │         │  - Usa smolagents + OpenRouter  │
│  - Logica de negocio en C#      │         │  - Consulta la API del MVC      │
└─────────────────────────────────┘         └─────────────────────────────────┘
```

**Regla de oro**: Este repositorio Python **NUNCA** toca la base de datos de vacaciones
directamente. Siempre habla con el sistema MVC por HTTP. Es como un cliente que le
pregunta al servidor MVC "oye, crea esta solicitud" o "oye, como va esta solicitud?".

---

## Como se comunican los dos sistemas?

Esta es la parte mas importante de entender:

### Flujo de una consulta (empleado escribe "Quiero vacaciones del 1 al 15 de septiembre")

```
EMPLEADO
   |
   |  Escribe en el chat
   ▼
SISTEMA MVC (C#)                          <- Aqui vive la pantalla de chat
   |
   |  Hace un POST a http://localhost:8001/chat
   |  Body: {"mensaje": "Quiero vacaciones...", "empleadoId": "123"}
   ▼
FASTAPI (Python) - app/main.py            <- Recibe la peticion
   |
   |  Llama al orquestador
   ▼
ORQUESTADOR (Python)                      <- Decide que hacer y guarda memoria
   |
   |  Llama al Agente de Solicitudes
   ▼
AGENTE SOLICITUDES (Python)               <- El LLM interpreta el mensaje
   |
   |  Usa sus tools (funciones propias)
   ▼
VACACIONES API CLIENT (Python)            <- Hace una llamada HTTP
   |
   |  POST http://localhost:5000/api/vacaciones/solicitar
   ▼
SISTEMA MVC (C#) - API REST               <- Recibe la peticion HTTP
   |
   |  Crea la solicitud en su BD y responde
   |  Respuesta: {"solicitudId": "...", "estado": "aprobada", ...}
   ▼
VOLVEMOS HACIA ATRAS ─────────────────────────────────────────────────────┐
   |                                                                       │
   │  Si el estado es "aprobada", el orquestador activa al                 │
   ▼                                                                       │
AGENTE DE VIAJE (clima, vuelos, hoteles, actividades) ────────────────────┤
   |                                                                       │
   │  El orquestador junta ambos textos                                    │
   ▼                                                                       │
FASTAPI                                                                   │
   |                                                                       │
   │  Devuelve: {"respuesta": "Solicitud creada... + recomendaciones"}     │
   ▼                                                                       │
SISTEMA MVC (C#)                                                          │
   |                                                                       │
   │  Muestra la respuesta en el chat del empleado                        │
   ▼                                                                      │
EMPLEADO ve el resultado                                                  │
```

### La respuesta viaja por el mismo camino por donde llego

Esto es clave: **la respuesta viaja por HTTP de regreso por la misma conexion**.

El sistema MVC hace una peticion HTTP y **espera la respuesta** (como cuando abres
una pagina web y esperas que cargue). FastAPI recibe esa peticion, hace todo el
trabajo, y cuando termina **devuelve un JSON** como respuesta de esa misma peticion.

Es como una llamada telefonica:
- MVC llama a Python (peticion)
- Python hace su trabajo
- Python responde a MVC (respuesta)
- MVC muestra la respuesta al empleado

**No hay WebSockets, no hay colas, no hay nada raro.**

```
POST http://localhost:8001/chat
{
  "mensaje": "Quiero vacaciones del 1 al 15 de septiembre",
  "empleadoId": "123"
}
```

Y recibir como respuesta:
```
{
  "respuesta": "Tu solicitud fue creada con estado pendiente. ..."
}
```

---

## Arquitectura general en una imagen

```
                    ┌──────────────────────────────┐
                    │        app/main.py           │  <- Puerta de entrada (FastAPI)
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │   orchestrator.py            │  <- Jefe de piso + memoria
                    │   (usa ViajesStore)          │
                    └──────┬──────────────┬────────┘
                           │              │
          ┌────────────────▼───┐    ┌─────▼──────────────┐
          │ AgenteSolicitudes  │    │    AgenteViaje     │
          │ (crear/consultar)  │    │ (recomendaciones)  │
          └────────┬───────────┘    └─────┬──────────────┘
                   │                      │
        ┌──────────▼──────────┐   ┌───────▼───────────────┐
        │ tools.py (2 funcs)  │   │ tools.py (4 mocks)    │  <- Tools = funciones
        └──────────┬──────────┘   │ de clima/vuelos/etc.  │     Python propias
                   │              └───────────────────────┘
        ┌──────────▼──────────────────────┐
        │ VacacionesAPIClient             │  <- Unico punto HTTP hacia el MVC
        └──────────┬──────────────────────┘
                   │
     [mock] o [HTTP real al sistema C#]

  Ambos agentes usan el "cerebro" de IA asi:
        agente → llm.py (RobustServerModel) → smolagents OpenAIServerModel → OpenRouter
```

---

## Cada archivo que hace?

### `app/main.py` - El mostrador de recepcion

Punto de entrada del servicio. Es como el mostrador de recepcion de un hotel:
si alguien entra, aqui lo atienden.

- Expone `GET /health` para verificar que el servicio esta vivo.
- Expone `POST /chat`, por donde llegan todos los mensajes.
- Configura CORS (permite que el sistema MVC llame a este servicio desde otro dominio).
- Crea **un solo** orquestador (`Orchestrator()`) y le pasa cada mensaje.

**Que recibe:**
```json
{"mensaje": "Quiero vacaciones", "empleadoId": "123"}
```

**Que devuelve:**
```json
{"respuesta": "Tu solicitud fue creada..."}
```

---

### `app/config.py` - El archivo de configuracion

Lee las variables de entorno (el archivo `.env`) y las deja disponibles para todo el
proyecto en un objeto global llamado `settings`.

Que carga:
- `BASE_URL_VACACIONES_API` - URL del sistema MVC (ej: http://localhost:5000)
- `USE_MOCK_VACACIONES_API` - si es `true`, responde simulado sin llamar al MVC real
- `MOCK_ESTADO` - estado que devuelven los mocks (pendiente / aprobada / rechazada)
- `API_KEY_VACACIONES_API` - llave que se envia en el header `X-Api-Key` al MVC
- `MODEL_PROVIDER` / `MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME` - conexion al
  modelo de IA via **OpenRouter** (una API compatible con OpenAI)
- `MODEL_FALLBACK` - lista de modelos de respaldo separados por coma
- `HOST` / `PORT` - donde corre el servidor (por defecto 127.0.0.1:8001)
- `CORS_ORIGINS` - origenes permitidos para las peticiones

---

### `app/models/chat.py` - Los formularios del chat

Define como se ven los datos que entran y salen del endpoint `/chat`:

- `ChatRequest` - lo que envia el MVC: `mensaje` (texto obligatorio) y
  `empleadoId` (texto opcional; acepta ese nombre con alias).
- `ChatResponse` - lo que respondemos: `respuesta` (texto).

---

### `app/orchestrator/orchestrator.py` - El jefe de piso (con memoria)

Coordina a los dos agentes. Cuando llega un mensaje hace esto:

1. Llama al **AgenteSolicitudes** para crear o consultar la solicitud.
2. **Registra el viaje** en el store (memoria): guarda `{solicitud_id -> empleado,
   destino, fechas}`.
3. Arma el texto de respuesta con el resultado.
4. **Disparo del mismo turno**: si la solicitud recien creada ya viene `aprobada`
   y tiene destino, llama al **AgenteViaje** y agrega sus recomendaciones.
5. **Revision de aprobaciones previas**: en cada mensaje revisa los viajes guardados
   del empleado que aun no recibieron recomendaciones; consulta su estado en el MVC
   y, si alguno paso a `aprobada`, entrega el bloque de felicitacion +
   recomendaciones **una sola vez** (lo marca como entregado). Si la solicitud ya no
   existe (404), la saca de la memoria para no volver a consultarla.

---

### `app/store/viajes_store.py` - La libreta de apuntes del orquestador

Es la **memoria persistente** del orquestador. Guarda en un archivo JSON local
(`data/viajes_store.json`) el contexto de cada solicitud creada por chat:

```json
{
  "viajes": {
    "<solicitud_id>": {
      "empleado_id": "123",
      "destino": "Colombia",
      "fecha_inicio": "2026-11-11",
      "fecha_fin": "2026-11-15",
      "recomendaciones_entregadas": false
    }
  }
}
```

Funciones principales:
- `guardar_viaje(...)` - registra o actualiza el contexto.
- `viajes_pendientes_de_empleado(id)` - viajes cuyas recomendaciones aun no se dieron.
- `marcar_entregado(id)` - evita repetir las recomendaciones.
- `eliminar(id)` - borra solicitudes que ya no existen en el MVC.

Usa un candado (`threading.Lock`) para que dos peticiones simultaneas no pisen el
archivo. **Nunca** toca la base de datos del MVC: vive solo en este repositorio.

`data/viajes_store.json` es el archivo fisico donde quedan esos apuntes.

---

### `app/clients/vacaciones_api_client.py` - El traductor HTTP

Es el **unico lugar** en todo el proyecto que habla con el sistema MVC por HTTP.
Ningun otro archivo llama directamente al MVC.

Metodos:
- `crear_solicitud()` -> `POST {base_url}/api/vacaciones/solicitar`
- `consultar_estado()` -> `GET {base_url}/api/vacaciones/{id}/estado`

Detalles importantes:
- Envuelve errores de red/HTTP en excepciones claras para que el servicio no se caiga.
- Envia la llave en el header `X-Api-Key`.
- **Interruptor mock**: si `USE_MOCK_VACACIONES_API=true`, no llama al MVC; devuelve
  respuestas falsas con el estado configurado en `MOCK_ESTADO`. Esto permite probar
  TODO el flujo (incluido el AgenteViaje con estado `aprobada`) sin el sistema C#.

---

### `app/utils/logger.py` - El periodista

Configura el sistema de logs. Cada modulo pide su logger con `get_logger(__name__)` y
escribe en consola lineas con fecha, nivel y mensaje:

```
2026-08-21 10:15:32 | INFO | app.orchestrator.orchestrator | Orquestador recibe mensaje...
```

Sirve para debuggear, monitorear y auditar que paso en cada request.

---

## La parte de los AGENTES (en detalle)

### `app/agents/base_agent.py` - El contrato

Plantilla abstracta que dice: "todo agente debe tener un metodo `run()`". No hace nada
por si solo.

**Para que sirve?** Para que el orquestador pueda llamar a cualquier agente igual
(`agente.run(...)`) sin importar su interior. Si manana cambiamos algo, la forma de
llamarlos no cambia.

---

### `app/agents/llm.py` - AQUI VIVE SMOLAGENTS (el cable hacia la IA)

#### Que es smolagents?

**smolagents** es un framework de agentes de IA creado por Hugging Face (version 1.26.0
en este proyecto). Ofrece varias piezas:

| Pieza de smolagents | Para que sirve | La usamos? |
|---|---|---|
| `OpenAIServerModel` | Conectar con cualquier API compatible con OpenAI (OpenRouter, etc.) | **SI** - es lo unico que usamos |
| `CodeAgent` | Agente que escribe y ejecuta codigo Python para resolver tareas | No |
| `ToolCallingAgent` | Agente que decide llamar tools registradas | No |
| `@tool` / clase `Tool` | Registrar funciones como herramientas del agente | No |

#### Donde y como lo usamos?

En `llm.py` importamos su clase de modelo y la mejoramos:

```python
from smolagents import OpenAIServerModel

class RobustServerModel(OpenAIServerModel):
    ...
```

`RobustServerModel` hereda de `OpenAIServerModel` y le agrega dos cosas:

1. **Reintentos**: si la llamada al modelo falla, reintenta hasta 3 veces esperando
   un poco mas entre cada intento.
2. **Modelo de respaldo (fallback)**: si el modelo principal sigue fallando, prueba
   con los modelos de la lista `MODEL_FALLBACK` antes de rendirse.

La funcion `build_model()` crea ese modelo usando la configuracion de `.env`:

```
nuestro codigo -> RobustServerModel (llm.py)
                     -> hereda de OpenAIServerModel (smolagents)
                        -> habla con https://openrouter.ai/api/v1
                           -> OpenRouter nos da el modelo de IA elegido
```

En palabras sencillas: **smolagents nos presta el "cable" que conecta nuestro Python
con el cerebro de IA**. Nosotros no usamos sus agentes ni sus herramientas automaticas;
solo la pieza de conexion al modelo, reforzada con reintentos.

Los agentes obtienen el modelo perezosamente (lazy): la primera vez que lo necesitan,
llaman a `build_model()`. En los tests se inyecta un modelo falso (`FakeModel`) para no
gastar tokens ni necesitar internet.

---

### De donde salen las TOOLS?

Aqui hay algo importante para la exposicion: **las tools NO vienen de smolagents**.
Son funciones Python normales, escritas por nosotros, que viven en el archivo
`tools.py` de cada agente.

El patron que seguimos es: **"el LLM decide, nuestro codigo ejecuta"**.

1. El mensaje del empleado llega al agente.
2. El LLM (via smolagents/OpenRouter) interpreta el mensaje y responde un JSON con la
   intencion (que accion hacer y con que datos).
3. Con ese JSON, nuestro codigo Python hace un `if/else` y llama directamente a la
   funcion tool correcta.
4. La tool hace el trabajo real (HTTP, datos) y devuelve un diccionario.

Ventajas de este diseno:
- **Control total**: sabemos exactamente que tool se ejecuta y cuando (no depende de
  que el LLM "elija" una herramienta).
- **Fácil de probar**: las tools son funciones puras; en tests se reemplaza el cliente
  HTTP y listo.
- **Mas seguro**: nunca ejecutamos codigo generado por el LLM (eso haria CodeAgent).

#### Tools del Agente de Solicitudes (`app/agents/solicitudes/tools.py`)

- `crear_solicitud_vacaciones(empleado_id, fecha_inicio, fecha_fin, destino)` ->
  llama al `VacacionesAPIClient` para crear la solicitud via HTTP.
- `consultar_estado_solicitud(solicitud_id)` -> llama al cliente para consultar estado.

Ambas completan campos faltantes con valores por defecto (`setdefault`) para que la
respuesta sea siempre predecible. Nunca hablan con la base de datos: siempre viajan
por el cliente HTTP.

#### Tools del Agente de Viaje (`app/agents/viajes/tools.py`) - MOCKS

Son 4 funciones que devuelven **datos de ejemplo** (estan marcadas como `[mock]`):

- `buscar_clima(destino, ...)` - resumen de clima tipico y temperaturas.
- `buscar_vuelos(destino, ...)` - opciones de vuelo con precio y escalas.
- `buscar_hoteles(destino, ...)` - hoteles con precio por noche.
- `sugerir_actividades(destino, ...)` - lista de actividades populares.

Estas son las piezas que eventualmente otro equipo conectara a APIs reales de clima,
vuelos y hoteles.

---

### `app/agents/solicitudes/` - Agente 1: Gestor de vacaciones

Tres archivos trabajan juntos:

#### `agent.py` - El cerebro del agente

Clase `AgenteSolicitudes(BaseAgent)`. Su metodo `run(mensaje, empleado_id)` hace esto:

1. **Analiza el mensaje** (`_analizar`): le pregunta al LLM con un prompt de sistema
   que le exige responder UNICAMENTE un JSON:
   ```json
   {
     "accion": "crear" o "consultar",
     "solicitud_id": "GUID o null",
     "empleado_id": "texto o null",
     "fecha_inicio": "YYYY-MM-DD o null",
     "fecha_fin": "YYYY-MM-DD o null",
     "destino": "texto o null"
   }
   ```
   Extrae ese JSON de la respuesta y lo convierte en `IntencionSolicitud`.
2. **Plan B (heuristica)**: si el LLM falla (sin internet, sin API key, JSON roto),
   usa reglas simples con expresiones regulares: busca palabras como "consultar/
   estado", busca GUIDs o fechas con formato dd/mm/yyyy, etc.
3. **Decide y ejecuta**:
   - Si es `consultar` con id -> llama a la tool `consultar_estado_solicitud`.
   - Si es `crear` pero faltan fechas o empleado -> responde "incompleta" pidiendo
     los datos que faltan.
   - Si es `crear` completo -> llama a la tool `crear_solicitud_vacaciones`.
4. Traduce errores comunes a mensajes amables (ej: si la solicitud no existe, sugiere
   revisar el identificador o crear una nueva).

#### `tools.py` - Las herramientas (explicadas arriba)

#### `schemas.py` - Los formularios

- `SolicitudInput` -> empleado_id + mensaje.
- `IntencionSolicitud` -> lo que el LLM entiende del mensaje (accion, ids, fechas).
- `SolicitudOutput` (y sus variantes Crear/Consultar) -> lo que el agente devuelve:
  accion, solicitud_id, estado, fechas, destino y mensaje final.

---

### `app/agents/viajes/` - Agente 2: Recomendador de viaje

Tres archivos:

#### `agent.py` - El asesor de viajes

Clase `AgenteViaje(BaseAgent)`. Su `run(destino, fecha_inicio, fecha_fin, mensaje)`:

1. **Recolecta datos** (`_recolectar`): llama sus 4 tools mock (clima, vuelos,
   hoteles, actividades).
2. **Redacta** (`_redactar`): le pasa todos esos datos al LLM junto con un prompt de
   "asesor de viajes" para que escriba una recomendacion breve (maximo 8 lineas),
   amable y SIN inventar datos.
3. **Plan B**: si el LLM falla, arma un texto basico eligiendo el vuelo y hotel mas
   baratos de los datos mock.

#### `tools.py` - Las 4 herramientas mock (explicadas arriba)

#### `schemas.py` - Los formularios

- `ViajeInput` -> destino, fechas opcionales y mensaje.
- `ViajeOutput` -> destino, fechas, `recomendaciones` (texto) y mensaje.

---

## Flujo completo: de principio a fin

Cuando un empleado escribe "Quiero vacaciones del 1 al 15 de septiembre a Colombia":

```
1. El empleado escribe en el chat del sistema MVC (la pantalla en C#).

2. El MVC hace POST a este servicio:
   POST http://localhost:8001/chat
   {"mensaje": "...", "empleadoId": "123"}

3. main.py recibe y llama a Orchestrator.responder().

4. El orquestador llama al AgenteSolicitudes.

5. El agente le pregunta al LLM (RobustServerModel -> smolagents -> OpenRouter):
   "que quiere este empleado?" -> JSON: accion=crear, fechas, destino.

6. El agente llama su tool crear_solicitud_vacaciones ->
   VacacionesAPIClient.

7. El cliente hace POST a la API del MVC (o devuelve mock segun .env).

8. El MVC crea la solicitud y responde: {solicitudId, estado}.

9. El orquestador GUARDA el contexto en data/viajes_store.json
   (solicitud -> empleado, destino, fechas).

10. Caso A (mismo turno): si el estado ya es "aprobada", el orquestador llama
    al AgenteViaje con el destino -> recolecta clima/vuelos/hoteles/actividades
    (mocks) -> el LLM redacta recomendaciones -> se agregan a la respuesta.

    Caso B (turnos siguientes): si el estado era "pendiente", el orquestador
    recuerda el viaje. En cualquier mensaje futuro vuelve a consultar el estado;
    cuando pasa a "aprobada", entrega las recomendaciones UNA sola vez.

11. La respuesta combinada vuelve por HTTP al MVC y se muestra en el chat.
```

---

## Las pruebas (`tests/`)

Se corren con `pytest` desde la raiz del proyecto. El archivo `conftest.py` agrega la
raiz al path para que los imports `from app...` funcionen.

- `test_agente_solicitudes.py` -> prueba el analisis del mensaje (LLM falso y
  heuristica), la creacion y consulta de solicitudes, y el manejo de errores con un
  `FakeClient`.
- `test_agente_viajes.py` -> prueba las 4 tools mock, la redaccion del LLM (con
  `FakeModel`) y el texto basico de respaldo cuando el modelo falla.
- `test_orchestrator.py` -> prueba la coordinacion completa con un `FakeStore` (misma
  interfaz de `ViajesStore`) y un `FakeEstadoClient`: disparo del mismo turno,
  revision de aprobaciones previas, entrega unica y limpieza de solicitudes 404.
- `test_vacaciones_api_client.py` -> prueba el cliente HTTP real con respuestas
  falsificadas (`FakeResponse`): exito, errores 4xx/5xx, headers y modo mock.
- `test_viajes_store.py` -> prueba guardar/obtener, pendientes por empleado,
  marcar entregado y eliminar (usando archivos temporales).

---

## `.env.example` - La plantilla de configuracion

Ejemplo de como debe verse el `.env`. Se copia como `.env` y se llenan los valores
reales. **Nunca** se sube el `.env` real a Git.

Variables actuales:
- `BASE_URL_VACACIONES_API`, `USE_MOCK_VACACIONES_API`, `MOCK_ESTADO`,
  `API_KEY_VACACIONES_API`
- `MODEL_PROVIDER`, `MODEL_API_KEY`, `MODEL_BASE_URL`, `MODEL_NAME`, `MODEL_FALLBACK`
- `HOST`, `PORT`, `CORS_ORIGINS`

---

## `requirements.txt` - La lista de compras

```
fastapi          - El framework web
uvicorn          - El servidor que ejecuta FastAPI
pydantic         - Validacion y estructura de datos (formularios/schemas)
requests         - Cliente HTTP para hablar con el MVC
python-dotenv    - Leer el archivo .env
smolagents 1.26.0- Framework de Hugging Face; usamos su OpenAIServerModel
openai >= 1.0    - Cliente base que OpenAIServerModel usa por debajo
pytest           - Para correr las pruebas
```

---

## `.gitignore` - Lo que Git ignora

- `.env` (contrasenas)
- `venv/` (entorno virtual)
- `__pycache__/` y `.pytest_cache/` (caches)
- `data/viajes_store.json` deberia considerarse dato local del servicio

---

## Estado del proyecto

- [x] Implementar el codigo real (agente de solicitudes, orquestador, API)
- [x] Integrar framework de agentes (smolagents como capa de modelo)
- [x] Conectar modelo de IA via OpenRouter (con reintentos y fallback)
- [x] Agente de viaje con recomendaciones generadas por IA (datos mock)
- [x] Memoria de conversacion persistente (ViajesStore)
- [ ] Reemplazar las tools mock de viaje por APIs reales de clima/vuelos/hoteles
      (equipo correspondiente)
- [ ] Conectar con el MVC real (desactivar mocks)
- [ ] Hacer que el MVC llame a `POST /chat` y muestre la respuesta en el chat
