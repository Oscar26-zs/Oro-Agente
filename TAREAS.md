# TAREAS.md — Plan de construcción del proyecto

## Estado actual

Todas las fases 0–7 están implementadas y verificadas con pruebas
automatizadas (`pytest`, 13/13 pasan) y con llamadas reales a la app FastAPI
vía `TestClient` (sin necesidad de un servidor corriendo). Lo que falta
requiere credenciales/servicios que solo tú puedes proveer: un `HF_TOKEN`
real de HuggingFace, y el sistema C# MVC exponiendo sus endpoints
`/api/vacaciones/...` (ver el `TAREAS.md` de ese otro proyecto).

---

## Fase 0: Configuración del entorno

- [x] Crear entorno virtual (`python -m venv venv`)
- [x] Completar `requirements.txt` con: `smolagents[toolkit]`, `fastapi`,
      `uvicorn[standard]`, `requests`, `python-dotenv`, `pytest`
- [x] Instalar dependencias (`pip install -r requirements.txt`) — instalación
      verificada sin errores
- [x] Definir y documentar qué modelo LLM se va a usar: **HuggingFace
      Inference API** (`smolagents.InferenceClientModel`), documentado en
      `README.md` y `app/config.py`
- [x] Completar `.env.example` (`HF_TOKEN`, `HF_MODEL_ID`,
      `VACACIONES_API_URL`, `CORS_ALLOWED_ORIGIN`, `LOG_LEVEL`), sin valores reales
- [x] Completar `.gitignore` (`venv/`, `.env`, `__pycache__/`, `*.pyc`, etc.)
- [x] Confirmar que la estructura de carpetas ya existente cubre lo
      necesario; se respetó, no se creó estructura paralela

## Fase 1: Agente 2 aislado (investigador de viaje)

- [x] Implementar `app/agents/viaje/agent.py` con un agente mínimo usando
      `WebSearchTool`
- [x] Crear script de prueba manual `probar_agente2.py`
- [ ] **Pendiente de tu parte**: ejecutar `probar_agente2.py` con un
      `HF_TOKEN` real — no se pudo correr en este entorno porque requiere una
      API key de HuggingFace que solo tú puedes proveer

## Fase 2: Formato de salida del Agente 2

- [x] Definir y forzar en el prompt del agente (`instructions` en
      `app/agents/viaje/agent.py`) el formato JSON de salida
- [x] Implementar `app/agents/viaje/schemas.py`
- [x] Crear función de parseo robusta `parsear_json_respuesta` en
      `app/agents/viaje/tools.py` — probada con JSON limpio, JSON con texto
      alrededor, y texto sin JSON (`tests/test_agente_viaje.py`, todas pasan)

## Fase 3: Mejora de calidad del Agente 2

- [x] Ajustar el prompt del agente para evitar alucinaciones (instrucción
      explícita de no inventar datos no encontrados)
- [x] Agregar `ClimaTool` (wttr.in) en `app/agents/viaje/tools.py`, probada
      con mocks de red (éxito y fallo de conexión)
- [ ] **Pendiente de tu parte**: probar con 2-3 destinos reales — requiere
      `HF_TOKEN` real, no ejecutable en este entorno

## Fase 4: Empaquetar Agente 2

- [x] Crear función reutilizable `buscar_info_viaje(destino, fecha_inicio, fecha_fin)`
      en `app/agents/viaje/agent.py`
- [ ] **Pendiente de tu parte**: probarla de forma aislada con llamadas
      reales al modelo (requiere `HF_TOKEN`)
- [x] Completar `tests/test_agente_viaje.py` — 5 pruebas, todas pasan

## Fase 5: Agente 1 (gestor de solicitudes)

- [x] Implementar `app/clients/vacaciones_api_client.py`
- [x] Implementar `app/agents/solicitudes/tools.py` con dos tools `@tool`
      (no clases `Tool`): `crear_solicitud_vacaciones(empleado_id, destino,
      fecha_inicio, fecha_fin)` → `POST /api/vacaciones/solicitar`, y
      `consultar_estado_solicitud(solicitud_id)` → `GET /api/vacaciones/{id}/estado`
- [x] Implementar `app/agents/solicitudes/schemas.py`
- [x] Implementar `app/agents/solicitudes/agent.py`, con instrucciones que
      encajan explícitamente el comportamiento por estado: `pendiente` → informa
      y no hace nada más; `aprobada` → informa que está lista para pasar al
      **agente_viaje** (que ya existe en este proyecto, `app/agents/viaje/agent.py`
      — no hizo falta placeholder/TODO); `rechazada` → informa el rechazo;
      error de conexión → mensaje claro sin tecnicismos
- [x] Manejar errores de conexión: `VacacionesApiError` distingue
      connection error / timeout / 404 / HTTP error, y las tools devuelven un
      JSON de error legible en vez de dejar propagar la excepción
