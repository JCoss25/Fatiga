# Despliegue en AWS — Test de Alertamiento por Fatiga Laboral

Esta guía lleva la aplicación (ya probada en local) a AWS, dejándola corriendo
"todo desde allá" y conectada a tu RDS MySQL `kogn1v1s`.

---

## 0. Datos de tu entorno

| Dato | Valor |
|---|---|
| Cuenta AWS | `459133916957` |
| Región de la BD | `mx-central-1` (México) |
| RDS endpoint | `kogn1v1s-db.cl2ekg8o2dj5.mx-central-1.rds.amazonaws.com` |
| Base de datos | `kogn1v1s` (MySQL 8.0.46) |

> **Importante:** despliega la aplicación en la **misma región** (`mx-central-1`)
> que la base de datos para tener baja latencia y tráfico privado.

---

## 1. Arquitectura recomendada

```
                         Internet (HTTPS)
                                │
                        ┌───────▼────────┐
                        │   AWS App Runner │  ← corre el contenedor
                        │  (contenedor)    │     (2 vCPU / 4 GB)
                        └───────┬────────┘
                                │ VPC Connector (red privada)
                        ┌───────▼────────┐
                        │  Amazon RDS MySQL│
                        │   kogn1v1s       │
                        └──────────────────┘
        Credenciales → AWS Secrets Manager
```

- **AWS App Runner**: forma más simple de "subir un contenedor y olvidarse".
  Da HTTPS automático, URL pública y escalado. Alternativas al final.
- **VPC Connector**: permite que App Runner hable con RDS por red privada
  (así cerramos el puerto 3306 a Internet).
- **Secrets Manager**: guarda la contraseña de la BD fuera del código.

---

## 2. Prerrequisitos

En tu máquina (o en AWS CloudShell):

```bash
# AWS CLI v2 configurado con la cuenta 459133916957
aws configure        # Access Key, Secret Key, region: mx-central-1

# Docker (solo si vas a construir la imagen en tu equipo)
docker --version
```

> ¿No tienes Docker local? Puedes construir la imagen con **AWS CodeBuild**
> o subir el código a un repo y usar la sección "alternativa CodeBuild".

---

## 3. Paso 1 — Guardar credenciales en Secrets Manager

Crea un secreto con el usuario de aplicación (`kogn_rw`):

```bash
aws secretsmanager create-secret \
  --name kogn1v1s/fatiga/db \
  --region mx-central-1 \
  --secret-string '{
    "username":"kogn_rw",
    "password":"PON_AQUI_LA_CONTRASENA",
    "host":"kogn1v1s-db.cl2ekg8o2dj5.mx-central-1.rds.amazonaws.com",
    "port":"3306",
    "dbname":"kogn1v1s"
  }'
```

Anota el `ARN` que devuelve. Más adelante se usa como `DB_SECRET_ARN`.

> El código ya sabe leer este secreto: si defines `DB_SECRET_ARN`, la app toma
> host/usuario/contraseña de Secrets Manager en lugar del `.env`.

---

## 4. Paso 2 — Subir la imagen a Amazon ECR

```bash
# 4.1 Crear el repositorio
aws ecr create-repository --repository-name kogn1v1s-fatiga --region mx-central-1

# 4.2 Autenticar Docker contra ECR
aws ecr get-login-password --region mx-central-1 \
  | docker login --username AWS --password-stdin 459133916957.dkr.ecr.mx-central-1.amazonaws.com

# 4.3 Construir (desde la raíz del proyecto) y etiquetar
docker build -f deploy/Dockerfile -t kogn1v1s-fatiga .
docker tag kogn1v1s-fatiga:latest \
  459133916957.dkr.ecr.mx-central-1.amazonaws.com/kogn1v1s-fatiga:latest

# 4.4 Subir
docker push 459133916957.dkr.ecr.mx-central-1.amazonaws.com/kogn1v1s-fatiga:latest
```

---

## 5. Paso 3 — VPC Connector (para llegar a RDS por red privada)

1. Consola AWS → **App Runner** → **VPC connectors** → *Create*.
2. Nombre: `fatiga-vpc-connector`.
3. VPC: la misma donde vive RDS. Subnets: al menos 2 (privadas si existen).
4. Security groups: crea uno nuevo, p. ej. `sg-fatiga-app`.
5. Crear.

Después, en el **Security Group de RDS** (`sg-08675e63aba31e26d`) agrega una
regla de entrada:

| Tipo | Puerto | Origen |
|---|---|---|
| MySQL/Aurora | 3306 | `sg-fatiga-app` |

> Así la BD **solo** acepta conexiones de la app. Luego **elimina** la regla
> actual que abre el 3306 a `0.0.0.0/0` (recomendado).

---

## 6. Paso 4 — Crear el servicio App Runner

Consola → **App Runner** → *Create service* → **Container registry (ECR)**:

- Image: `459133916957.dkr.ecr.mx-central-1.amazonaws.com/kogn1v1s-fatiga:latest`
- Deployment trigger: *Manual* (o automático al hacer push).
- **Port**: `8000`
- **Networking**: *Private/outbound* → selecciona el `fatiga-vpc-connector`.

**Variables de entorno** (Configuration → Environment variables):

