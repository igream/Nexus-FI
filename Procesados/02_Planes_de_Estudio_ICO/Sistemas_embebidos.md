---
id: "ico_sistemas_embebidos"
titulo: "Sistemas_embebidos"
categoria: "planes_estudio"
subcategoria: "temario_asignatura"
carrera: "ICO"
periodo: "VIGENTE"
archivo_fuente: "info fi planes de estudio/Sistemas_embebidos.pdf"
total_paginas: 11
es_ocr: false
total_tokens: 7618
total_chunks: 14
---

# Sistemas_embebidos

<!-- Página 1 -->
UNIVERSIDAD AUTÓNOMA DEL ESTADO DE MÉXICO
LICENCIATURA DE INGENIERÍA EN COMPUTACIÓN

PROGRAMA DE ESTUDIOS
SISTEMAS EMBEBIDOS

Elaboró:
M. en Doc. Benjamín Pérez Clavel

Facultad de Ingeniería
M. en C. Judith Moreno Jiménez

Facultad de Ingeniería
Dr. Javier Salas García

Facultad de Ingeniería
Dr. José Martín Flores Albino

Centro Universitario
UAEM Valle de México.
M. en I. David Martínez Martínez

Centro Universitario
UAEM Teotihuacán.

Asesoría
técnica:
Lic. Araceli Rivera Guzmán
Dirección de Estudios
Profesionales

Fecha de
aprobación:
H. Consejo Académico

H. Consejo de Gobierno
12 de septiembre de 2022
13 de septiembre de 2022
Facultad de Ingeniería

<!-- Página 2 -->
2

Índice

Pág.
I.
Datos de identificación.
3
II.
Presentación del programa de estudios.
4
III.
Ubicación de la unidad de aprendizaje en el mapa
curricular.
5
IV.
Objetivos de la formación profesional.
7
V.
Objetivos de la unidad de aprendizaje.
8
VI.
Contenidos de la unidad de aprendizaje y su
organización.
9
VII.
Acervo bibliográfico.
11

<!-- Página 3 -->
3
I. Datos de identificación.
Espacio académico
donde se imparte
Facultad de Ingeniería
Centro Universitario UAEM Atlacomulco
Centro Universitario UAEM Ecatepec
Centro Universitario UAEM Texcoco
Centro Universitario UAEM Valle de Chalco
Centro Universitario UAEM Valle de México
Centro Universitario UAEM Valle de Teotihuacan
Centro Universitario UAEM Zumpango
Unidad Académica Profesional Tianguistenco

Estudios profesionales Licenciatura de Ingeniería en Computación, 2019

Unidad de aprendizaje
Sistemas embebidos
Clave LINC48

Carga académica
2

2

4

6

Horas
teóricas
Horas
prácticas
Total de
horas
Créditos
Carácter
Obligatoria
Tipo
CursoTaller
Periodo escolar
Octavo

Área
curricular
Ingeniería Aplicada y Diseño de
Ingeniería
Núcleo de
formación
Integral

Seriación
Sistemas digitales

Ninguna

UA Antecedente

UA Consecuente

Formación común

No presenta
X