- [x] Completar `tests/test_agente_solicitudes.py` — 6 pruebas, todas pasan
      (payload correcto, propagación de error de conexión, tools devuelven el
      JSON de la API o un JSON de error legible)
- [x] Crear `probar_agente1.py`: prueba `crear_solicitud_vacaciones` y
      `consultar_estado_solicitud` contra `VACACIONES_API_URL` real,
      **sin necesitar `HF_TOKEN`** (llama las tools directamente, no pasa por
      el LLM). Probado en dos condiciones: (a) con el sistema C# MVC apagado
      → falla de forma clara, sin traceback, `exit code 1`; (b) con el
      sistema C# MVC real corriendo (LocalDB) → crea la solicitud y consulta
      su estado de verdad, con Guid + header `X-Api-Key` funcionando
      correctamente extremo a extremo.

> **Corrección post-integración**: cuando se implementó la API real del lado
> C# (`Sali_Vacaciones/TAREAS.md`), dos cosas cambiaron respecto a lo que
> este proyecto ya asumía: `empleadoId`/`solicitudId` son `Guid` (string), no
> `int`, y el endpoint exige el header `X-Api-Key`. Se actualizó
> `vacaciones_api_client.py` (tipos a `str`, envío de `X-Api-Key` vía
> `VACACIONES_API_KEY`, mensajes específicos para 401/503), `tools.py`,
> `schemas.py`, `models/chat.py` (con validación de formato Guid), y el
> puerto por defecto de `VACACIONES_API_URL` a `5051` (el real, no `5000`).
> Verificado en vivo contra el servidor C# real: creación de solicitud,
> consulta de estado, y un 409 real por traslape de fechas — no solo mocks.

> **Cambio de diseño respecto a la versión anterior de este archivo**: las
> tools ahora son funciones `@tool` con las firmas exactas pedidas
> (`crear_solicitud_vacaciones(empleado_id, destino, fecha_inicio, fecha_fin)`,
> `consultar_estado_solicitud(solicitud_id)`) en vez de subclases de `Tool`
> con el `empleado_id` fijado por closure. Efecto secundario: se eliminó el
> caché en memoria `_ULTIMA_SOLICITUD_POR_EMPLEADO` que permitía preguntar
> "¿ya se aprobó?" sin repetir el ID — ahora `consultar_estado_solicitud`
> requiere el `solicitud_id` explícito, tal como se especificó. El agente
> puede reutilizar el ID dentro de una misma llamada (lo ve en su propio
> historial de pasos), pero recordarlo entre llamadas HTTP `/chat`
> separadas queda pendiente si se necesita — no estaba pedido en este
> alcance.

## Fase 6: Orquestador

- [x] Definir en `app/agents/base_agent.py` la interfaz común (`Protocol`
      `AgenteEjecutable`)
- [x] Implementar `app/orchestrator/orchestrator.py`: `CodeAgent` orquestador
      con `managed_agents=[agente_solicitudes, agente_viaje]`
- [x] Definir la lógica/prompt: instrucción explícita de solo delegar a
      `agente_viaje` cuando el estado sea `aprobada`, más un helper puro
      `debe_investigar_viaje(estado)` que documenta y prueba esa regla
      independientemente del LLM
- [x] Completar `tests/test_orchestrator.py` — 2 pruebas, todas pasan (regla
      de negocio + construcción correcta de la tarea que recibe el orquestador)

## Fase 7: Servicio FastAPI

- [x] Implementar `app/config.py`
- [x] Implementar `app/utils/logger.py`
- [x] Implementar `app/models/chat.py`
- [x] Implementar `app/main.py` con `POST /chat`
- [x] Validar `empleadoId` presente y entero válido — verificado con
      `TestClient`: falta el campo → 422, tipo incorrecto → 422
- [x] Configurar CORS (`CORS_ALLOWED_ORIGIN`)
- [x] Verificado con `TestClient` (equivalente in-process a curl/Postman):
      validación de entrada, y que si el modelo LLM falla (ej. sin
      `HF_TOKEN`) el endpoint responde `200` con un mensaje amigable en vez
      de reventar — no se probó una conversación real de punta a punta
      porque eso requiere `HF_TOKEN` real
- [ ] **Pendiente de tu parte**: probar `uvicorn app.main:app --port 8001`
      con curl/Postman y un `HF_TOKEN` real, para ver una respuesta real del
      LLM

## Fase 8: Pruebas de integración

- [x] Documentado en `README.md` cómo levantar el servicio (venv, instalar
      dependencias, `.env`, comando `uvicorn`, puerto)
- [ ] Pruebas end-to-end contra el sistema C# MVC real (`localhost:5000`)
      cuando esté disponible — no ejecutable todavía: el proyecto C# MVC no
      expone aún los endpoints `/api/vacaciones/...` (ver su propio
      `TAREAS.md`), y esta prueba además requiere un `HF_TOKEN` real
