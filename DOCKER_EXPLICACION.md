# Qué se hizo: Dockerizar Oro-Agente

Este documento explica, con analogías simples, qué se agregó al proyecto para poder correrlo con Docker.

## 1. ¿Qué es una imagen y qué es un contenedor?

Piensa en una **imagen** como el molde de gelatina: define la forma exacta que va a tener el resultado (qué versión de Python, qué librerías, qué código). No se puede "usar" directamente, solo sirve para producir algo a partir de ella.

Un **contenedor** es la gelatina ya hecha, sacada del molde: una copia en ejecución de esa imagen, corriendo de verdad, con su propio proceso, su propia memoria, aislado de lo que pasa en tu computadora. Puedes crear varios contenedores desde el mismo molde (imagen), y cada uno vive por separado.

## 2. El `Dockerfile` — la receta

El archivo [Dockerfile](Dockerfile) es la **receta de cocina** que le dice a Docker paso a paso cómo construir el molde (la imagen):

1. Parte de una base ya lista (`python:3.11-slim` — como comprar una masa pre-hecha en vez de hacerla desde cero).
2. Copia `requirements.txt` e instala las dependencias (como comprar los ingredientes antes de empezar a cocinar).
3. Copia el código de `app/` (los ingredientes específicos de esta receta).
4. Define el comando final que arranca el servidor (`uvicorn app.main:app ...`) — es como escribir "hornea a 180° durante 40 minutos" al final de la receta: eso es lo que se ejecuta cuando alguien "usa" la imagen.

## 3. `docker-compose.yml` — el director de orquesta

Con una sola imagen alcanzaría con `docker build` y `docker run`, pero eso obliga a escribir a mano el puerto, las variables de entorno y los volúmenes cada vez. [docker-compose.yml](docker-compose.yml) es el **director de orquesta**: en un solo archivo describe qué contenedor(es) hay que levantar y con qué configuración, y con un solo comando (`docker compose up`) los pone a todos a tocar juntos.

Hoy solo hay un "músico" en la orquesta (el servicio `oro-agente`), porque —como vimos al revisar el proyecto— el orquestador y los dos agentes (Solicitudes y Viajes) no son servicios separados: son clases de Python que corren dentro de un mismo proceso. Es como tener una sola persona tocando varios instrumentos a la vez en vez de una banda completa — no hace falta un director complejo, con uno solo que la presente al escenario (el contenedor) alcanza.

> Si en el futuro se separan los agentes en servicios independientes (cada uno con su propio servidor), ahí sí el `docker-compose.yml` crecería para tener un servicio por agente — como pasar de un solista a una banda con varios músicos, cada uno con su propio "instrumento" (contenedor) pero tocando la misma canción.

## 4. El volumen de `data/` — la libreta que vive afuera de la caja

Cuando un contenedor se borra o se recrea, todo lo que escribió *dentro* de sí mismo desaparece con él — como tirar la caja de gelatina y perder la gelatina también.

El proyecto guarda el contexto de las conversaciones en `data/viajes_store.json`. Para que esa información **no se pierda** cada vez que el contenedor se reinicia o se reconstruye, el `docker-compose.yml` monta esa carpeta como un **volumen**:

```yaml
volumes:
  - ./data:/app/data
```

Es como tener una libreta que vive **fuera** de la caja (en tu computadora), pero que el contenedor puede abrir y escribir mientras trabaja. Si tiras la caja (el contenedor) y armas una nueva, la libreta sigue intacta.

## 5. `.env` / `env_file` — la llave que no va horneada en la receta

El proyecto necesita datos sensibles o específicos del entorno: la API key del modelo de IA, la URL del sistema de vacaciones, etc. Esos datos **no se escriben en la receta** (el `Dockerfile` ni el código), porque si lo hicieras quedarían grabados dentro de la imagen para siempre y cualquiera que la tenga podría verlos.

En cambio, se le "entregan" al contenedor en el momento de arrancarlo, como pasarle una llave por debajo de la puerta en vez de dejarla pegada en la cerradura. Eso es lo que hace `env_file: .env` en el `docker-compose.yml`: lee tu archivo `.env` local y se lo inyecta al contenedor como variables de entorno, sin que ese archivo jamás entre a la imagen (por eso también está excluido en `.dockerignore`).

## 6. `.dockerignore` — qué no metemos en la maleta

Así como el `.gitignore` le dice a Git qué no subir, el [.dockerignore](.dockerignore) le dice a Docker qué **no copiar** dentro de la imagen al construirla: el entorno virtual (`venv/`), el archivo `.env` (secretos), los datos (`data/`) y otros archivos que no hacen falta para correr la app. Esto mantiene la imagen liviana y evita filtrar información sensible por accidente.

## Cómo correrlo

```bash
docker compose build   # arma la imagen (la "receta" se cocina una vez)
docker compose up      # levanta el contenedor usando esa imagen
```

## Cómo probarlo

1. Revisar que responde: `curl http://localhost:8001/health` → debería devolver `{"status": "ok"}`.
2. Probar el chat:
   ```bash
   curl -X POST http://localhost:8001/chat \
     -H "Content-Type: application/json" \
     -d '{"empleado_id": "123", "mensaje": "quiero pedir vacaciones"}'
   ```
3. Verificar que `data/viajes_store.json` (en tu carpeta local, no dentro del contenedor) se actualiza después de interactuar con el chat — eso confirma que el volumen está funcionando.

## Punto importante: `BASE_URL_VACACIONES_API`

El `.env` de ejemplo apunta a `http://localhost:5000` para hablar con el sistema externo de vacaciones (la app C# MVC). **Dentro de un contenedor, `localhost` se refiere al propio contenedor, no a tu computadora.** Si esa API corre en tu máquina fuera de Docker, tienes que cambiar esa URL en tu `.env` a `http://host.docker.internal:5000` para que el contenedor pueda encontrarla — es como si el contenedor, al decir "localhost", se señalara a sí mismo en vez de señalar afuera de la caja.

Si en algún momento esa API también se dockeriza y se agrega al mismo `docker-compose.yml`, en vez de `host.docker.internal` se usaría el nombre del servicio (por ejemplo `http://vacaciones-api:5000`), porque Docker Compose crea una red interna donde los contenedores se pueden llamar por nombre, como si se llamaran por apodo en vez de por dirección.
