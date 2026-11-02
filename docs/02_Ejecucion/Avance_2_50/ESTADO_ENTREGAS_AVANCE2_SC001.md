# Estado de las entregas del Avance 2 tras la SC-001

**Proyecto:** Nexus FI · Equipo 404
**Referencia:** Solicitud de Cambio SC-001, aprobada el 29 de octubre de 2026 (`docs/02_Ejecucion/Control_Cambios/SOLICITUD_CAMBIO_SC001_PRUEBA_PILOTO_ICO.docx`)

La SC-001 acota el proyecto a una prueba piloto en ICO y descarta el control de acceso por IP. Ningún archivo se borra: lo descartado se conserva como línea base y como evidencia del trabajo realizado y evaluado en el 50 %.

| Entrega | Integrantes | Estado | Motivo |
| :--- | :--- | :--- | :--- |
| Middleware de filtrado perimetral por IP (subredes /24 de la FI) | Joaquín Ulises García Álvarez | **Descartada** | Ya no se valida el acceso por IP. El código se retira en la Fase 3 de la SC-001 y queda en el historial de Git (etiqueta `pre-SC-001`). |
| Control de sesión con límite de uso por IP y dispositivo | Joaquín Ulises García Álvarez | **Se reutiliza parcialmente** | La lógica de límite se conserva para aplicarla por usuario registrado: 20 consultas por hora y 60 por día. |
| Investigación de subredes IP de la Facultad (inciso a) | Santiago Cuevas Sánchez y Azuleica Betsabel de la Cruz González | **Descartada** | Ya no se solicitan segmentos de red; el oficio de segmentación también se descarta. |
| Oficio de solicitud de la Meta Graph API (inciso b) | Santiago Cuevas Sánchez y Azuleica Betsabel de la Cruz González | **Vigente** | Se conserva; en la prueba piloto se asume respuesta positiva. |
| Nginx como proxy inverso y Docker Compose | Ángel Israel de la Cruz Martínez | **Vigente, con ajuste** | El proxy sigue; reenviar la IP real del cliente (`X-Forwarded-For`) deja de ser requisito de acceso y solo queda para bitácoras. |
| Especificación de arquitectura AWS | Ángel Israel de la Cruz Martínez y Aarón Nevid Domínguez Fuentes | **Vigente** | El montaje en la nube continúa (EC2 en us-east-2). |
| Modo oscuro, tablero de usuario y panel de métricas | Daniel Aguilar Sánchez y Joan Alexis Ocaña Martínez | **Vigente** | Sin relación con el control por IP. |

## Archivos relacionados
- Descartados como entrega vigente (se conservan):
  - `Asignaciones/FORMATO_ASIGNACION_AVANCE2_JOAQUIN_GARCIA.docx`
  - `Entregas/FORMATO_UNIVERSAL_AVANCE2_JOAQUIN_GARCIA.docx`
  - `Entregas/RESUMEN_AVANCE2_JOAQUIN_GARCIA.md`
  - Inciso a) de `Asignaciones/FORMATO_ASIGNACION_AVANCE2_SANTIAGO_CUEVAS_Y_AZULEICA_DE_LA_CRUZ.docx`
