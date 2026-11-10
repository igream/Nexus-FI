# Comparación de modelos — Nexus FI (2026-11-10 0150)

Generado con `scripts/comparar_modelos.py` sobre 20 preguntas de `scripts/preguntas_comparacion.json`, por el mismo flujo de `/api/chat` que usa producción. Acierto = la respuesta contiene los hechos esperados; cita = alguna fuente es el documento esperado. Las respuestas completas están en el JSON del mismo nombre.

| Modelo | Esfuerzo | Aciertos | Citas correctas | Latencia LLM (mediana / máx.) | Tokens de salida (prom.) | Costo por consulta | Costo total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gpt-4o-mini` | — | 17/20 | 17/20 | 2452 / 6861 ms | 107 | 0.000393 USD | 0.00708 USD |
| `gpt-6-luna` | low | 17/20 | 17/20 | 2127 / 2786 ms | 87 | 0.000263 USD | 0.00473 USD |
| `gpt-5.6-luna` | low | 17/20 | 17/20 | 2062 / 4371 ms | 137 | 0.000603 USD | 0.01085 USD |

## Detalle por pregunta

| # | Pregunta | `gpt-4o-mini` | `gpt-6-luna` | `gpt-5.6-luna` |
| :---: | :--- | :---: | :---: | :---: |
| 1 | ¿Cuántas horas de servicio social se deben cubrir? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 2 | ¿Qué porcentaje del plan de estudios necesito para hacer el servicio social? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 3 | ¿Cuánto tiempo mínimo y máximo dura el servicio social? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 4 | ¿En cuánto tiempo se emite la carta de presentación del servicio social? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 5 | ¿Qué opciones de titulación existen en la UAEMéx? | ❌ ∅ | ❌ ∅ | ❌ ∅ |
| 6 | ¿Qué promedio necesito para hacer movilidad estudiantil? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 7 | Que materias se dan en el sexto semestre de ingenieria en computación? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 8 | ¿Qué materias hay en séptimo semestre de ICO? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 9 | ¿Qué se cursa en el décimo semestre de Ingeniería en Computación? | ❌ ∅ | ❌ ∅ | ❌ ∅ |
| 10 | ¿Quién es la coordinadora de la Licenciatura en Ingeniería en Computación? | ❌ ∅ | ❌ ∅ | ❌ ∅ |
| 11 | ¿Qué capítulos tiene la Rama Estudiantil IEEE de la UAEMéx? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 12 | ¿En qué competencias o hackatones participa la rama IEEE? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 13 | ¿Qué promedio piden para la Beca de Reinscripción Escolar? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 14 | ¿Para qué sirve la Beca de Reinscripción Escolar? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 15 | ¿Quién es la jefa de Control Escolar de la Facultad de Ingeniería? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 16 | ¿Cuál es el correo de Control Escolar de la FI? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 17 | ¿Qué trámites puedo hacer en Control Escolar? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 18 | ¿Puedo hacer el servicio social si apenas llevo el 30 % de mis créditos? | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 19 | Dame una receta de pozole rojo | ✅ 📄 | ✅ 📄 | ✅ 📄 |
| 20 | ¿Quién ganó el mundial de fútbol de 2022? | ✅ 📄 | ✅ 📄 | ✅ 📄 |

✅/❌ acierto · 📄 cita correcta · ∅ sin la fuente esperada

## Respuestas que fallaron

**[5] `gpt-4o-mini`** — ¿Qué opciones de titulación existen en la UAEMéx?

- Esperado: Reglamento de Evaluación Profesional: 13 opciones (aprovechamiento académico, tesis, tesina, EGEL...).
- Fuentes: Guia_Tramites.pdf, Guia_Tramites.pdf, Guia_Tramites.pdf, Guia_Tramites.pdf
- Respuesta: En la UAEMéx, existen varias opciones de titulación para los egresados. A continuación, se presentan las modalidades más comunes:  1. **Evaluación Profesional**: Esta opción requiere la presentación de un examen profesional. Los documentos necesarios incluyen:    - Acta de evaluación profesional.    - Certificado total de licenciatura.    - Solicitud por escrito dirigida a la Subdirección Académica.  2. **Artículo Especializado**: Consiste en la publicación de un artículo en una revista arbitrada. Se deben presentar documentos similares a los de la evaluación profesional, además de la constanc

**[5] `gpt-6-luna`** — ¿Qué opciones de titulación existen en la UAEMéx?

- Esperado: Reglamento de Evaluación Profesional: 13 opciones (aprovechamiento académico, tesis, tesina, EGEL...).
- Fuentes: Guia_Tramites.pdf, Guia_Tramites.pdf, Guia_Tramites.pdf, Guia_Tramites.pdf
- Respuesta: La **Guía de Trámites de la UAEMéx** menciona estas opciones de titulación profesional en el contexto proporcionado:  - **Aprovechamiento académico** (págs. 35–37). - **Artículo especializado publicado en revista arbitrada** (págs. 37–38). - **Créditos en estudios avanzados** (pág. 39).  La guía también alude a la evaluación profesional, pero el contexto disponible no incluye la lista completa de modalidades. Para confirmarlas, consulta la **Guía de Trámites** completa o a la **Coordinación de ICO**.

**[5] `gpt-5.6-luna`** — ¿Qué opciones de titulación existen en la UAEMéx?

- Esperado: Reglamento de Evaluación Profesional: 13 opciones (aprovechamiento académico, tesis, tesina, EGEL...).
- Fuentes: Guia_Tramites.pdf, Guia_Tramites.pdf, Guia_Tramites.pdf, Guia_Tramites.pdf
- Respuesta: Según la **Guía de Trámites de la UAEMéx**, se identifican las siguientes modalidades de titulación:  1. **Aprovechamiento académico**.   2. **Artículo especializado publicado en revista arbitrada**.   3. **Créditos en estudios avanzados**, mediante estudios de maestría, doctorado integral o diplomado superior, conforme a los requisitos establecidos.  **Fuente:** *Guia_Tramites.pdf*, págs. 35-39, integración de expedientes de titulación.    La guía proporcionada no incluye el listado completo de modalidades ni especifica cuáles aplican particularmente a Ingeniería en Computación. Para confirma

**[9] `gpt-4o-mini`** — ¿Qué se cursa en el décimo semestre de Ingeniería en Computación?

- Esperado: Horario 2026-B, semestre 10: Práctica profesional.
- Fuentes: Tecnologias_computacionales_I.pdf, Calculo_I.pdf, horarios_ico_semestre_9.md, 6to_PE_ICO_INGENIERIA_DE_SOFTWARE_II.pdf
- Respuesta: En el décimo semestre de la Licenciatura en Ingeniería en Computación se cursan las siguientes materias:  1. **Proyecto integral de comunicación de datos** 2. **Proyecto integral de ingeniería de software** 3. **Tecnologías computacionales II** 4. **Gestión de redes** 5. **Computing in industry** 6. **Interacción hombre-máquina** 7. **Tecnologías emergentes** 8. **Tópicos de tecnologías de datos** 9. **Sistemas interactivos**  Esta información se encuentra en el documento de horarios correspondiente al semestre 10 de la carrera (FUENTE [3]). Si necesitas más detalles sobre alguna materia en pa

**[9] `gpt-6-luna`** — ¿Qué se cursa en el décimo semestre de Ingeniería en Computación?

- Esperado: Horario 2026-B, semestre 10: Práctica profesional.
- Fuentes: Tecnologias_computacionales_I.pdf, Calculo_I.pdf, horarios_ico_semestre_9.md, 6to_PE_ICO_INGENIERIA_DE_SOFTWARE_II.pdf
- Respuesta: No puedo identificar con certeza las materias del décimo semestre con el texto disponible: los mapas curriculares aparecen desordenados y no permiten asociar de forma confiable cada materia con ese periodo.  Para confirmar la lista, consulta el plan de estudios oficial o a la Coordinación de Ingeniería en Computación (ICO).

**[9] `gpt-5.6-luna`** — ¿Qué se cursa en el décimo semestre de Ingeniería en Computación?

- Esperado: Horario 2026-B, semestre 10: Práctica profesional.
- Fuentes: Tecnologias_computacionales_I.pdf, Calculo_I.pdf, horarios_ico_semestre_9.md, 6to_PE_ICO_INGENIERIA_DE_SOFTWARE_II.pdf
- Respuesta: El contexto disponible **no presenta una lista clara y confiable de las unidades de aprendizaje correspondientes al décimo semestre** de Ingeniería en Computación. El mapa curricular está desordenado y no permite asociar con certeza cada materia al **periodo 10**.  La fuente sí identifica materias del **semestre 9**, pero no del décimo: **“Horario del periodo 2026B… semestre 9”**, en *horarios_ico_semestre_9.md*.  Para confirmar qué se cursa en décimo semestre, consulta el **plan de estudios vigente** o acude a la **Coordinación de Ingeniería en Computación (ICO)** y, si es necesario, a **Subd

**[10] `gpt-4o-mini`** — ¿Quién es la coordinadora de la Licenciatura en Ingeniería en Computación?

- Esperado: Horarios 2026-B: Mtra. Beatriz Orozco Garduño, Coordinación de ICO.
- Fuentes: Mapa_Curricular_ICO_F19.pdf, INVESTIGACION_DE_OPERACIONES.pdf, Epistemologia.pdf, INGENIERIA_DE_SOFTWARE_I.pdf
- Respuesta: No se proporciona información sobre la coordinadora de la Licenciatura en Ingeniería en Computación en el contexto oficial disponible. Te sugiero que consultes directamente con la Coordinación de la Licenciatura en Ingeniería en Computación o revises la página oficial de la Facultad de Ingeniería para obtener esta información.

**[10] `gpt-6-luna`** — ¿Quién es la coordinadora de la Licenciatura en Ingeniería en Computación?

- Esperado: Horarios 2026-B: Mtra. Beatriz Orozco Garduño, Coordinación de ICO.
- Fuentes: Mapa_Curricular_ICO_F19.pdf, INVESTIGACION_DE_OPERACIONES.pdf, Epistemologia.pdf, INGENIERIA_DE_SOFTWARE_I.pdf
- Respuesta: El contexto proporcionado no indica quién es la coordinadora de la Licenciatura en Ingeniería en Computación. Puedes consultar directamente a la Coordinación de ICO de la Facultad de Ingeniería.

**[10] `gpt-5.6-luna`** — ¿Quién es la coordinadora de la Licenciatura en Ingeniería en Computación?

- Esperado: Horarios 2026-B: Mtra. Beatriz Orozco Garduño, Coordinación de ICO.
- Fuentes: Mapa_Curricular_ICO_F19.pdf, INVESTIGACION_DE_OPERACIONES.pdf, Epistemologia.pdf, INGENIERIA_DE_SOFTWARE_I.pdf
- Respuesta: No se proporciona el nombre de la coordinadora de la Licenciatura en Ingeniería en Computación en el contexto oficial disponible.  Te sugiero consultarlo directamente con la **Coordinación de Ingeniería en Computación (ICO)** de la Facultad de Ingeniería.