<!-- Página 4 -->
4
II. Presentación del programa de estudios.
A lo largo de la línea de unidades de aprendizaje del área de arquitectura de
computadoras dentro del programa educativo de Ingeniería en Computación, se ha
abordado el estudio de los sistemas analógicos y digitales cada uno en su contexto
de usos y aplicaciones. Sin embargo, uno de los campos en donde se pueden
mezclar ambos mundos, el de los sistemas analógicos y digitales, es el de los
microcontroladores.
El estudio de los microcontroladores permitirá al estudiante entender que no solo se
pueden programar sistemas basados en microprocesadores que soportan
aplicaciones de alto nivel orientadas en su mayoría al software, sino que también
existen otros dispositivos electrónicos en los cuales se pueden aplicar los conceptos
y paradigmas de programación en ensamblador o en alto nivel, para aplicaciones
específicas de software y hardware, tales como control de procesos, adquisición de
datos y señales o aplicaciones en tiempo real.
La Unidad de Aprendizaje Sistemas embebidos consta de cuatro unidades
temáticas, cuyo nivel de complejidad irá incrementándose y además seráá
acumulativo. En la unidad uno se introduce al estudiante en el contexto del estado
del arte de los microcontroladores desde una panorámica general. En la unidad dos
se definen y describen conceptos generales respecto a la arquitectura interna que
todo microcontrolador tiene y debe conocerse para ello se sugiere que el docente
defina qué microcontrolador se usará en el curso, considerando la disponibilidad en
el mercado y las aplicaciones que se realicen en las prácticas.
Dado que cada fabricante de microcontroladores tiene sus propias herramientas de
programación, es decir el lenguaje e IDE de programación, la unidad tres aborda los
pormenores de las reglas sintácticas del lenguaje en el cual se trabajará a lo largo
del curso en función del microcontrolador seleccionado, asíí como el aprendizaje del
entorno de programación y las herramientas disponibles para ello.
Finalmente, en la unidad cuatro se integran todos los conocimientos para manipular
en su totalidad todos los recursos con los que cuenta el microcontrolador que se
eligió en la unidad dos y poder realizar la síntesis del conocimiento para dar solución
a diversos problemas y aplicaciones de control de procesos y adquisición de datos
y señales.
Con los conocimientos adquiridos en esta UA, el alumno seráá capaz, no solo de
utilizar la plataforma del microcontrolador elegido para el curso (sea sistema mínimo
o embebido) sino también aventurarse al aprendizaje de nuevas plataformas
basadas en microcontroladores, teniendo como base la experiencia adquirida a lo
largo del curso y la capacidad de elegir la plataforma y recursos necesarios en el
desarrollo de sistemas embebidos acorde con las necesidades específicas de
solución de proyectos.

<!-- Página 5 -->
5
III. Ubicación de la unidad de aprendizaje en el mapa curricular

3
3
3
4
3
3
2
1
1
1
2
1
1
2
4
4
4
6
4
4
4
7
7
7
10
7
7
6
3
3
3
3
3
3
1
3
1
1
1
1
1
1
1
3
1
3
4
4
4
4
4
4
4
4
4
7
7
7
7
7
7
5
7
5
3
3
3
1
3
3
3
0
1
1
1
3
1
1
1
4
4
4
4
4
4
4
4
4
7
7
7
5
7
7
7
4
3
3
1
1
3
3
1
1
1
1
3
3
1
1
3
3
4
4
4
4
4
4
4
4
7
7
5
5
7
7
5
5
3
3
3
1
3
3
3
1
1
1
1
1
3
1
1
1
3
3
4
4
4
4
4
4
4
4
4
7
7
7
5
7
7
7
5
5
3
3
3
3
3
3
3
--
1
1
1
1
1
1
1
**
4
4
4
4
4
4
4
**
7
7
7
7
7
7
7
8
3
2
2
2
2
1
2
1
2
2
2
2
3
2
4
4
4
4
4
4
4
7
6
6
6
6
5
6
Ingeniería de software I
1
1
3
3
4
4
5
5
}
1
3
4
5
6
6

HT
18
HT
20
HT
18
HT
14
HT
21
HT
18
HT
15
HT
9
HT
5
HT
--
HP
6
HP
8
HP
10
HP
14
HP
9
HP
6
HP
13
HP
15+**
HP
15
HP
**
TH
24
TH
28
TH
28
TH
28
TH
30
TH
24
TH
28
TH
24+**
TH
20
TH
**
CR
42
CR
48
CR
46
CR
42
CR
51
CR
42
CR
43
CR
41
CR
25
CR
30
MAPA CURRICULAR DE LA LICENCIATURA DE INGENIERÍA EN COMPUTACIÓN, 2019
Integrativa
profesional
Cálculo II
Circuitos eléctricos
y electrónicos
Transmision de
datos
Álgebra superior
Paradigmas de
programación I
Optativa 2
Tecnologías
computacionales II
Cálculo III
Gestión de
proyectos de
investigación
Inglés 5
Graficación
computacional
Paradigmas de
programación II
Matemáticas
discretas
Electromagnetismo
Sistemas
embebidos
Procesamiento de
imágenes digitales
Proyecto integral
de comunicación
de datos
Proyecto integral
de ingeniería de
software
Ciencia de los
datos
Robótica
Sistemas
operativos
Seguridad de la
información
Tecnologías
computacionales I
PERIODO 9
PERIODO 10
PERIODO 8
Protocolos de
comunicación de
datos
Arquitectura de
redes
Administración de
proyectos
informáticos
30
PERIODO 1
Compiladores
Ingeniería de
software II
Optativa 1
Investigación de
operaciones
Ensambladores
Arquitectura de
computadoras
Inteligencia artificial
Métodos numéricos
Ecuaciones
diferenciales
Bases de datos I
Bases de datos II
PERIODO 2
PERIODO 3
Sistemas digitales
Programación II
PERIODO 5
Ingeniería de
software I
PERIODO 7
PERIODO 4
PERIODO 6
--
--
--
Métodos
estadísticos
P
r
á
c
t
i
c
a

