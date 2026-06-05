-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 05-06-2026 a las 06:43:48
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `flask_db`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `clases_docente`
--

CREATE TABLE `clases_docente` (
  `id_clase` int(11) NOT NULL,
  `id_docente` int(11) NOT NULL,
  `nombre` varchar(120) NOT NULL,
  `codigo` varchar(16) NOT NULL,
  `fecha_creacion` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `inscripciones_clase`
--

CREATE TABLE `inscripciones_clase` (
  `id_inscripcion` int(11) NOT NULL,
  `id_clase` int(11) NOT NULL,
  `id_estudiante` int(11) NOT NULL,
  `fecha_inscripcion` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `registros_clasificacion`
--

CREATE TABLE `registros_clasificacion` (
  `id` int(11) NOT NULL,
  `id_usuario` int(11) NOT NULL,
  `fecha_hora` datetime DEFAULT current_timestamp(),
  `residuo_detectado` varchar(100) DEFAULT NULL,
  `categoria_asignada` varchar(50) DEFAULT NULL,
  `categoria_correcta` varchar(50) DEFAULT NULL,
  `es_correcto` tinyint(1) NOT NULL DEFAULT 0,
  `confianza_modelo` float DEFAULT NULL,
  `container_color` varchar(20) DEFAULT NULL,
  `es_auto_capture` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tipo_documento`
--

CREATE TABLE `tipo_documento` (
  `id_tipo_documento` int(11) NOT NULL,
  `descripcion` varchar(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `tipo_documento` (`id_tipo_documento`, `descripcion`) VALUES
(1, 'Cedula de ciudadania'),
(3, 'Cedula de extranjeria'),
(4, 'Pasaporte'),
(2, 'Tarjeta de identidad');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tipo_genero`
--

CREATE TABLE `tipo_genero` (
  `id_tipo_genero` int(11) NOT NULL,
  `descripcion` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `tipo_genero` (`id_tipo_genero`, `descripcion`) VALUES
(2, 'Femenino'),
(1, 'Masculino'),
(3, 'Otro'),
(7, 'Prefiero no decirlo');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tipo_usuario`
--

CREATE TABLE `tipo_usuario` (
  `id_tipo_usuario` int(11) NOT NULL,
  `descripcion` varchar(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `tipo_usuario` (`id_tipo_usuario`, `descripcion`) VALUES
(1, 'Admin'),
(2, 'Docente'),
(3, 'Estudiante');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `usuarios`
--

CREATE TABLE `usuarios` (
  `id` int(11) NOT NULL,
  `nombres` varchar(100) NOT NULL,
  `apellidos` varchar(100) NOT NULL,
  `id_tipo_documento` int(11) NOT NULL,
  `numero_documento` varchar(20) NOT NULL,
  `id_tipo_genero` int(11) NOT NULL,
  `id_tipo_usuario` int(11) NOT NULL,
  `correo` varchar(100) NOT NULL,
  `telefono` varchar(20) DEFAULT NULL,
  `foto_perfil` varchar(255) DEFAULT NULL,
  `ecopuntos` int(11) NOT NULL DEFAULT 0,
  `ecomultas` int(11) NOT NULL DEFAULT 0,
  `usuario` varchar(50) NOT NULL,
  `contrasena` varchar(255) NOT NULL,
  `fecha_registro` timestamp NOT NULL DEFAULT current_timestamp(),
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `rostro_facial` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Índices
--

ALTER TABLE `clases_docente`
  ADD PRIMARY KEY (`id_clase`),
  ADD UNIQUE KEY `codigo` (`codigo`),
  ADD KEY `idx_clases_docente_id_docente` (`id_docente`);

ALTER TABLE `inscripciones_clase`
  ADD PRIMARY KEY (`id_inscripcion`),
  ADD UNIQUE KEY `uq_clase_estudiante` (`id_clase`,`id_estudiante`),
  ADD KEY `idx_inscripciones_clase` (`id_clase`),
  ADD KEY `idx_inscripciones_estudiante` (`id_estudiante`);

ALTER TABLE `registros_clasificacion`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_reg_clasif_usuario` (`id_usuario`),
  ADD KEY `idx_reg_clasif_fecha` (`fecha_hora`);

ALTER TABLE `tipo_documento`
  ADD PRIMARY KEY (`id_tipo_documento`),
  ADD UNIQUE KEY `uq_tipo_documento_descripcion` (`descripcion`);

ALTER TABLE `tipo_genero`
  ADD PRIMARY KEY (`id_tipo_genero`),
  ADD UNIQUE KEY `uq_tipo_genero_descripcion` (`descripcion`);

ALTER TABLE `tipo_usuario`
  ADD PRIMARY KEY (`id_tipo_usuario`),
  ADD UNIQUE KEY `uq_tipo_usuario_descripcion` (`descripcion`);

ALTER TABLE `usuarios`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `numero_documento` (`numero_documento`),
  ADD UNIQUE KEY `correo` (`correo`),
  ADD UNIQUE KEY `usuario` (`usuario`),
  ADD KEY `fk_tipo_documento` (`id_tipo_documento`),
  ADD KEY `fk_tipo_genero` (`id_tipo_genero`),
  ADD KEY `fk_tipo_usuario` (`id_tipo_usuario`);

--
-- AUTO_INCREMENT
--

ALTER TABLE `clases_docente` MODIFY `id_clase` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;
ALTER TABLE `inscripciones_clase` MODIFY `id_inscripcion` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;
ALTER TABLE `registros_clasificacion` MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=34;
ALTER TABLE `tipo_documento` MODIFY `id_tipo_documento` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=77;
ALTER TABLE `tipo_genero` MODIFY `id_tipo_genero` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=76;
ALTER TABLE `tipo_usuario` MODIFY `id_tipo_usuario` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=58;
ALTER TABLE `usuarios` MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- Restricciones
--

ALTER TABLE `usuarios`
  ADD CONSTRAINT `fk_tipo_documento` FOREIGN KEY (`id_tipo_documento`) REFERENCES `tipo_documento` (`id_tipo_documento`),
  ADD CONSTRAINT `fk_tipo_genero` FOREIGN KEY (`id_tipo_genero`) REFERENCES `tipo_genero` (`id_tipo_genero`),
  ADD CONSTRAINT `fk_tipo_usuario` FOREIGN KEY (`id_tipo_usuario`) REFERENCES `tipo_usuario` (`id_tipo_usuario`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
