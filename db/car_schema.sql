-- ============================================================================
--  Modulo CAR · Tarjeta de control y administración de riesgos
--  Base: kogn1v1s (MySQL 8.0 / Amazon RDS)
--
--  Script idempotente. Solo agrega tablas con prefijo car_ y no modifica
--  fatiga_*, sst_* ni usuarios.
-- ============================================================================

CREATE TABLE IF NOT EXISTS car_areas (
  id_area    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre     VARCHAR(120) NOT NULL,
  activo     TINYINT(1) NOT NULL DEFAULT 1,
  creado_en  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_area),
  UNIQUE KEY uq_car_area_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS car_tarjetas (
  id_tarjeta          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  folio               VARCHAR(20) NOT NULL,
  fecha               DATE NOT NULL,
  id_usuario          INT NULL,
  observador          VARCHAR(120) NOT NULL,
  num_empleado        INT NULL,
  area                VARCHAR(120) NOT NULL,
  tipo                VARCHAR(30) NOT NULL,
  descripcion         TEXT NOT NULL,
  controlado          VARCHAR(2) NOT NULL,
  clasificacion       VARCHAR(10) NOT NULL,
  acciones_inmediatas TEXT NULL,
  acciones_definitivas TEXT NULL,
  fecha_compromiso    DATE NULL,
  firma_emisor        MEDIUMTEXT NOT NULL,
  estado              VARCHAR(12) NOT NULL DEFAULT 'PENDIENTE',
  responsable         VARCHAR(120) NULL,
  area_responsable    VARCHAR(120) NULL,
  firma_responsable   MEDIUMTEXT NULL,
  comentario_cierre   TEXT NULL,
  revision            TINYINT(1) NOT NULL DEFAULT 0,
  fecha_cierre        DATE NULL,
  cerrado_en          DATETIME NULL,
  cerrado_por         VARCHAR(40) NULL,
  creado_en           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip_origen           VARCHAR(45) NULL,
  PRIMARY KEY (id_tarjeta),
  UNIQUE KEY uq_car_folio (folio),
  KEY idx_car_fecha (fecha),
  KEY idx_car_estado (estado),
  KEY idx_car_clasificacion (clasificacion),
  KEY idx_car_usuario (id_usuario),
  KEY idx_car_area (area)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS car_evidencias (
  id_evidencia BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_tarjeta   BIGINT UNSIGNED NULL,
  tipo         VARCHAR(10) NOT NULL,
  nombre       VARCHAR(255) NOT NULL,
  mime         VARCHAR(100) NOT NULL,
  tamano       INT UNSIGNED NOT NULL,
  archivo      VARCHAR(80) NOT NULL,
  creado_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_evidencia),
  UNIQUE KEY uq_car_archivo (archivo),
  KEY idx_car_evidencia_tarjeta (id_tarjeta),
  CONSTRAINT fk_car_evidencia_tarjeta
    FOREIGN KEY (id_tarjeta) REFERENCES car_tarjetas (id_tarjeta)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Áreas iniciales. El administrador puede quitarlas o agregar más desde
-- Panel → Catálogos. Si ya existen, no se duplican.
INSERT IGNORE INTO car_areas (nombre) VALUES
  ('Almacén'),
  ('Calidad'),
  ('Mantenimiento'),
  ('Operaciones'),
  ('Seguridad y Salud'),
  ('TI');