p
r
o
f
e
s
i
o
n
a
l
*
Inglés 6
Sistemas
analógicos
Probabilidad y
estadística
O
P
T
A
T
I
V
A
S
El ingeniero y su
entorno
socioeconómico
Álgebra lineal
Química
Inglés 7
Inglés 8
Cálculo I
Física
Programación I
Geometría analítica
Comunicación y
relaciones humanas
Administración de
recursos
informáticos
Ética profesional y
sustentabilidad
Epistemología
Optativa 3
O

B

L

I

G

A

T

O

R

I

A

S

<!-- Página 6 -->
6

1
1
3
3
4
4
5
5
1
3
4
5
1
1
3
3
4
4
5
5
1
3
4
5
1
1
3
3
4
4
5
5
1
3
4
5
HT: Horas Teóricas
56
HP: Horas Prácticas
24
TH: Total de Horas
80
CR: Créditos
136
Créditos mínimos 21 y máximos 51 por periodo escolar.
* Actividad académica.
70
** Las horas de la actividad académica.
40
Î UA optativa que debe impartirse, cursarse y acreditarse en el idioma inglés.
110
180
Núcleo básico obligatorio.
Núcleo básico optativo
9
3
Núcleo sustantivo obligatorio.
23+**
9
Núcleo integral obligatorio.
32+**
12
Núcleo integral optativo
79
15
18 líneas de seráiación.
PERIODO 1
PERIODO 2
PERIODO 10
PERIODO 9
Núcleo sustantivo
obligatorio: cursar y
acreditar 27 UA
PERIODO 3
PERIODO 4
Núcleo integral
obligatorio: cursar y
acreditar 8 UA + 2*
Núcleo básico
obligatorio: cursar y
acreditar 20 UA
PERIODO 5
PARÁMETROS DEL PLAN DE ESTUDIOS
410
TOTAL DEL PLAN DE ESTUDIOS
58 + Actividades académicas
UA a acreditar
3
UA optativas
55 + 2 Actividades académicas
Créditos
SIMBOLOGÍA
PERIODO 8
Núcleo integral
optativo: cursar y
acreditar 3 UA
Total del núcleo básico:
acreditar 20 UA para
cubrir 136 créditos
Total del núcleo integral:
acreditar 11 UA + 2* para
cubrir de 94 créditos
Total del núcleo
sustantivo: acreditar 27
UA para cubrir 180
créditos
UA obligatorias
Unidad de
aprendizaje
PERIODO 7
Gestión de redes
DISTRIBUCIÓN DE LAS UNIDADES DE APRENDIZAJE OPTATIVAS
PERIODO 6
Computing in
industry
Î
Análisis y diseño
de redes
Tecnologías
emergentes
Visión artificial
Reconocimiento
de patrones
Sistemas
interactivos
Interacción
hombre-máquina
Tópicos de
tecnologías de
datos

<!-- Página 7 -->
7
IV. Objetivos de la formación profesional.
Objetivos del programa educativo:
Son objetivos de la Licenciatura de Ingeniería en Computación, formar
profesionistas que sean capaces de proveer soluciones computacionales
innovadoras y sustentables a los problemas, requerimientos y necesidades
específicas de la sociedad con responsabilidad ética y mediante la aplicación de
metodologías y normas adecuadas en el desarrollo, implantación, optimización,
administración y mantenimiento de sistemas de cómputo, que impliquen el uso o la
integración de hardware, software y comunicación en diferentes plataformas y
dispositivos y desarrollar los aprendizajes y competencias para:

