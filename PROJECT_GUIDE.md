# Oro Agente Service - Guia del Proyecto

## Que es este proyecto?

Este proyecto es un **servicio de inteligencia artificial** que ayuda a los empleados a
gestionar sus vacaciones. El empleado le escribe por chat (como si fuera un asistente)
y el sistema:

1. **Gestiona la solicitud de vacaciones**: la crea o consulta su estado, hablando siempre
   con el sistema MVC.

> **Nota**: la investigacion de destinos (vuelos, hoteles, clima, actividades) la cubre
> **otro equipo de desarrolladores**; no es parte de este repositorio.

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
│  - API REST de vacaciones       │◄───────►│  - Orquesta agentes de IA       │
│  - Base de datos de vacaciones  │         │  - Consulta la API del MVC      │
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
   │
   │  Escribe en el chat
   ▼
SISTEMA MVC (C#)                          ← Aqui vive la pantalla de chat
   │
   │  Hace un POST a http://localhost:8001/chat
   │  Body: {"mensaje": "Quiero vacaciones...", "empleadoId": 123}
   ▼
FASTAPI (Python) - app/main.py            ← Recibe la peticion
   │
   │  Llama al orquestador
   ▼
ORQUESTADOR (Python)                      ← Decide que hacer
   │
   │  Llama al Agente de Solicitudes
   ▼
AGENTE SOLICITUDES (Python)               ← Analiza el mensaje
   │
   │  Usa sus "tools" (herramientas)
   ▼
VACACIONES API CLIENT (Python)            ← Hace una llamada HTTP
   │
   │  POST http://localhost:5000/api/vacaciones/solicitar
   │  Body: {"empleadoId": 123, "fechaInicio": "2026-09-01", "fechaFin": "2026-09-15"}
   ▼
SISTEMA MVC (C#) - API REST               ← Recibe la peticion HTTP
   │
   │  Crea la solicitud en la BD, responde con el estado
   │  Respuesta: {"solicitudId": 1001, "estado": "aprobada", ...}
   ▼
VOLVEMOS HACIA ATRAS ─────────────────────────────────────────────────────┐
   │                                                                       │
   │  El Agente de Solicitudes recibe la respuesta y la devuelve           │
   ▼                                                                       │
ORQUESTADOR                                                               │
   │                                                                       │
   │  Formula el texto de respuesta al empleado                           │
   ▼                                                                       │
FASTAPI                                                                   │
   │                                                                       │
   │  Devuelve: {"respuesta": "Solicitud #1001 creada con estado aprobada"}│
   ▼                                                                       │
SISTEMA MVC (C#)                                                          │
   │                                                                       │
   │  Recibe la respuesta JSON y la muestra en el chat del empleado       │
   ▼                                                                       │
EMPLEADO ve el resultado                                                  │
```

### La respuesta viaja por el mismo camino por donde llego

Esto es clave: **la respuesta viaja por HTTP de regreso por la misma conexion**.

El sistema MVC hace una peticion HTTP y **espera la respuesta** (como cuando abres
una pagina web y esperas que cargue). FastAPI recibe esa peticion, hace todo el
trabajo (hablar con el MVC para crear o consultar la solicitud), y cuando termina
**devuelve un JSON** como respuesta de esa misma peticion HTTP.

Es como una llamada telefonica:
- MVC llama a Python (peticion)
- Python hace su trabajo
- Python responde a MVC (respuesta)
- MVC muestra la respuesta al empleado

**No hay WebSockets, no hay colas, no hay nada raro.** Es una peticion HTTP normal
y corriente. El sistema MVC solo tiene que hacer:

```
POST http://localhost:8001/chat
{
  "mensaje": "Quiero vacaciones del 1 al 15 de septiembre",
  "empleadoId": 123
}
```

Y recibir como respuesta:
```
{
  "respuesta": "Tu solicitud #1001 fue creada con estado aprobada."
}
```

---

## Cada archivo que hace?

### `app/main.py` - El mostrador de recepcion

Este archivo es el punto de entrada. Es como el mostrador de recepcion de un hotel:
si alguien entra, aqui lo atienden.

- Expone el endpoint `POST /chat` que es por donde llegan todos los mensajes.
- Expone un endpoint `GET /health` para verificar que el servicio esta vivo.
- Configura CORS (permite que el sistema MVC llame a este servicio desde otro dominio).
- Crea una instancia del orquestador y le pasa los mensajes.

**Que recibe:**
```json
{"mensaje": "Quiero vacaciones", "empleadoId": 123}
```

**Que devuelve:**
```json
{"respuesta": "Tu solicitud fue creada..."}
```

---

### `app/config.py` - El archivo de configuracion

Lee las variables de entorno (el archivo `.env`) y las pone disponibles para todo el
proyecto. Es como una caja de herramientas donde estan todas las contrasenas y URLs.

Que carga:
- `BASE_URL_VACACIONES_API` - URL del sistema MVC (ej: http://localhost:5000)
- `MODEL_PROVIDER` / `MODEL_API_KEY` / `MODEL_NAME` - Para el modelo de IA (por definir)
- `WEATHER_API_KEY` / `FLIGHTS_API_KEY` / `HOTELS_API_KEY` - APIs externas (por definir)
- `HOST` / `PORT` - Donde corre el servidor
- `CORS_ORIGINS` - De que origen se permiten peticiones
- `USE_MOCK_VACACIONES_API` - Si es `true`, usa respuestas simuladas en vez de hablar con el MVC real

---

### `app/models/chat.py` - Los formularios del chat

Define como se ven los datos que entran y salen del chat. Son como formularios vacios
que se llenan con informacion:

- `ChatRequest` - Lo que el empleado envia: un `mensaje` (texto) y un `empleadoId` (numero).
- `ChatResponse` - Lo que el servicio responde: un `respuesta` (texto).

---

### `app/orchestrator/orchestrator.py` - El jefe de piso

Este es el cerebro que decide que hacer. Recibe el mensaje del empleado y coordina
al agente de solicitudes:

1. **Primero** llama al Agente de Solicitudes para crear o consultar la vacacion.
2. **Despues** toma el resultado (id y estado de la solicitud) y arma el texto de
   respuesta para el empleado.

**Futuro**: Cuando elijamos un framework de agentes (smolagents, langchain, crewai),
este archivo sera el que se reemplace o adapte para usar el orquestador nativo
de ese framework.

---

### `app/agents/base_agent.py` - El contrato

Es una plantilla vacia que dice "todo agente debe tener un metodo `run()`". No hace
nada por si mismo, solo establece la regla.

**Para que sirve?** Para que si manana cambiamos de framework de IA, solo tengamos
que cambiar la implementacion interna de cada agente, pero la forma en que el
orquestador los llama (`agente.run(datos)`) no cambie.

Es como un contrato que dicen: "si quieres ser agente en este proyecto, tienes que
saber hacer `run(input)` y devolver un `output`".

---

### `app/agents/solicitudes/` - Agente 1: Gestor de vacaciones

Tres archivos trabajan juntos aqui:

#### `agent.py` - El cerebro del agente

Define la clase `AgenteSolicitudes`. Cuando recibe un mensaje:
1. Analiza que quiere hacer el empleado (crear vacacion o consultar estado).
2. Llama a las tools correspondientes.
3. Devuelve el resultado.

**Actualmente** tiene logica basica que detecta palabras clave ("solicitar", "vacaciones").
**En el futuro**, un modelo de IA interpretara el mensaje y extraera fechas, destino, etc.

#### `tools.py` - Las herramientas

Son funciones normales que hacen el trabajo sucio:

- `crear_solicitud_vacaciones(empleado_id, fecha_inicio, fecha_fin)` -> llama al `VacacionesAPIClient` para crear la solicitud via HTTP.
- `consultar_estado_solicitud(solicitud_id)` -> llama al `VacacionesAPIClient` para consultar el estado via HTTP.

**Nunca** hablan directamente con la base de datos. Siempre pasan por el cliente HTTP.

#### `schemas.py` - Los formularios

Define que datos entra y sale de este agente:

- `SolicitudInput` -> `empleado_id` (int) y `mensaje` (str)
- `SolicitudCrearOutput` -> `solicitud_id`, `estado`, `fecha_inicio`, `fecha_fin`, `mensaje`
- `SolicitudConsultarOutput` -> `solicitud_id`, `estado`, `mensaje`

---

> **Agente de Viaje**: fuera de este repositorio. La investigacion de destinos
> (vuelos, hoteles, clima, actividades) la desarrolla otro equipo.

---

### `app/clients/vacaciones_api_client.py` - El traductor HTTP

Es la **unico lugar** en todo el proyecto que habla con el sistema MVC por HTTP.
Ningun otro archivo llama directamente al MVC.

Tiene dos metodos:
- `crear_solicitud()` -> hace `POST` a `/api/vacaciones/solicitar`
- `consultar_estado()` -> hace `GET` a `/api/vacaciones/{id}/estado`

Maneja errores de red y de HTTP para que el servicio no se caiga si el MVC no responde.

**Tiene un interruptor**: si `USE_MOCK_VACACIONES_API=true` en `.env`, en vez de
llamar al MVC real, usa respuestas simuladas (mocks) para poder desarrollar sin
necesitar el otro repositorio.

---

### `app/utils/logger.py` - El periodista

Configura el sistema de logs (registros). Cuando algo pasa (un error, una peticion,
un resultado), escribe un mensaje en la consola con fecha y hora.

Sirve para:
- **Debuggear**: "que paso exactamente en este request?"
- **Monitorear**: "hay errores repetidos?"
- **Auditar**: "que requests llegaron y que respuestas se dieron?"

---

### `tests/` - Las pruebas

Archivos para verificar que todo funciona:

- `test_orchestrator.py` -> prueba que el orquestador invoca al agente de solicitudes
  y arma la respuesta con el estado de la solicitud.
- `test_agente_solicitudes.py` -> prueba que el agente crea y consulta solicitudes.

---

### `.env.example` - La plantilla de configuracion

Es un ejemplo de como debe verse el archivo `.env`. Se copia como `.env` y se llenan
los valores reales. **Nunca** se sube el `.env` real a Git (por seguridad).

---

### `requirements.txt` - La lista de compras

Las librerias de Python que necesita el proyecto:

```
fastapi         - El framework web
uvicorn         - El servidor que ejecuta FastAPI
pydantic        - Validacion y estructura de datos
httpx           - Cliente HTTP para hablar con el MVC
python-dotenv   - Leer el archivo .env
pytest          - Para correr las pruebas
```

**Nota**: No hay ningun framework de agentes (smolagents, langchain, etc.) porque
aun no lo hemos decidido. Se instalara cuando se elija.

---

### `.gitignore` - Lo que Git ignora

Le dice a Git que no suba archivos que no deben ir al repositorio:
- `.env` (contrasenas)
- `venv/` (entorno virtual)
- `__pycache__/` (cache de Python)
- `.pytest_cache/` (cache de pruebas)

---

## Flujo completo: de principio a fin

Para que quede 100% claro, aqui esta lo que pasa de principio a fin cuando un
empleado escribe "Quiero vacaciones del 1 al 15 de septiembre a Cancun":

```
1. El empleado escribe en el chat del sistema MVC (la pantalla en C#).

2. El sistema MVC toma ese mensaje y hace un POST a este servicio Python:
   POST http://localhost:8001/chat
   Body: {"mensaje": "Quiero vacaciones del 1 al 15 de septiembre a Cancun", "empleadoId": 123}

3. app/main.py recibe la peticion y se la pasa al orquestador.

4. El orquestador la pasa al Agente de Solicitudes.

5. El Agente de Solicitudes (con ayuda de un modelo de IA en el futuro) entiende
   que el empleado quiere CREAR una solicitud, y extrae las fechas.

6. El agente usa su tool "crear_solicitud_vacaciones" que llama al VacacionesAPIClient.

7. El VacacionesAPIClient hace un POST a la API del sistema MVC:
   POST http://localhost:5000/api/vacaciones/solicitar
   Body: {"empleadoId": 123, "fechaInicio": "2026-09-01", "fechaFin": "2026-09-15"}

8. El sistema MVC crea la solicitud en su base de datos y responde:
   {"solicitudId": 1001, "estado": "aprobada", ...}

9. Esa respuesta viaja de regreso: MVC → VacacionesAPIClient → Agente de Solicitudes → Orquestador.

10. El orquestador arma el texto de respuesta:
    "Tu solicitud #1001 fue creada con estado aprobada, del 1 al 15 de septiembre."

11. Esa respuesta viaja de regreso por HTTP: Python → MVC.

12. El sistema MVC muestra ese texto en el chat del empleado.

13. El empleado ve su respuesta.
```

**Todo viaja por HTTP**. No hay nada magico. Es una peticion que va y una respuesta
que viene.

---

## Que hace falta aun?

- [x] Implementar el codigo real en cada archivo (agente de solicitudes, orquestador, API)
- [x] Elegir e integrar un framework de agentes de IA (smolagents)
- [x] Conectar el modelo de IA para interpretar mensajes del empleado
- [ ] Conectar con el MVC real (desactivar mocks)
- [ ] Hacer que el MVC llame a `POST /chat` y muestre la respuesta en el chat
- [ ] (Otro equipo) Agente de viaje: APIs reales de clima, vuelos y hoteles