| Variable | Valor |
|---|---|
| `DB_SECRET_ARN` | `arn:aws:secretsmanager:mx-central-1:459133916957:secret:kogn1v1s/fatiga/db-XXXXXX` |
| `AWS_REGION` | `mx-central-1` |
| `DB_NAME` | `kogn1v1s` |
| `DB_SSL` | `required` |
| `ADMIN_PASSWORD` | *una clave fuerte para el panel* |
| `SOLICITANTE_PASSWORD` | `Soli.2026` (o una clave fuerte) |
| `APROBADOR_PASSWORD` | `Apro.2026` |
| `SOLICITANTE_EMAIL` | cuenta Gmail del solicitante |
| `APROBADOR_EMAIL` | cuenta Gmail del aprobador |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_TLS` | `starttls` |
| `SMTP_USER` | cuenta Gmail exclusiva para notificaciones |
| `SMTP_PASSWORD` | contraseña de aplicación de 16 caracteres |
| `SMTP_FROM` | la misma cuenta de notificaciones |
| `SMTP_FROM_NAME` | `Kogn1v1s - Comercial` |
| `CORREO_SIMULADO` | `0` |
| `APP_URL` | `https://<tu-servicio>.mx-central-1.awsapprunner.com` |

> No definas `COT_DATABASE_URL` en AWS: el módulo Comercial usa la misma base
> MySQL/RDS (`kogn1v1s`) y crea solo tablas `cot_*`.
>
> Puedes poner las claves y la contraseña de Gmail también en Secrets Manager.

**Health check**: path `/api/health`.

Al terminar, App Runner te da una URL tipo
`https://xxxxx.mx-central-1.awsapprunner.com` — esa es la dirección pública
(con HTTPS) de la aplicación. Puedes conectar tu propio dominio después
(Configuration → Custom domains).

---

## 7. Crear las tablas (una sola vez)

Las tablas se crean ejecutando las migraciones. Opciones:

**a) Ya están creadas** (se hicieron durante la prueba en local — `fatiga_preguntas`,
`fatiga_tests`, `fatiga_respuestas`). No necesitas hacer nada más.

**b) Recrearlas/actualizarlas** desde una máquina con acceso a RDS:

```bash
python db/migrate.py              # fatiga / SST
python db/migrate_comercial.py    # tablas cot_* del módulo Comercial
```

(Usa las credenciales de administrador del `.env`. En producción se recomienda
un usuario con permiso solo `CREATE`/`ALTER` para esta tarea puntual.)

> En AWS **no** definas `COT_DATABASE_URL`: con eso el módulo Comercial usa la
> misma base `kogn1v1s` y crea las tablas `cot_*`. Para vaciar solo las
> solicitudes: `python db/reset_comercial.py`.

---

## 8. Alternativas de hosting (comparación)

| Opción | Complejidad | Costo aprox./mes | Cuándo usarla |
|---|---|---|---|
| **App Runner** (recomendada) | Baja | ~$15–40 USD | Quieres HTTPS y escalado sin administrar servidores |
| **ECS Fargate** | Media | ~$20–50 USD | Ya usas ECS o necesitas más control |
| **EC2 (t3.small)** | Media | ~$17 USD + administración | Quieres la opción más barata y controlas el SO |
| **Lightsail** | Muy baja | ~$10–20 USD | Alternativa simple fuera del ecosistema VPC |

**RDS** ya lo tienes (el costo de la BD es aparte).

### Alternativa rápida: un solo EC2 (t3.small)

```bash
# En la instancia EC2 (Amazon Linux 2023), con Docker instalado:
sudo dnf install -y docker git
sudo systemctl enable --now docker
git clone <tu-repo> app-fatiga && cd app-fatiga
sudo docker build -f deploy/Dockerfile -t kogn1v1s-fatiga .
sudo docker run -d --restart unless-stopped -p 80:8000 \
  --env-file .env kogn1v1s-fatiga
```
Abre el puerto 80 en el Security Group del EC2 y listo.

---

## 9. Checklist de seguridad (importante)

Este proyecto recibió credenciales en texto plano; conviene atender esto:

- [ ] **Rotar** las contraseñas de `kogn_ro`, `kogn_rw` y `kognadmin`.
- [ ] Guardar credenciales solo en **Secrets Manager** (no en `.env` de producción).
- [ ] **Cerrar el puerto 3306** de RDS a Internet; permitir solo el SG de la app.
- [ ] Usar `DB_SSL=required` en producción.
- [ ] Cambiar `ADMIN_PASSWORD` del panel por una clave fuerte.
- [ ] Considerar **AWS WAF** o autenticación (Cognito) para el panel si estará expuesto.
- [ ] Activar **backups automáticos** y *deletion protection* en RDS.
- [ ] Poner la app y la BD en **subredes privadas** cuando sea posible.

---

## 10. Actualizaciones futuras

Para publicar cambios:

```bash
docker build -f deploy/Dockerfile -t kogn1v1s-fatiga .
docker tag kogn1v1s-fatiga:latest 459133916957.dkr.ecr.mx-central-1.amazonaws.com/kogn1v1s-fatiga:latest
docker push 459133916957.dkr.ecr.mx-central-1.amazonaws.com/kogn1v1s-fatiga:latest
# App Runner → Deploy (o activa el trigger automático)
```
