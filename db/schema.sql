-- ============================================================================
--  Tablas para el Test Diario de Alertamiento por Fatiga Laboral
--  Base: kogn1v1s (Amazon RDS MySQL 8.0)
--
--  Este script es IDEMPOTENTE (se puede ejecutar varias veces sin problema).
--  Solo AGREGA tablas nuevas con prefijo "fatiga_"; no modifica las existentes.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Catalogo de preguntas (10 preguntas, 4 secciones)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fatiga_preguntas (
  id_pregunta   TINYINT UNSIGNED NOT NULL,
  seccion       VARCHAR(40)  NOT NULL,
  orden         TINYINT UNSIGNED NOT NULL,
  texto         VARCHAR(255) NOT NULL,
  critica       TINYINT(1)   NOT NULL DEFAULT 0,
  opcion_0      VARCHAR(140) NOT NULL,
  opcion_1      VARCHAR(140) NOT NULL,
  opcion_2      VARCHAR(140) NOT NULL,
  PRIMARY KEY (id_pregunta)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 2. Encabezado del test (un registro por test llenado)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fatiga_tests (
  id_test          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_usuario       INT NULL,
  num_empleado     INT NULL,
  nombre_completo  VARCHAR(100) NOT NULL,
  puesto           VARCHAR(60)  NULL,
  departamento     VARCHAR(60)  NULL,
  empresa          VARCHAR(70)  NULL,
  turno            VARCHAR(30)  NULL,
  hora_entrada     TIME NULL,
  fecha            DATE NOT NULL,
  puntaje_total    TINYINT UNSIGNED NOT NULL,
  semaforo         ENUM('VERDE','AMARILLO','ROJO') NOT NULL,
  critica_con_2pts TINYINT(1) NOT NULL DEFAULT 0,
  jornada_extra    ENUM('PUEDE','NO_DEBE') NOT NULL,
  accion_tomada    VARCHAR(255) NULL,
  observaciones    TEXT NULL,
  firma_trabajador VARCHAR(120) NULL,
  validador_nombre VARCHAR(120) NULL,
  creado_en        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip_origen        VARCHAR(45) NULL,
  PRIMARY KEY (id_test),
  KEY idx_fatiga_fecha    (fecha),
  KEY idx_fatiga_usuario  (id_usuario),
  KEY idx_fatiga_num_emp  (num_empleado),
  KEY idx_fatiga_semaforo (semaforo),
  KEY idx_fatiga_depto    (departamento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 3. Detalle: valor (0/1/2) por cada pregunta de cada test
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fatiga_respuestas (
  id_respuesta BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_test      BIGINT UNSIGNED NOT NULL,
  id_pregunta  TINYINT UNSIGNED NOT NULL,
  valor        TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (id_respuesta),
  KEY idx_resp_test (id_test),
  KEY idx_resp_preg (id_pregunta),
  CONSTRAINT fk_resp_test FOREIGN KEY (id_test)
    REFERENCES fatiga_tests (id_test) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 3b. Firma dibujada (imagen) por test. Tabla aparte para no depender de ALTER.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fatiga_firmas (
  id_test      BIGINT UNSIGNED NOT NULL,
  firma_imagen MEDIUMTEXT NOT NULL,
  creado_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_test)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 4. Semilla del catalogo de preguntas
-- ---------------------------------------------------------------------------
INSERT INTO fatiga_preguntas
  (id_pregunta, seccion, orden, texto, critica, opcion_0, opcion_1, opcion_2)
VALUES
  (1,'A. Descanso',1,'¿Cuántas horas dormiste anoche?',1,
     '7 h o más','Entre 5 y 6 h','Menos de 5 h'),
  (2,'A. Descanso',2,'¿Cómo fue la calidad de tu sueño?',0,
     'Reparador','Interrumpido','Casi no dormí'),
  (3,'A. Descanso',3,'¿Cuántas horas pasaron entre el fin de tu última jornada y el inicio de la de hoy?',1,
     '12 h o más','Entre 10 y 11 h','Menos de 10 h'),
  (4,'A. Descanso',4,'¿Cuántos días seguidos llevas trabajando, sin día de descanso?',0,
     '1 a 5 días','6 días','7 días o más'),
  (5,'B. Estado de ánimo',5,'¿Cómo te sientes hoy?',0,
     'Tranquilo/a, de buen ánimo','Algo cansado/a o irritable','Agotado/a, muy irritable o decaído/a'),
  (6,'B. Estado de ánimo',6,'¿Tienes preocupaciones o estrés (personal o laboral) que te cuesten concentración?',0,
     'Ninguna','Algunas','Muchas'),
  (7,'C. Motivación y atención',7,'¿Qué tantas ganas tienes de trabajar hoy?',0,
     'Muchas','Regulares','Pocas o ninguna'),
  (8,'C. Motivación y atención',8,'¿Te sientes capaz de mantener la atención en tus tareas (maniobras, conducción de unidades)?',1,
     'Totalmente','Con esfuerzo','Me cuesta mucho'),
  (9,'D. Señales físicas y sustancias',9,'¿Tienes somnolencia, bostezos frecuentes, mareo, visión borrosa o dolor de cabeza?',1,
     'Ninguno','Leve','Intenso'),
  (10,'D. Señales físicas y sustancias',10,'En las últimas 12 h, ¿consumiste alcohol, medicamentos que dan sueño o energizantes en exceso?',1,
     'No','Café o energizantes en exceso','Alcohol o medicamento que da sueño')
ON DUPLICATE KEY UPDATE
  seccion=VALUES(seccion), orden=VALUES(orden), texto=VALUES(texto),
  critica=VALUES(critica), opcion_0=VALUES(opcion_0),
  opcion_1=VALUES(opcion_1), opcion_2=VALUES(opcion_2);

-- ============================================================================
--  CHECK LIST DE SEGURIDAD BASADA EN COMPORTAMIENTO (REG-SST-25)
--  Modulo independiente. No modifica fatiga_* ni usuarios.
-- ============================================================================

CREATE TABLE IF NOT EXISTS sst_preguntas (
  id_pregunta TINYINT UNSIGNED NOT NULL,
  orden       TINYINT UNSIGNED NOT NULL,
  texto       VARCHAR(255) NOT NULL,
  PRIMARY KEY (id_pregunta)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sst_auditorias (
  id_auditoria     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha            DATE NOT NULL,
  area             VARCHAR(100) NOT NULL,
  departamento     VARCHAR(100) NOT NULL,
  auditado         VARCHAR(120) NOT NULL,
  auditor          VARCHAR(120) NOT NULL,
  comentarios      TEXT NULL,
  seguras          TINYINT UNSIGNED NOT NULL,
  inseguras        TINYINT UNSIGNED NOT NULL,
  porcentaje       TINYINT UNSIGNED NOT NULL,
  firma_trabajador MEDIUMTEXT NOT NULL,
  firma_auditor    MEDIUMTEXT NOT NULL,
  creado_en        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip_origen        VARCHAR(45) NULL,
  PRIMARY KEY (id_auditoria),
  KEY idx_sst_fecha    (fecha),
  KEY idx_sst_area     (area),
  KEY idx_sst_auditado (auditado),
  KEY idx_sst_auditor  (auditor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sst_respuestas (
  id_respuesta  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_auditoria  BIGINT UNSIGNED NOT NULL,
  n             TINYINT UNSIGNED NOT NULL,
  estado        ENUM('SEGURO','INSEGURO') NOT NULL,
  observacion   VARCHAR(400) NULL,
  PRIMARY KEY (id_respuesta),
  KEY idx_sst_resp_aud (id_auditoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Catalogos administrables (se agregan desde el Panel > Catalogos).
-- No modifican sst_auditorias: area y auditor siguen guardandose como texto.
CREATE TABLE IF NOT EXISTS sst_auditores (
  id_auditor  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre      VARCHAR(120) NOT NULL,
  activo      TINYINT(1) NOT NULL DEFAULT 1,
  creado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_auditor),
  UNIQUE KEY uq_sst_auditor_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sst_areas (
  id_area    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre     VARCHAR(120) NOT NULL,
  activo     TINYINT(1) NOT NULL DEFAULT 1,
  creado_en  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_area),
  UNIQUE KEY uq_sst_area_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sst_preguntas (id_pregunta, orden, texto) VALUES
  (1,1,'Porta su EPP completo, de forma correcta y de acuerdo al riesgo de su tarea.'),
  (2,2,'Hace uso del uniforme otorgado por la empresa de forma adecuada.'),
  (3,3,'Reporta incidencias, actos o condiciones inseguras de inmediato a su supervisor.'),
  (4,4,'Realiza sus actividades de acuerdo a lo establecido en su Instrucción de Trabajo y el AST.'),
  (5,5,'Se relaciona de forma respetuosa, no realiza bromas o juegos físicos en el área de trabajo.'),
  (6,6,'Se relaciona de forma respetuosa, no realiza bromas o juegos físicos en el área de trabajo.'),
  (7,7,'Evita atajos o métodos no autorizados para agilizar su trabajo.'),
  (8,8,'Conduce a velocidad adecuada de acuerdo con los flujos establecidos.'),
  (9,9,'Sigue los métodos de conducción segura (reversa asistida, uso de claxon, etc.).'),
  (10,10,'No usa el teléfono celular durante la operación de equipos o tareas de riesgo.'),
  (11,11,'Adopta posturas ergonómicas al levantar cargas (espalda recta, piernas dobladas) y no excede el límite de carga permitido.'),
  (12,12,'Hace uso de los tres puntos de apoyo al ascender o descender de un equipo, unidad o plataforma.'),
  (13,13,'Trabaja sin exponer partes del cuerpo a zonas de pellizco o atrapamiento.'),
  (14,14,'Verifica el estado de sus herramientas de trabajo antes de usarlas y las usa adecuadamente.'),
  (15,15,'Mantiene su área de trabajo ordenada y libre de obstáculos en pasillos.'),
  (16,16,'Deposita residuos y materiales en los lugares designados.'),
  (17,17,'Participa activamente en el diálogo de seguridad / plática de arranque de turno.'),
  (18,18,'Acepta retroalimentación de seguridad de forma receptiva y sin actitud defensiva.')
ON DUPLICATE KEY UPDATE
  orden=VALUES(orden), texto=VALUES(texto);

