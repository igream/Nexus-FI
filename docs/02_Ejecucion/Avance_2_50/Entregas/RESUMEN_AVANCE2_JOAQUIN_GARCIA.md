# FORMATO UNIVERSAL DE DOCUMENTACIÓN DE TAREAS

**PROYECTO:** Nexus FI  
**INSTITUCIÓN:** Facultad de Ingeniería - UAEMéx  
**EQUIPO:** 404  
**TAREA:** Avance 2 - WBS 1.3.5 / 1.4.2 (Middleware de Filtrado Perimetral por IP y Control de Sesión / Límite de Uso)  
**ENCARGADO:** Joaquín Ulises García Álvarez  
**PROJECT MANAGER:** Fernando Azuara Ibarra  
**FECHA DE ENTREGA:** 28 de octubre de 2026  

---

## 1. RESUMEN EJECUTIVO Y OBJETIVOS

En cumplimiento con la entrega del 50% del proyecto Nexus FI, se implementó la capa perimetral de seguridad y control de cuotas para el backend en FastAPI. El objetivo general es proteger los créditos de inferencia del API de Gemini y restringir el acceso exclusivo a los equipos conectados a la red física e inalámbrica institucional de la Facultad de Ingeniería (UAEMéx).

---

## 2. SUBREDES /24 AUTORIZADAS (PERÍMETRO INSTITUCIONAL)

Se configuró el filtrado perimetral validando contra los bloques `/24` asignados oficialmente a los Edificios A, B, C y laboratorios de la Facultad:

1. `172.17.18.0/24`
2. `148.215.12.0/24`
3. `148.215.18.0/24`
4. `148.215.30.0/24`
5. `148.215.31.0/24`

Cualquier solicitud fuera de estos bloques retorna un código **HTTP 403 Forbidden**.

---

## 3. CONTROL DE CUOTAS Y RATE LIMITING (WBS 1.4.2)

Se implementó el seguimiento mediante **Device Fingerprinting** en combinación con **UUID persistente** (`X-Device-Fingerprint`, `X-Session-ID`).

- **Límite por Hora:** 20 consultas / hora.
- **Límite por Día:** 60 consultas / día.
- **Exceso de límite:** Retorna **HTTP 429 Too Many Requests** acompañado del encabezado `Retry-After`.

---

## 4. COORDINACIÓN TÉCNICA E INFRAESTRUCTURA (AWS & NGINX)

Se envió la Ficha de Coordinación Técnica a Ángel Israel de la Cruz Martínez para garantizar que el proxy Nginx en AWS EC2 transmita la cabecera `X-Forwarded-For` agregando la IP cliente real sin sobrescribirla por la IP privada interna.

---

**Nombre y firma del encargado:** Joaquín Ulises García Álvarez  
**Nombre y firma del PM:** Fernando Azuara Ibarra