Generales
• Ejercer el diálogo y el respeto como principios de la convivencia con sus
semejantes, y de apertura al mundo.
• Reconocer la diversidad cultural y disfrutar de sus bienes y valores.
• Convivir con las reglas de comportamiento socialmente aceptables, y
contribuir en su evolución.
• Adquirir los valores de cooperación y solidaridad.
• Cuidar su salud y desarrollar armoniosamente su cuerpo; ejercer
responsablemente y de manera creativa el tiempo libre.
• Ampliar su universo cultural para mejorar la comprensión del mundo y del
entorno en que vive, para cuidar de la naturaleza y potenciar sus
expectativas.
• Participar activamente en su desarrollo académico para acrecentar su
capacidad de aprendizaje y evolucionar como profesional con autonomía.
• Asumir los principios y valores universitarios, y actuar en consecuencia.
• Emplear habilidades lingüístico-comunicativas del idioma inglés.
• Evaluar el progreso, integración e incertidumbre de las ciencias, ante la
creciente complejidad de las profesiones.

Particulares
• Crear proyectos de sistemas computacionales a través de la identificación de
necesidades, metodologías ad hoc, teorías de la computación, empleo de
sistemas de programación, mejores prácticas, sistemas electrónicos,
comunicaciones y de sistemas, señales y control, para mejorar la cobertura
y calidad de los serávicios de cómputo de la sociedad y en sectores prioritarios
como la educación, salud y seguridad social.

<!-- Página 8 -->
8
• Evaluar redes de cómputo a través del análisis, el diseño y la administración
de la interconexión de dispositivos en redes de computadoras de área local
y abierta, considerando estáándares y modelos internacionales, para
garantizar el rendimiento óptimo en la transmisión de datos.
• Crear nuevas tecnologías computacionales, empleando tecnologías
emergentes tales como la inteligencia artificial, la visión computacional, el
reconocimiento de patrones, la graficación por computadora, los sistemas
embebidos y la ciencia de los datos; para resolver problemas específicos de
la sociedad y en sectores prioritarios como la educación, salud y seguridad
social.

Objetivos del núcleo de formación:
Proveer al alumno de escenarios educativos para la integración, aplicación y
desarrollo de los conocimientos, habilidades y actitudes que le permitan el
desempeño de funciones, tareas y resultados ligados a las dimensiones y ámbitos
de intervención profesional o campos emergentes de la misma.

Objetivos del área curricular o disciplinaria:
Evaluar sistemas computacionales empleando paradigmas como la teoría de la
computación, la teoría de juegos, la teoría de las bases de datos, las
comunicaciones de datos, la ingeniería de software, tecnologías de vanguardia y
arquitecturas de hardware, para optimizar la cobertura y calidad de los serávicios de
cómputo en las organizaciones de los sectores prioritarios como la educación, salud
y seguridad social, asíí como la creación de aplicaciones específicas.

V. Objetivos de la unidad de aprendizaje.
Ensamblar sistemas basados en microcontroladores integrando componentes
análogos y digitales para la automatización de procesos en tiempo real y/o
tratamiento de datos y señales.

<!-- Página 9 -->
9
VI. Contenidos de la unidad de aprendizaje, y su organización.
Unidad temática 1. Los microcontroladores en sistemas embebidos
Objetivo: Analizar el uso y aplicaciones generales de un microcontrolador,
mediante el estudio del estado del arte de estáos dispositivos digitales, para
entender las diversas aplicaciones en el campo de la automatización y tratamiento
de datos o señales.
Temas:
1.1 Concepto de microcontrolador.
1.2 Diferencias entre microcontroladores y microprocesadores.
1.3 Sistema mínimo: concepto y partes básicas.
1.4 Fabricantes y familias de microcontroladores.
1.5 Fabricantes y familias de tarjetas de desarrollo.
1.6 Aplicaciones generales de los microcontroladores.
1.7 Descripción general de un sistema embebido
1.8 Otros dispositivos programables.

