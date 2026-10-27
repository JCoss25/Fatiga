-- ============================================================================
--  Modulo de Cotizacion de danos (Orden de Reparacion TOT)
--  Base: kogn1v1s (Amazon RDS MySQL 8.0)
--
--  Script IDEMPOTENTE. Solo crea tablas con prefijo "cot_"; no modifica
--  las tablas existentes (usuarios, fatiga_*, sst_*).
-- ============================================================================

CREATE TABLE IF NOT EXISTS cot_solicitudes (
  id_solicitud          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  folio                 VARCHAR(30)  NOT NULL,
  serie                 VARCHAR(10)  NOT NULL DEFAULT 'LC',
  estatus               ENUM('BORRADOR','PENDIENTE','APROBADA','COMPRADO','CERRADO','RECHAZADA','CANCELADA')
                        NOT NULL DEFAULT 'BORRADOR',
  fecha_solicitud       DATE NOT NULL,
  solicitante_cliente   VARCHAR(160) NOT NULL DEFAULT '',
  vin                   VARCHAR(30)  NOT NULL DEFAULT '',
  ubicacion             VARCHAR(120) NOT NULL DEFAULT '',
  tipo_servicio         VARCHAR(120) NOT NULL DEFAULT '',
  no_parte              VARCHAR(120) NOT NULL DEFAULT '',
  descripcion           TEXT NULL,
  cantidad              DECIMAL(12,2) NOT NULL DEFAULT 1,
  alcance_servicio      TEXT NULL,
  proveedor_sugerido    VARCHAR(160) NOT NULL DEFAULT '',
  precio                DECIMAL(14,2) NOT NULL DEFAULT 0,
  moneda                VARCHAR(3)   NOT NULL DEFAULT 'MXN',
  total                 DECIMAL(16,2) NOT NULL DEFAULT 0,
  fecha_requerida       DATE NULL,
  observaciones         TEXT NULL,
  datos                 JSON NULL,
  creado_por_rol        VARCHAR(20)  NOT NULL DEFAULT 'solicitante',
  creado_por_nombre     VARCHAR(120) NOT NULL DEFAULT '',
  creado_por_email      VARCHAR(160) NULL,
  aprobador_nombre      VARCHAR(120) NOT NULL DEFAULT '',
  aprobador_email       VARCHAR(160) NULL,
  numero_sb             VARCHAR(60)  NULL,
  enviada_en            DATETIME NULL,
  aprobada_en           DATETIME NULL,
  aprobacion_notificada_en DATETIME NULL,
  comprado_en           DATETIME NULL,
  cerrado_en            DATETIME NULL,
  rechazada_en          DATETIME NULL,
  ultimo_recordatorio   DATETIME NULL,
  recordatorios_enviados INT NOT NULL DEFAULT 0,
  creado_en             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  ip_origen             VARCHAR(45) NULL,
  PRIMARY KEY (id_solicitud),
  UNIQUE KEY uq_cot_folio (folio),
  KEY idx_cot_estatus (estatus),
  KEY idx_cot_enviada (enviada_en),
  KEY idx_cot_creado  (creado_en),
  KEY idx_cot_vin     (vin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cot_comentarios (
  id_comentario BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_solicitud  BIGINT UNSIGNED NOT NULL,
  autor_rol     VARCHAR(20)  NOT NULL,
  autor_nombre  VARCHAR(120) NOT NULL,
  tipo          ENUM('COMENTARIO','REVISION','APROBACION','RECHAZO','SISTEMA')
                NOT NULL DEFAULT 'COMENTARIO',
  texto         TEXT NOT NULL,
  creado_en     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_comentario),
  KEY idx_cot_com_sol (id_solicitud)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cot_adjuntos (
  id_adjunto   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_solicitud BIGINT UNSIGNED NOT NULL,
  nombre       VARCHAR(200) NOT NULL,
  mime         VARCHAR(120) NOT NULL DEFAULT 'application/octet-stream',
  tamano       INT UNSIGNED NOT NULL DEFAULT 0,
  contenido    MEDIUMBLOB NOT NULL,
  creado_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_adjunto),
  KEY idx_cot_adj_sol (id_solicitud)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cot_correos (
  id_correo    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_solicitud BIGINT UNSIGNED NULL,
  tipo         ENUM('SOLICITUD','RECORDATORIO','APROBACION','RECHAZO')
               NOT NULL DEFAULT 'SOLICITUD',
  destinatario VARCHAR(200) NOT NULL DEFAULT '',
  asunto       VARCHAR(255) NOT NULL DEFAULT '',
  cuerpo       TEXT NOT NULL,
  estado       ENUM('SIMULADO','ENVIADO','ERROR') NOT NULL DEFAULT 'SIMULADO',
  error        TEXT NULL,
  creado_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_correo),
  KEY idx_cot_correo_sol (id_solicitud),
  KEY idx_cot_correo_fecha (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cot_catalogos (
  id_catalogo INT UNSIGNED NOT NULL AUTO_INCREMENT,
  tipo        VARCHAR(30)  NOT NULL,
  valor       VARCHAR(160) NOT NULL,
  activo      TINYINT(1)   NOT NULL DEFAULT 1,
  creado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_catalogo),
  UNIQUE KEY uq_cot_catalogo (tipo, valor),
  KEY idx_cot_cat_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Semilla inicial de catalogos (puedes agregar mas desde el formulario).
INSERT INTO cot_catalogos (tipo, valor) VALUES
  ('tipo_servicio', 'Reparación'),
  ('tipo_servicio', 'Mantenimiento correctivo'),
  ('tipo_servicio', 'Mantenimiento preventivo'),
  ('tipo_servicio', 'Suministro'),
  ('tipo_servicio', 'Servicio externo'),
  ('ubicacion', 'TOT LC'),
  ('ubicacion', 'TOT NDVC')
ON DUPLICATE KEY UPDATE activo = 1;