Unidad temática 2. Arquitectura de un microcontrolador
Objetivo: Analizar la arquitectura interna de un microcontrolador, mediante el
estudio de su hoja de especificaciones, para conocer las prestaciones disponibles
en los diferentes contextos de aplicación.
Temas:
2.1 Concepto de arquitectura.
2.2 Arquitecturas CISC y RISC.
2.3 Bloques funcionales.
2.4 Sistema de buses.
2.5 Modelos de ciclos de máquina: Von Neuman y Harvard.
2.6 Modelo y administración de memoria.
2.7 Registros.
2.8 Puertos.
2.9 Descripción específica de periféricos internos.

<!-- Página 10 -->
10
Unidad temática 3. Lenguaje y Entorno de programación para un
microcontrolador
Objetivo: Diferenciar los elementos del lenguaje y entorno de programación de
un microcontrolador, mediante el estudio del paradigma de programación y sus
reglas sintácticas, para la realización de pruebas básicas de operación del
sistema mínimo o embebido.
Temas:
3.1 Descripción de la plataforma de programación
3.2 Manejo básico del entorno de programación
3.3 Ensamblado, enlazado y ejecución de programas.
3.4 Concepto de Directiva.
3.5 Identificadores: etiquetas y variables
3.6 Tipos y definición de datos y constantes simbólicas
3.7 Conjunto de instrucciones y su clasificación
3.8 Partes de una línea de instrucción.
3.9 Esquema general de un programa.
3.10 Tipos y declaración de funciones o procedimientos.
3.11 Pruebas iniciales de programación de un microcontrolador.

Unidad temática 4. Programación de microcontroladores
Objetivo: Analizar el proceso de programación de un microcontrolador, mediante
el estudio y aprendizaje específico de sus prestaciones y configuraciones, para la
solución de problemas de automatización de procesos y tratamiento de datos o
señales.
Temas:
4.1 Modos de direccionamiento.
4.2 Transferencia de datos.
4.3 Uso de funciones o procedimientos.
4.4 Configuración y uso de puertos.
4.5 Concepto de interrupción.
4.6 Configuración y uso de interrupciones.
4.7 Configuración y uso de contadores.
4.8 Configuración y uso de temporizadores
4.9 Configuración y uso de periféricos de adquisición de señales.
4.10 Configuración y uso de periféricos generadores de señales.
4.11 Protocolos de comunicación (UART, SPI, I2C)

<!-- Página 11 -->
11
4.12 Configuración y uso de periféricos de comunicación de datos.
4.13 Interfaces con circuitos analógicos.
4.14 Interfaces con circuitos digitales.
4.15 Aplicaciones integradoras.
4.16 Simulación de circuitos con un microcontrolador.

VII. Acervo bibliográfico
Básico:
Aisa, C. B., (2017), Programación de microcontroladores pic en lenguaje c, 1a ed.,
Alfaomega.
Ferreira, J. C. V., Muriel, E., & Sinsel, M., (2008), Microcontroladores motorolafreescale, Marcombo.
Herrera, P. J. M., (2018), Microcontrolador STM32 Programación y desarrollo, 1a
ed., RA-MA Editorial.
Mackenzie, S., (2007), Microcontrolador 8051, 4a ed., Prentice hall/Pearson.
Palacios, E., Remiro, F., & López, L., (2009), Microcontrolador PIC16F84: Desarrollo
de proyectos. 3a Edición, Alfaomega - Rama.
Pérez, F. E. V., & Areny, R. P., (2007), Microcontroladores: Fundamentos y
aplicaciones con PIC, Alfaomega.
Ruiz Zamarreño C., (2021), Programación de microcontroladores pic paso a paso,
Marcombo-Alfaomega.

Complementario:
Boylestad, R. L., (2018), Electrónica: Teoría De Circuitos Y Dispositivos
Electrónicos, 11a ed., Pearson.
Floyd Thomas L., (2016), Fundamentos de sistemas digitales, Pearson.
Morris M. M., (2015), Diseño Digital, 5a ed., Pearson.
Rafiquzzaman M., (2018), Microcontroller Theory and Applications with the PIC18F,
editorial Wiley.
Tocci, Ronald J., (2017), Sistemas digitales: principios y aplicaciones, 11a ed.,
México: Pearson Education.
