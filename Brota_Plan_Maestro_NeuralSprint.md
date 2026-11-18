# Plan Maestro · Brota

> Transcripción editable del PDF original. El contenido se organiza por página para facilitar correcciones.

## Página 1

N NeuralSprint · Equipo de desarrollo · Hackatón 2026
PLAN MAESTRO · ARQUITECTURA · ESTRATEGIA PARA GANAR
Brota.
Lo que separas, brota.
Un mensaje o un toque en WhatsApp. El barrio recicla sin
aprender nada nuevo: la tecnología se esconde y todo queda
registrado.
🌱 Recolección de orgánicos y aprovechables
📍 Villas de San Pablo · Piloto Brisas + corredor comercial
🤝 Fundación Santo Domingo · Asorescatar · Huerta Ecorazón
LA IDEA EN UNA FRASE
«Cero pantallas nuevas»: nadie descarga una app, nadie llena
un formulario y nadie deja su papel. Los residentes usan
WhatsApp, los coordinadores toman foto a su tiquete y la IA
hace el resto.
Preparado para Versión 3 Jornadas de desarrollo
Equipo NeuralSprint 17 de noviembre de 2026 Viernes 20 y sábado 21 de
noviembre

## Página 2

### Cómo leer este documento
Lo escribí desde el rol de coordinador de proyecto y director creativo del equipo. Parte del
informe de levantamiento del Día 1 (visita a la Fundación, al punto de acopio de Asorescatar, a
Brisas de San Pablo y a la huerta Ecorazón) y lo convierte en una propuesta concreta: qué
construimos, con qué, quién lo hace, en qué orden y cómo lo contamos para ganar.
01 La gran idea: «Cero pantallas nuevas» 11 Motor de puntos y Moneda Verde
02 Lo que escuchamos → lo que construimos 12 IA con humano al mando
03 12 ideas «de serie» 13 Conexión débil, seguridad y datos personales
04 La experiencia de cada actor 14 Plan de trabajo, roles y backlog
05 Casos de uso 15 Entregables
06 Arquitectura de la solución 16 Métricas y matriz de alineación
07 Stack tecnológico 17 Riesgos y plan B
08 Flujo de datos 18 El pitch y la demo
09 Modelo de datos y ciclo de una solicitud 19 Hoja de ruta 2027 y sostenibilidad
10 Brisa: guiones de la asistente de WhatsApp
Importante: las métricas de evaluación y el stack obligatorio llegan el 20 de noviembre. Este plan está
pensado para ajustarse ese mismo día en 30 minutos: la arquitectura es modular (los canales, la IA y la base
de datos se pueden cambiar sin rehacer todo) y la sección 16 trae una matriz lista para cruzar con los
criterios reales.
Datos del Día 1 que sostienen todo el plan
FÁCIL 40-50 ≈550 33,9 %
El principio no negociable años tiene el usuario apartamentos en Brisas de la población ve los
del reto típico, estrato 1-2, poca de San Pablo, donde residuos como su
destreza digital arranca el piloto principal problema
ambiental
2 ≈15-20 100 % 60-70
coordinadores con tablet recolectores por gremio, del registro actual está en personas ya están en el
(recicladores y huerta) muchos adultos mayores; papel: borradores, canal de WhatsApp de la
algunos sin WhatsApp libretas, tiquetes, hojas huerta, y crece
de carga

## Página 3

### La gran idea: «Cero pantallas nuevas»
01
La mayoría de equipos va a llegar con lo mismo: una app con registro, contraseña, un
formulario y un mapa. Eso choca con todo lo que vimos en campo. Nuestra apuesta es la
contraria: no pedirle a nadie que cambie sus costumbres. Cada actor sigue usando lo que ya
usa, y el sistema se conecta por detrás.
1 · El residente no descarga nada 2 · El papel no se elimina: se vuelve inteligente
Pide por WhatsApp, que ya tiene instalado. Se Viviana prefiere escribir. Perfecto: sigue llenando
registra una sola vez y después pedir son dos su tiquete de pesaje y le toma una foto. La IA lee
toques: «hola» y un botón (Reciclable, Orgánico o los kilos por material y los convierte en datos. Ella
Los dos). También puede mandar un audio. Como solo confirma con un botón grande. Lo llamamos
respaldo hay una página web de un toque Papel Inteligente.
conectada al mismo sistema.
3 · La red humana se respeta 4 · Cada kilo es evidencia y es valor
La coordinación es por llamadas y recados entre Cada recolección lleva un Pasaporte Circular, un
vecinos, y funciona. La tablet no la reemplaza: le identificador que la sigue desde la solicitud hasta
da una bandeja de recados ordenada, un botón los puntos. Los registros alimentan la Liga de
para llamar y una hoja de ruta imprimible. Los Torres, los puntos y un Certificado Verde
recolectores no necesitan celular ni cuenta: la mensual, que sirve como apoyo documental para
coordinadora registra por ellos. gestionar la tarifa multiusuario con Triple A.
Por qué esta idea nos diferencia en el hackatón
Lo que probablemente harán otros equipos Lo que haremos nosotros
✕ App descargable con registro y contraseña ✓ Cero instalación: WhatsApp con botones (2
✕ Formulario de 5 o 6 campos para pedir toques)
✕ Digitar a mano en la tablet lo que hoy va en ✓ Audio, foto o botón: el usuario elige cómo hablar
papel ✓ Foto al tiquete de papel → datos automáticos
✕ Puntos genéricos sin conexión con el barrio ✓ Recolectores sin celular: la coordinadora registra
✕ Asumir buena conexión a internet por ellos
✕ IA como adorno o promesa de fase 2 ✓ Liga de Torres + canje en la huerta y en los
negocios del corredor
✓ Modo sin señal demostrado en vivo
✓ IA útil desde el día 1, siempre con confirmación
humana
«En Villas de San Pablo nadie tiene que aprender tecnología. La tecnología aprendió
del barrio.»
Frase de cierre propuesta para el pitch.

## Página 4

Nombre y personalidad
Brota Brisa Alternativas
El recurso completo. Viene de La asistente de WhatsApp. Si el equipo prefiere otro:
brotar: lo que el vecino separa Lleva el nombre de la brisa «Retoño», «Cosecha» o «De
vuelve al barrio convertido en barranquillera y de Brisas de Vuelta», con la misma asistente
abono, en plantas de la huerta San Pablo, donde arranca el Brisa. Lo decidimos hoy y no
y en ingresos para los piloto. Habla como una vecina se vuelve a discutir.
recicladores. Una sola palabra, amable: frases cortas, sin
fácil de decir. Lema: «Lo que tecnicismos, con emojis que
separas, brota.» funcionan como íconos (🍌
orgánico, ♻ reciclable).
### Lo que escuchamos → lo que construimos
02
Cada decisión tiene un hallazgo de campo detrás. Esta tabla es oro para el jurado: demuestra
que no inventamos una app, sino que respondimos a lo que dijeron las personas.
Hallazgo del Día 1 Decisión de diseño Funcionalidad en Brota
1. El papel es el sistema Digitalizar sin quitar el papel. La pantalla se Papel Inteligente (foto → datos) y Tiquete
actual (borrador, libreta, parece al tiquete que ya conocen. Vivo: formulario idéntico al tiquete n.º
tiquete, hoja de carga del 38298.
compostador, métrica del
concurso)
2. Baja alfabetización Pocas pantallas, pocos campos, botones Registro único y pedir en 2 toques por
digital; algunos sin grandes, íconos, voz. WhatsApp; máximo 3 botones por
WhatsApp; la mensaje; audios; dictado por voz en la
coordinadora prefiere tablet.
escribir
3. La coordinación es No reemplazar la red: ordenarla. Bandeja tipo recados, botón «Llamar», hoja
humana (llamadas y de ruta imprimible, aviso automático al
recados) residente. El recolector no usa ningún
aparato.
4. La calidad del material Educar antes y en el momento justo. Guía visual sí/no; rechazo con motivo;
importa (contaminado no video de 30 s enviado justo cuando hay un
se paga y daña rechazo.
máquinas)
5. Los negocios de Flujo de volumen y frecuencia, distinto al Ruta fija diaria, botón «Hoy hay más», Sello
comida son el foco de un hogar. Negocio Verde para la vitrina.
orgánico
6. La motivación decide Premiar lo colectivo y lo tangible. Liga de Torres, Moneda Verde, canje por
la adopción (resistencia a abono, plántulas y descuentos en el
separar en casa) corredor.
7. La conectividad es Funcionar con poca o ninguna señal. PWA offline con cola de sincronización;
frágil (el call center cerró WhatsApp liviano; respaldo por SMS o
por caídas de internet) llamada.

## Página 5

8. Los datos son Cada registro se convierte en reporte sin Pasaporte Circular, panel de la Fundación y
evidencia (tarifa trabajo extra. Certificado Verde mensual (apoyo
multiusuario, monitoreo documental; no reemplaza el aforo de la
2027, pagos) empresa de aseo).
Ideas de los huerteros Darles crédito público en el pitch: «esto lo Entrega directa registrada por la
(entrega directa, propusieron ellos». coordinadora de la huerta; abono y
incentivos en especie, plántulas en el catálogo; registro de a
botellas, registro pocos.
progresivo)
Riesgo: datos personales Mínimos datos, consentimiento en el chat. Solo nombre, celular y torre/apto. Sin
(pregunta del público) cédula. Cumplimiento de la Ley 1581 de
2012.
Lo que NO vamos a hacer (y lo decimos en voz alta)
Sin contraseñas para residentes. Sin formularios largos. Si hace Sin castigos que frustren. Un
El número de WhatsApp es la falta un dato, lo pregunta Brisa rechazo da cero puntos y un
identidad. uno por uno, una sola vez. video, nunca puntos negativos.
### 12 ideas «de serie»
03
Ideas para sorprender, ordenadas por impacto. Las etiquetas dicen qué hacemos con cada
una: DEMO funciona en vivo · PITCH se muestra como prototipo o maqueta · FUTURO va en la
hoja de ruta.
01
Pedir en dos toques, sin instalar nada DEMO
El vecino se registra una sola vez con Brisa (nombre, torre y apartamento). Desde ahí, pedir es
escribir «hola» y tocar ♻ Reciclable, 🍌 Orgánico o 🔄 Los dos. Si escoge los dos, ve una sola
solicitud, pero por dentro nacen dos órdenes, una para cada gremio. Sin QR, sin imanes, sin
contraseñas.
Cómo: mensajes interactivos de WhatsApp + página web de un toque como respaldo. Esfuerzo: bajo. En la demo el
jurado lo prueba con su propio celular.
02
Brisa entiende audios y fotos DEMO
«Buenas, tengo unas cajas y unas botellas» en un audio se convierte en una solicitud de reciclable
con cartón y PET. Brisa confirma con un botón antes de enviarla. Así quien no escribe bien también
puede pedir.
Cómo: Whisper para pasar audio a texto + un modelo de lenguaje que devuelve JSON con tipo y materiales.
Esfuerzo: medio.
03
Papel Inteligente: foto al tiquete de pesaje DEMO
La coordinadora llena su tiquete como siempre, le toma foto con la tablet y la IA extrae proveedor,
fecha y kilos por material, con precio según la lista de Asorescatar. Ella revisa y confirma. En la demo
usamos la foto real del tiquete n.º 38298 que tomamos en la visita.
Cómo: modelo multimodal con salida en JSON validado. Esfuerzo: medio. Es el momento «wow» de la presentación.

## Página 6

04
Contador de baldes para la huerta DEMO
En la huerta pesan en baldes. En vez de digitar kilos, botones gigantes «+1 balde», «+½ balde», con
equivalencia configurable (1 balde ≈ X kg). Funciona sin señal.
Esfuerzo: bajo. Muestra que escuchamos a Luis y Bladimiro.
05
Liga de Torres en vivo DEMO
El concurso que Víctor lleva a mano, digitalizado: ranking por porcentaje de hogares que participan
(para que torres pequeñas compitan justo y sin mostrar nombres), mensaje semanal por WhatsApp y
una pantalla en la portería. El premio sigue siendo colectivo, como la silla de ruedas.
Esfuerzo: bajo. Conecta con la motivación colectiva que vimos en Brisas.
06
Pasaporte Circular y Certificado Verde DEMO PITCH
Cada recolección tiene un identificador que la sigue desde la solicitud, la asignación y el pesaje hasta
los puntos: cualquier cifra del informe se puede rastrear hasta su origen. Cada mes, un PDF por
conjunto con kilos aprovechados, compostados y tasa de rechazo. Sirve como apoyo documental
para que la administración gestione la tarifa multiusuario con Triple A; la reducción depende del aforo
que hace la empresa de aseo, no del sistema.
Esfuerzo: bajo-medio. Es el argumento de trazabilidad y de valor para el barrio.
07
Moneda Verde de barrio PITCH
Los puntos se canjean por abono y plántulas de la propia huerta (costo casi cero, ciclo cerrado) y por
descuentos en los negocios del corredor comercial, que a su vez entregan sus orgánicos. El dinero
no sale del barrio: economía circular de verdad.
Esfuerzo: medio (catálogo y canje básico). Se alinea con la línea de inclusión productiva de la Fundación.
08
Educación justo a tiempo DEMO
Si una recolección se rechaza por cartón mojado, Brisa envía en ese momento el video de 30
segundos sobre cómo entregar cartón. Se aprende cuando importa, no con una campaña que nadie
ve.
Esfuerzo: bajo. Grabamos 2 o 3 videos cortos antes del viernes.
09
Modo sin señal en vivo DEMO
En la presentación apagamos el wifi de la tablet, registramos un pesaje, volvemos a encender y se
sincroniza solo. Demuestra en 15 segundos que entendimos por qué cerró el call center.
Cómo: PWA con service worker, IndexedDB y cola con reintentos. Esfuerzo: medio.
10
Ojo Verde: ¿esto se recoge? PITCH
El residente manda una foto y Brisa responde si es orgánico, reciclable o no sirve, con una
explicación corta. La Fundación lo dejó para fase 2; nosotros mostramos que ya es posible, como
sugerencia y nunca como decisión automática.
Esfuerzo: medio. Si sobra tiempo pasa a DEMO.

## Página 7

11
Recolectores sin smartphone PITCH
Para quien no usa WhatsApp: hoja de ruta impresa del día, SMS simple o llamada automática («Rosa,
tienes recolección en Torre 3, apartamento 402, a las 4. Marca 1 para aceptar»). La tecnología se
adapta al recolector, no al revés.
Cómo: PDF de ruta + Twilio (SMS o voz) como opción. Esfuerzo: bajo para la hoja, medio para la llamada.
12
Mapa de calor y botón físico FUTURO
Mapa de solicitudes y puntos críticos reportados con foto (conecta con el proyecto de drones de la
Fundación), predicción de demanda para armar rutas y un botón físico tipo «timbre verde» para
restaurantes. Es la visión 2027 del pitch.
Esfuerzo: alto. No se construye en el hackatón; se muestra en una diapositiva.
### La experiencia de cada actor
04
Seis actores, seis puertas de entrada distintas a un mismo sistema. Los nombres de residentes
y recolectores son personajes de ejemplo para el pitch.
🏠 Carmen · residente de Torre 3, 47 años 🍗 Asadero del corredor comercial
1 2 3 4 1 2 3 4
Escribe Toca ♻ Recibe: Recibe Ruta fija Botón Kilos por Sello
«hola» a Reciclable «Rosa sus diaria a la «Hoy hay negocio Negocio
Brisa pasa hoy puntos y hora de más» si en el Verde y
a las 4 el puesto cierre se llena registro descuento
pm» de su antes canjeable
torre
Gana reputación y clientes; la huerta asegura material
Tiempo para pedir: menos de 10 segundos. Se registró constante.
una sola vez; no instala nada.

## Página 8

📋 Viviana · coordinadora del punto de acopio 🧾 Tiquete Vivo (pantalla de pesaje)
Recibe las solicitudes en una tablet que funciona como su La pantalla de confirmación imita el tiquete físico. Los valores
libreta de recados. Toca la cara del reciclador para asignar y leídos por la IA vienen marcados; los dudosos, en amarillo
el sistema avisa al residente. Para pesar, escribe su tiquete para revisar.
como siempre y le toma foto, o le dicta a la tablet: «Rosa trajo
9 kilos de cartón y 3 de PET». TIQUETE DE PESAJE N.º 38298 02-11-26
Proveedor Rosa M.
Recados de hoy · Reciclables 3 nuevos Cartón 9,0 kg
PET 3,0 kg
Torre 3 · Apto 402
♻ Asignar Archivo ⚠ revisar 1,? kg
Cartón y botellas · hace 5 min
Valor según lista calculado
♻ Torre 1 · Apto 101 Asignar ✓ Confirmar Corregir
🎤 Audio: «unas cajas grandes»
📷 Pesaje Rosa · tiquete Revisar El mismo tiquete digital genera el registro por
Leído por IA · revisar
reciclador que hoy Viviana pasa a mano en casa: le
ahorramos ese trabajo nocturno.
👵 Rosa 👴 Víctor 🧑 Jairo
2 hoy 1 hoy 0 hoy
👵 Rosa · recicladora, sin 🌱 Huerta · coordinadora y 🏛 Fundación y Asorescatar
celular voluntarios
Panel web: kilos por material,
No usa ningún aparato ni tiene Misma tablet, bandeja de usuario, torre, negocio y periodo;
cuenta. Viviana la llama como orgánicos. Pesaje con el contador ingresos de recicladores;
siempre y marca en la tablet de baldes. Entrega directa: el rechazos y causas. Exporta a
«asignado a Rosa». Cuando Rosa vecino llega con sus orgánicos, Excel y genera el Certificado
regresa o avisa, Viviana confirma da su nombre o celular y la Verde. Es lo que necesitan para el
qué se recogió y qué se rechazó. coordinadora lo registra, como monitoreo de 2027.
Si quiere, lleva su hoja de ruta propusieron los huerteros.
impresa. Su ingreso queda
registrado como evidencia de
movilidad social.
Recolectores sin celular: cómo se cierra el ciclo
1 2 3 4 5 6
La solicitud llega Viviana llama a Rosa recoge, sin Rosa avisa: «el Viviana confirma Pesaje del lote en
a la tablet Rosa y marca aparatos 402 bien, el 403 o rechaza en la el acopio
«asignado» mojado» tablet
Decisión clave: si Rosa llega al acopio con el material de seis apartamentos junto, no se puede saber cuántos kilos
eran de cada uno. Por eso, en el piloto, el vecino gana puntos por entrega válida (confirmada sin rechazo) y los kilos
se registran por recolector y por torre. Donde haya alguien con pesa y teléfono en la puerta, como Víctor en Brisas, se
registra también el peso por apartamento. Ver la sección 11.

## Página 9

### Casos de uso
05
Quién hace qué en el sistema. El recolector aparece como actor externo: participa en el
proceso, pero no toca el sistema; la coordinadora registra por él.
Actores
Residente Negocio Coordinadora de Coordinadora de la
Hogar de Brisas. Usa Unidad productiva del reciclaje huerta
WhatsApp (o la web de corredor. Mismo canal, Viviana, Asorescatar. Ecorazón. Tablet.
un toque). más volumen. Tablet.
Recolector (externo) Fundación Administrador Sistema
Reciclador o huertero. Monitoreo, informes, Configura materiales, Brisa, motor de puntos,
Sin celular ni cuenta. certificados. precios, reglas. sincronización, IA.
Matriz de casos de uso por actor
ID Caso de uso Res. Neg. Coord. R Coord. H Recol. Fund. Admin Sist. Prioridad
CU-01 Registrarse (una sola vez) ● ● ○ DEBE
CU-02 Solicitar recolección (reciclable, ● ● ○ DEBE
orgánico o los dos)
CU-03 Solicitar por mensaje de voz ● ● ○ DEBERÍA
CU-04 Consultar estado y puntos ● ● DEBERÍA
CU-05 Ver bandeja de solicitudes del ● ● DEBE
gremio
CU-06 Asignar recolector y franja horaria ● ● ○ ○ DEBE
CU-07 Confirmar o rechazar recolección ● ● ○ DEBE
(con motivo)
CU-08 Registrar pesaje (manual, baldes o ● ● ○ DEBE
foto del tiquete)
CU-09 Registrar entrega directa en la huerta ○ ● ● DEBERÍA
o el acopio
CU-10 Acreditar puntos por entrega ● DEBE
validada
CU-11 Enviar contenido educativo al ○ ○ ● DEBERÍA
rechazar
CU-12 Canjear puntos ● ● ○ ○ PODRÍA
CU-13 Consultar panel e indicadores ○ ○ ● ● DEBE
CU-14 Generar Certificado Verde (PDF) ● ● ○ DEBERÍA
CU-15 Configurar materiales, precios y ● DEBERÍA
reglas de puntos

## Página 10

CU-16 Trabajar sin señal y sincronizar ● ● ● DEBERÍA
CU-17 Imprimir hoja de ruta del día ● ● ○ PODRÍA
● actor principal · ○ participa o recibe el resultado.
Especificación de los casos clave
CU-02 · Solicitar recolección CU-06 · Asignar recolector
Actor: residente o negocio. Precondición: registrado Actor: coordinadora. Precondición: orden NUEVA en
(CU-01). su bandeja.
1.  Escribe «hola» a Brisa. 1.  Abre la bandeja (funciona sin señal).
2.  Brisa muestra 3 botones: Reciclable, Orgánico, Los 2.  Toca la orden y el nombre del recolector.
dos. 3.  Llama o manda el recado, como hoy.
3.  Toca uno. El sistema crea la solicitud con su 4.  Marca la franja («hoy 4-5 p. m.») y la forma de
Pasaporte Circular. aviso.
4.  El sistema crea una orden por gremio y la envía a la 5.  El sistema pasa la orden a ASIGNADA y Brisa avisa
bandeja correspondiente. al residente.
5.  Brisa confirma: «Recibido, te aviso quién pasa».
Alternos: 3a. El recolector no contesta → asigna a otro.
Alternos: 1a. Manda un audio  →  IA lo interpreta  →  Brisa 5a. Sin señal → queda en cola y el aviso sale al
pide confirmar (CU-03). 3a. Ya tiene una solicitud sincronizar.
abierta del mismo tipo  →  Brisa lo avisa y no duplica. 3b. Postcondición: orden ASIGNADA con recolector y
Toca por error → «Cancelar» en el mensaje de franja.
confirmación.
Postcondición: 1 solicitud y 1 o 2 órdenes en estado
NUEVA.
CU-07 · Confirmar o rechazar CU-08 · Registrar pesaje
Actor: coordinadora, con el reporte verbal del Actor: coordinadora. Precondición: material recibido
recolector. en acopio o huerta.
1.  El recolector regresa o llama: «el 402 bien, el 403 1.  Elige cómo registrar: manual, contador de baldes o
estaba mojado». foto del tiquete.
2.  La coordinadora marca cada orden: ✓ Recogida o ✕ 2.  Si es foto, la IA llena el Tiquete Vivo y marca en
Rechazada. amarillo lo dudoso.
3.  Si rechaza, elige el motivo con un toque (mojado, 3.  Revisa kilos aceptados y rechazados por material.
mezclado, contaminado, no reciclable). 4.  Confirma con un toque. Se guarda por recolector y
4.  Sistema: recogida  →  CU-10 (puntos); rechazada  →  por torre.
CU-11 (video).
Alternos: 2a. Foto ilegible → registro manual. 4a. Sin
Regla: nunca se dan puntos sin esta confirmación señal → «pendiente de sincronizar», no cuenta en
humana. informes hasta confirmarse.
### Arquitectura de la solución
06
Arquitectura por capas y desacoplada. Si el viernes la Fundación impone otro lenguaje, otra
base de datos u otro canal, se cambia una pieza sin tocar las demás.

## Página 11

WhatsApp · Web de un PWA Tablet Llamada · Panel web
Brisa toque «Tiquete Vivo»: Papel Fundación,
1 · CANALES Residentes, Respaldo de bandeja, Recolectores Asorescatar,
(puertas de negocios, WhatsApp, asignación, sin celular, vía la Liga de Torres
entrada) huerteros. mismo backend. pesaje. Offline. coordinadora. en pantalla.
Texto, botones,
audio, foto.
▼ webhooks HTTPS · REST / JSON ▼
Gateway de mensajería Orquestador Cola de trabajos
Recibe webhooks de conversacional Reintentos, envíos
2 ·
WhatsApp y SMS; valida firma; Máquina de estados por programados, procesamiento
ORQUESTACIÓN
normaliza. usuario (registro, pedir, de IA asíncrono.
confirmar, puntos).
▼
Solicitudes Enrutamiento Asignación Pesaje Puntos y canje
Crear, estados, Tipo → gremio Recolector, Material, kg, Reglas
historial hora, aviso precio configurables
3 · SERVICIOS DE
DOMINIO
(API central)
Educación Reportes Identidad
Contenidos por motivo Panel, Excel, certificados Unidades, roles,
consentimiento
▼
Voz → texto Intención Visión Resúmenes
4 · INTELIGENCIA
Audios de residentes Texto libre  →  JSON Lectura del tiquete; Informe semanal en
(con humano al
y dictado de (tipo, materiales) clasificación de lenguaje sencillo
mando)
coordinadores residuo
▼
PostgreSQL Almacén de Redis Docker Compose
Datos archivos Cola, sesiones del Todo empaquetado
5 · DATOS E INFRA transaccionales (+ Fotos y audios (MinIO bot, caché para la
PostGIS opcional) o S3), con retención infraestructura de la
Fundación
Principios de arquitectura
Canal agnóstico. El núcleo no sabe si la solicitud vino Offline primero. La tablet guarda todo localmente y
de WhatsApp, de la web o de la tablet. Mañana se sincroniza. Cada operación lleva un identificador único
agrega Telegram, una línea telefónica o un kiosco sin para no duplicar al reintentar.
tocar la lógica.
IA reemplazable. Una interfaz única para «transcribir», Reglas como datos. Puntos, equivalencias de baldes,
«extraer» y «ver». Detrás puede ir un modelo en la precios por material y motivos de rechazo son
nube o uno local (Ollama con un modelo de visión) si la configuración, no código. La Fundación los ajusta sin
Fundación no permite enviar datos afuera. programador.

## Página 12

### Stack tecnológico
07
Elegido con tres criterios: que el equipo ya lo conozca (nadie aprende un lenguaje nuevo en
dos días), que sea liviano de instalar en la infraestructura de la Fundación y que funcione con
conexión débil. Se mencionó Python como posible herramienta definida, así que el núcleo va
en Python. La última columna dice qué hacemos si el viernes nos imponen otra cosa.
Stack por capa
Capa Herramienta Para qué Plan B
Canal del WhatsApp Business Platform Registro único, pedir en 2 Twilio Sandbox para
residente (Cloud API de Meta) con toques, avisos, puntos, audios WhatsApp; o solo la web
mensajes interactivos de botones de un toque
Web de un toque Pantalla del residente dentro de Respaldo si WhatsApp falla o —
la misma PWA no se aprueba
Tablet y panel React + TypeScript + Vite, Bandeja, asignación, Tiquete Si imponen Angular u otro
Tailwind CSS, React Router, Vivo, contador de baldes, framework, son 6
TanStack Query panel Fundación, Liga pantallas: se portan
Modo sin señal vite-plugin-pwa (Workbox) + App en caché, cola local de Sincronizar al abrir la app o
Dexie (IndexedDB) operaciones y sincronización con un botón
Gráficas Recharts Indicadores del panel y Liga de Chart.js
Torres
API central Python 3.12 + FastAPI, Pydantic, Reglas de negocio, webhook Se reescriben endpoints; la
Uvicorn, httpx de WhatsApp, IA, reportes lógica y el modelo se
mantienen
Datos PostgreSQL 16 + SQLAlchemy 2 Solicitudes, órdenes, pesajes, MySQL, Oracle o SQL
+ Alembic (migraciones) libro de puntos, auditoría Server: el modelo es
relacional estándar
Tareas de fondo BackgroundTasks de FastAPI Transcribir audios, leer —
(hackatón)  →  Redis + RQ tiquetes, enviar avisos sin
(operación) bloquear
IA · voz Whisper (API o faster-whisper Audios de residentes y dictado Sin audios: solo botones
local) de la coordinadora
IA · lenguaje y Un modelo multimodal por API, Entender texto libre, leer el Local con Ollama y un
visión con salida JSON validada por tiquete, sugerir tipo de residuo modelo de visión si los
Pydantic datos no pueden salir
Reportes Jinja2 + WeasyPrint (PDF); Certificado Verde, hoja de ruta CSV
openpyxl (Excel) imprimible, exportaciones
Documentación OpenAPI/Swagger automático de Contrato entre frontend, bot y —
API FastAPI backend; entregable técnico
Pruebas Pytest (reglas) + Playwright Puntos una sola vez, sin Pruebas manuales con
(recorrido completo) duplicados al sincronizar, guion
solicitud mixta

## Página 13

Infraestructura Docker Compose; VPS con Demo pública con HTTPS (lo El mismo compose en
Caddy (HTTPS automático); exige WhatsApp) y entrega servidores de la Fundación
cloudflared o ngrok para probar portable
el webhook en local
Herramientas de trabajo del equipo
Diseño Código Gestión Asistentes de código
Figma (pantallas) y GitHub, monorepo, GitHub Projects como Claude Code o Copilot
FigJam (flujos y casos ramas cortas y PR tablero único; para acelerar, si el
de uso). revisado por otra sincronización cada 3 reglamento lo permite.
persona. horas.
Lo que deliberadamente NO usaremos
App nativa (Flutter, React Microservicios, Kubernetes, QR, imanes o carnés. El número
Native). Obliga a instalar desde Kafka. Un monolito modular se de WhatsApp ya identifica al
una tienda y a publicar; la PWA y prueba, despliega y entrega vecino, y los recolectores no
WhatsApp cubren todo. mucho más fácil. tienen celular para escanear.
Estructura del repositorio
brota/
├─ api/ FastAPI · modelos · reglas · reportes
│ ├─ domain/ solicitudes.py, ordenes.py, enrutamiento.py, pesaje.py, puntos.py
│ ├─ ai/ transcribir.py, extraer_intencion.py, leer_tiquete.py
│ ├─ channels/ whatsapp_webhook.py, mensajes.py (plantillas y botones)
│ └─ reports/ certificado.html, hoja_ruta.html
├─ web/ PWA React: /pedir (residente) · /tablet · /panel · /liga
├─ infra/ docker-compose.yml · Caddyfile · .env.example · seeds/
├─ tests/ unit/ (reglas) · e2e/ (Playwright)
└─ docs/ arquitectura, casos de uso, manual por rol, guion del pitch
Verificar el viernes: si el reglamento permite APIs externas (WhatsApp, modelos de IA) y llegar con código o cuentas
preparadas. Si no, lo de miércoles y jueves se limita a diseño, cuentas y contenidos.

## Página 14

### Flujo de datos
08
Qué datos entran, por dónde pasan, dónde se guardan y a quién llegan. Tres vistas: el
contexto general, el recorrido de una solicitud paso a paso y el detalle de cada flujo.
Nivel 0 · Diagrama de contexto
Residente / negocio Coordinadoras
celular con WhatsApp tablet (PWA offline)
bandeja, asignación,
pesajes, rechazos
pedidos, audios llamadas y
avisos, puntos recados
Brota
JSON
WhatsApp (Meta) Recolectores
API central
Cloud API · webhook sin celular · externos
+ base de datos
indicadores, informes,
audio, foto → datos certificado PDF
Servicio de IA Fundación
voz, texto, visión panel web
La línea punteada no pasa por el sistema: el recolector solo habla con la coordinadora, y ella registra.
Recorrido de una solicitud por carriles
**Residente Brisa (WhatsApp) API y base de datos Coordinadora (tablet) Recolector**
1 Escribe «hola» y Recibe el mensaje y
toca ♻ lo envía al webhook
2 Identifica al usuario por
su número. Crea
solicitud BR-00018 y su
orden
3 «Recibido, te Envía la confirmación La orden aparece en la
aviso» bandeja
4 Llama a Rosa y marca Recibe la llamada
«asignado, 4-5 p. m.»
5 «Rosa pasa hoy 4- Envía el aviso Orden  →  ASIGNADA
5 p. m.»
6 Entrega la bolsa Recoge y revisa el
material
7 Orden  →  RECOGIDA o Marca ✓ o ✕ con Reporta al volver
RECHAZADA motivo según lo que
Rosa reporta

## Página 15

8 Guarda pesaje por Pesa el lote (manual, Entrega en el
recolector y torre baldes o foto) acopio
9 «+10 puntos · Envía puntos (o el Acredita puntos en el
Torre 3 va 2.ª» video si hubo libro, una sola vez
rechazo)
Nivel 1 · Detalle de los flujos
N.º Dato que fluye Origen Proceso Destino / almacén
F1 Mensaje, botón o audio Residente vía P1 Recibir y entender D1 Usuarios (identifica por
WhatsApp número)
F2 Audio o foto P1 Servicio de IA  →  JSON De vuelta a P1; archivo en D6
validado
F3 Solicitud (unidad, tipo, P1 P2 Crear y enrutar D2 Solicitudes · D3 Órdenes
canal) (1 o 2)
F4 Orden por gremio D3 P3 Bandeja Tablet de la coordinadora
F5 Asignación (recolector, Coordinadora P3 Asignar y avisar D3 · aviso al residente
franja, forma de aviso)
F6 Reporte verbal del Recolector → P4 Confirmar o rechazar D3 (estado, motivo)
recolector coordinadora
F7 Motivo de rechazo P4 P7 Educación WhatsApp: motivo + video
de 30 s
F8 Pesaje (material, kg Coordinadora P5 Registrar pesaje D4 Pesajes · foto en D6
aceptados y rechazados)
F9 Evento «orden validada» P4 P6 Calcular puntos D5 Libro de puntos · aviso
(reglas de D7)
F10 Operaciones sin señal Tablet (IndexedDB) P8 Sincronizar D3, D4
(idempotente)
F11 Consultas agregadas D2 a D5 P9 Reportes Panel, Excel, Certificado
Verde
D1 Usuarios y unidades D3 Órdenes por gremio D5 Libro de puntos D7 Configuración:
D2 Solicitudes D4 Pesajes D6 Archivos (con materiales, precios,
(Pasaporte) retención) reglas
### Modelo de datos y ciclo de una solicitud
09
Entidades principales
Entidad Campos clave
Conjunto / Torre id, nombre (Brisas de San Pablo), etapa, torre, n.º de viviendas (para normalizar la Liga)
Unidad id, tipo (hogar | negocio), torre, apartamento o dirección, geolocalización opcional

## Página 16

Usuario id, nombre, celular (WhatsApp), unidad, rol (residente, negocio, coordinador, recolector,
admin), consentimiento (fecha, versión)
Gremio recicladores (Asorescatar) | huerteros (huerta Ecorazón); coordinador responsable
Recolector id, gremio, nombre, teléfono de contacto opcional. No tiene cuenta en el sistema
Solicitud id de Pasaporte Circular, unidad, tipo (orgánico, reciclable o los dos), canal de origen, audio o
foto opcional, estado general
Orden (por gremio) id, solicitud, gremio, estado, recolector, franja horaria, forma de aviso (llamada o recado),
motivo de rechazo
Pesaje id, solicitud o entrega directa, proveedor, fecha, líneas (material, kg aceptados, kg rechazados,
motivo), origen (manual | foto IA | dictado | baldes), confirmado por
Material nombre, gremio, precio por kg (lista de Asorescatar), factor de puntos
Movimiento de usuario, unidad, puntos (+/−), regla aplicada, referencia (orden o canje). Las correcciones son
puntos movimientos nuevos; nunca se borra
Canje / Catálogo ítem (abono, plántula, descuento en negocio, mercado), costo en puntos, aliado, existencias
Contenido título, video de 30 s o imagen, material, motivo de rechazo asociado
educativo
Ciclo de vida de una solicitud
NUEVA ENRUTADA ASIGNADA RECOGIDA PESADA PUNTUADA
Llega por Orgánico → Coordinador Coordinadora Pesaje en Puntos al
WhatsApp, QR huerta · elige confirma lo acopio o usuario y a su
→ → → → →
o audio Reciclable → recolector y que reporta el huerta (foto, torre
Asorescatar hora; aviso recolector baldes,
automático manual)
RECHAZADA EDUCACIÓN ENTREGA DIRECTA CANCELADA
Motivo en un toque: Brisa explica el motivo y El vecino lleva sus El usuario o el coordinador
mojado, mezclado, → envía el video de 30 s orgánicos y la la anula
contaminado, no es coordinadora lo registra
reciclable
Regla de oro de la Fundación, en la arquitectura: «lo único que debe preocupar al usuario es solicitar el servicio». Por
eso el usuario solo ve tres momentos (pedí, ya vienen, gané puntos). Todo lo demás pasa entre la API y la tablet.
Endpoints mínimos para el hackatón
POST /webhook/whatsapp entrada de mensajes (texto, botón, audio, imagen)
POST /solicitudes crear; «los dos» → 2 órdenes
GET /solicitudes?gremio=&estado= bandeja del coordinador
POST /solicitudes/{id}/asignar recolector + franja → notifica al residente
POST /solicitudes/{id}/rechazar motivo → dispara contenido educativo
POST /pesajes manual, baldes o dictado
POST /pesajes/desde-foto imagen del tiquete → borrador para confirmar
GET /liga?conjunto=brisas ranking por kg/vivienda
GET /reportes/certificado?conjunto=&mes= PDF del Certificado Verde
POST /sync lote de operaciones offline desde la tablet

## Página 17

### Brisa: guiones de la asistente de WhatsApp
10
Reglas de estilo: frases de una línea, tuteo cálido, máximo 3 botones por mensaje (es el límite
de los botones de respuesta de WhatsApp), un emoji como ícono, nunca palabras técnicas.
A · Primera vez (registro único) B · Asignación y cierre
hola 🚲 Rosa pasa hoy entre 4 y 5 p. m. Ten la
bolsa lista en la puerta.
¡Hola, vecino! 👋 Soy Brisa, de los
recicladores y la huerta de Villas de San 💚 ¡Gracias, Carmen! Tu reciclaje llegó bien
Pablo. ¿Cómo te llamas? separado.
+10 puntos · Tienes 120.
Carmen 🏆 Torre 3 va 2.ª en la Liga de Brisas.
⭐ Mis puntos 🎁 Canjear
Gracias, Carmen. Usamos tu nombre y tu
número solo para coordinar la recolección.
C · Mensaje de voz
¿Estás de acuerdo?
🎤 0:06 «Buenas, tengo unas cajas y unas
Sí, acepto Ver más No
botellas para que me las recojan»
Sí, acepto
Entendí: cartón y botellas ♻. ¿Pido la
recolección?
¿En qué torre y apartamento vives?
Sí, pedir No
Elegir torre
Torre 3 · 402
¡Listo, Carmen! 💚 Ya quedaste registrada.
Para pedir, solo escribe «hola».
D · Rechazo con educación justo a tiempo E · Cualquier «hola» abre el menú
😕 Carmen, Rosa no pudo llevarse el cartón: hola
estaba mojado y así no se puede vender.
¡Hola, Carmen! ¿Qué quieres que
Mira este video de 30 segundos para la recojamos?
próxima 👇
♻ Reciclable 🍌 Orgánico
▶ Cómo entregar el cartón
🔄 Los dos
¿Pedimos de nuevo cuando esté seco?
Escribe PUNTOS para ver tus puntos.
Sí Más tarde
F · Foto (Ojo Verde)
📷 [foto de cáscaras y una bolsa plástica]
Veo cáscaras 🍌 (van a la huerta) y una
bolsa plástica (esa no). Separa la bolsa y te
pido la recolección de orgánico.
Pedir orgánico

## Página 18

Máquina de estados del bot (simplificada)
SIN_REGISTRO CONSENTIMIENTO MENÚ CONFIRMAR ESPERANDO
Pide nombre, torre Acepta tratamiento 3 botones Solo si vino de Avisos automáticos
→ → → →
y apartamento de datos audio, foto o texto de asignación,
libre recogida y puntos
Para los huerteros (que ya reportan cosecha por WhatsApp con peso y foto): el mismo número de Brisa acepta
«reporte de cosecha» desde números autorizados. Responde la pregunta abierta del informe sobre un tercer canal: no
hace falta, se usa el mismo.
### Motor de puntos y Moneda Verde
11
La Fundación dijo que las reglas están por definir y que los equipos pueden proponer.
Proponer reglas claras, justas y configurables es un punto a favor frente al jurado.
Principio 1 Principio 2 Principio 3
Se premia lo validado, no lo Lo colectivo pesa tanto como Nunca puntos negativos. Un
pedido. Así nadie pide lo individual. La torre gana rechazo da cero puntos y una
recolecciones vacías para junta, como en el concurso de lección; la sanción es perder la
sumar puntos. Brisas. racha.
Reglas propuestas (valores de ejemplo, todos configurables)
Regla Valor inicial Por qué
Entrega validada sin rechazo +10 pts Premia la frecuencia y la buena separación.
Por kilo, solo donde se pesa en la +10 pts/kg reciclable Aplica donde hay quien pese (Víctor en Brisas); en el
puerta · +5 pts/kg orgánico resto se premia la entrega válida.
Racha de 4 semanas seguidas -1,5 durante la Crea hábito, que es lo difícil.
semana 5
Rechazo 0 pts + video Educar sin castigar.
3 rechazos en el mes «Tarjeta amarilla»: Sanción leve, como se mencionó que se aceptan
pierde la racha propuestas.
Entrega directa en la huerta +15 pts Ahorra el viaje del carrito; idea de los huerteros.
Liga de Torres % de hogares que Torres de distinto tamaño compiten justo; el ranking no
participan + kg de la muestra nombres ni apartamentos.
torre
Catálogo de canje: el dinero no sale del barrio
🌱 Bolsa de abono 🪴 Plántula 🏪 Descuento en el 🏆 Premio colectivo
Producida por la propia Incentivo en especie corredor Para la torre ganadora:
huerta con los propuesto por los Negocios aliados que silla de ruedas, camilla,
orgánicos que el vecino huerteros. también entregan sus mejora del cuarto de
entregó. orgánicos. basuras.

## Página 19

El círculo completo (para una diapositiva): el hogar separa → el reciclador vende y gana más → la huerta composta →
el abono vuelve al hogar como premio → el negocio del corredor recibe clientes por los descuentos → el conjunto
demuestra buenas prácticas y baja su tarifa de aseo.
¿Cómo se pesa si el recolector no tiene celular?
Opción A · Puntos por entrega válida Opción B · Peso en la puerta (donde haya quien
(recomendada para el piloto) pese)
El vecino gana puntos cuando la coordinadora confirma Si hay alguien con pesa de mano y teléfono, como
su recolección sin rechazo. Los kilos se pesan igual en Víctor en Brisas, que ya mide para el concurso, el peso
el acopio o la huerta, pero por lote: por recolector y por se registra por apartamento y se suman puntos por
torre. Es lo que la Fundación necesita para sus kilo. Se activa por conjunto desde la configuración.
informes y no exige ningún aparato al recolector.
### IA con humano al mando
12
La IA está en todas partes, pero nunca decide sola. Propone, y una persona confirma con un
toque. Esto responde a los riesgos de recolecciones erróneas y gana confianza del jurado.
Uso Entrada → salida Control humano Fase
Audio a solicitud Nota de voz → texto → {tipo, El residente confirma con «Sí, DEMO
materiales} pedir»
Papel Inteligente Foto del tiquete → {proveedor, La coordinadora confirma; DEMO
fecha, líneas kg} campos dudosos en amarillo
Dictado del «Rosa trajo 9 kg de cartón» → Pantalla de confirmación SI HAY TIEMPO
coordinador pesaje
Ojo Verde Foto del residuo → orgánico / Solo sugiere; la validación la PITCH
reciclable / no sirve hace el gremio
Resumen semanal Datos de la semana  →  5 líneas en Lo lee y reenvía el coordinador SI HAY TIEMPO
lenguaje sencillo
Predicción de Historial → franjas y recorridos El coordinador decide FUTURO
demanda y rutas sugeridos

## Página 20

Ejemplo: instrucción para leer el tiquete
Eres un asistente que digitaliza tiquetes de pesaje escritos a mano de
Asorescatar (Barranquilla). Devuelve SOLO JSON válido con este esquema:
{
"numero_tiquete": "string|null",
"fecha": "AAAA-MM-DD|null",
"proveedor": "string|null",
"lineas": [{"material": "uno de: CARTON, ARCHIVO, PET, PLEGADIZA, ...",
"kg": number, "confianza": 0-1}],
"observaciones": "string"
}
Reglas: si un valor no es legible usa null y confianza < 0.6.
No inventes materiales que no estén en la lista. Usa coma o punto decimal
tal como aparezca y conviértelo a número.
Antes del viernes probamos esta instrucción con la foto real del tiquete n.º 38298 y la lista de precios para medir qué tan
bien lee la letra.
Ejemplo: instrucción para entender un mensaje
Clasifica el mensaje de un vecino de Villas de San Pablo que quiere que
recojan sus residuos. Devuelve JSON:
{"intencion": "pedir|puntos|pregunta|otro",
"tipo": "ORGANICO|RECICLABLE|MIXTO|null",
"materiales": ["carton","pet","vidrio","cascaras",...],
"respuesta_corta": "máx. 15 palabras, tono vecino, sin tecnicismos"}
### Conexión débil, seguridad y datos personales
13
Diseñado para conexión débil Datos personales
WhatsApp como canal principal: la app ya está Marco: Ley 1581 de 2012 de protección de datos
instalada, es liviana y guarda los mensajes hasta que personales en Colombia y su reglamentación.
hay señal. Mínimo necesario: nombre, celular, torre y
PWA de la tablet offline: service worker con la app apartamento. No pedimos cédula ni dirección exacta
en caché, IndexedDB para datos y una cola de de negocio si no hace falta.
operaciones que se envía al volver la señal. Consentimiento en el chat con versión y fecha
Idempotencia: cada operación tiene un id único, así guardadas; opción «Ver más» con la política.
un reintento nunca duplica un pesaje. Roles: el coordinador ve solo su gremio; la
Fotos livianas: se comprimen en la tablet a unos Fundación ve reportes agregados.
cientos de KB antes de subir. Retención: audios y fotos se borran después de
Plan de contingencia: SMS o llamada para avisos procesarlos (o a los N días configurables).
críticos; hoja de ruta impresa. Derecho a salir: el usuario escribe «borrar mis
Indicador visible: «Sin señal · 3 registros por datos» y Brisa lo gestiona.
enviar», para dar tranquilidad a la coordinadora.
Seguridad técnica
Webhooks verificados con la Autenticación de la tablet con Secretos en variables de
firma de Meta o Twilio; HTTPS PIN corto y sesión por dispositivo entorno, nunca en el repositorio;
obligatorio. (nada de contraseñas largas para respaldo diario de la base de
la coordinadora). datos.

## Página 21

Riesgo de dependencia de una sola persona por gremio: la tablet admite un segundo usuario de respaldo por gremio,
y todo lo registrado queda en el servidor, no en el dispositivo. Si la tablet se pierde, no se pierde la información.
### Plan de trabajo, roles y backlog
14
Roles del equipo (para 5 personas)
Rol Responsable de Entregable del sábado
1 · Líder de producto y Prioridades, cruce con las métricas del viernes, Pitch ensayado 3 veces, video de
pitch guion, demo, ritmo del equipo y decisiones respaldo, matriz de alineación.
rápidas.
2 · Backend y datos API, modelo de datos, enrutamiento, puntos, Liga, API desplegada con datos semilla
reportes y certificado PDF, despliegue. de Brisas.
3 · Bot e IA Webhook de WhatsApp, máquina de estados, Brisa funcionando de punta a punta
audios, lectura de tiquete, prompts. en el celular del jurado.
4 · Frontend PWA de la tablet (bandeja, asignar, Tiquete Vivo, Tablet y panel listos para presentar.
baldes, offline) y panel de la Fundación.
5 · UX, contenido y Textos de Brisa, íconos, videos de 30 s, prueba Videos, textos aprobados,
validación con una persona de 50+ años, diseño de las evidencia de prueba con usuario
diapositivas. real.
Si son 3 personas: (1+5) producto y UX · (2+3) backend, bot e IA · (4) frontend. Si son 4: se unen 1 y 5.
Cronograma
Mar 17 · noche
Horarios exactos por confirmar: el informe deja
Leer este plan juntos (30 min). Elegir nombre, roles y
pendiente la agenda de las jornadas. Los bloques se
alcance. Crear repositorio y tablero.
ajustan cuando la publiquen.
Mié 18
Wireframes de la tablet y del panel. Guion completo de
Rituales de equipo
Brisa. Digitar la lista de precios y las torres de Brisas
como datos semilla. Crear cuentas: Meta for Sincronización de 10 min cada 3 horas: qué terminé, qué
Developers (número de prueba de WhatsApp), llave del sigue, qué me bloquea.
modelo de IA, VPS con dominio y HTTPS. Una sola fuente de verdad: el tablero. Lo que no está ahí
no se hace.
Jue 19
Regla de los 45 minutos: si algo se traba más de 45 min,
Probar prompts con la foto del tiquete y con audios
se pide ayuda o se cambia a plan B.
reales. Grabar 2 o 3 videos de 30 s. Esqueleto de
Integración temprana: unir el código por lo menos cada
diapositivas. Lista de preguntas para los organizadores.
medio día, nunca al final.
Vie 20 · mañana Hora de corte: después del congelamiento solo se
Llegan las métricas. Reunión de 30 min: cruzar corrigen errores y textos.
criterios con la matriz (sección 16) y ajustar el backlog.
Preguntas para los organizadores el viernes
Luego: modelo de datos, API base, webhook del bot,
bandeja de la tablet. ¿Se puede llegar con código o cuentas preparadas?
¿Se aceptan APIs externas (WhatsApp, modelos de IA) en
Vie 20 · tarde
el prototipo?
Hilo de acero: pedir por WhatsApp → aparece en la
tablet → asignar → el residente recibe el aviso. Aunque ¿El entregable debe correr ya en su infraestructura o
se vea feo, debe funcionar completo. basta una demo desplegada?

## Página 22

Vie 20 · noche ¿Podemos usar la foto del tiquete y la lista de precios en
Pesaje (manual y baldes), Papel Inteligente, rechazo la presentación?
con video. Hito: demo completa de punta a punta. ¿Cuánto dura el pitch y hay demo en vivo?
Sáb 21 · mañana
Puntos, Liga de Torres, panel, Certificado Verde,
audios. Prueba con una persona mayor y ajustes de
textos y tamaños.
Sáb 21 · mediodía
Congelar funcionalidades. Desplegar, grabar el video
de respaldo, cargar datos de demo realistas.
Sáb 21 · tarde
Ensayar el pitch 3 veces con cronómetro. Practicar
preguntas difíciles. Presentar.
Backlog priorizado (MoSCoW)
Prioridad Historias
DEBE Pedir por WhatsApp con botones (incluye «Los dos») · Registro único · Enrutamiento automático
por tipo · Bandeja del coordinador y asignación · Aviso al residente · Pesaje manual y contador de
baldes · Rechazo con motivo · Reporte básico por usuario y torre · Consentimiento de datos
DEBERÍA Papel Inteligente (foto al tiquete) · Puntos y «Mis puntos» · Liga de Torres · Certificado Verde PDF ·
Audios · Video educativo al rechazar · Modo offline de la tablet
PODRÍA Ojo Verde (foto del residuo) · Mapa de solicitudes · SMS o llamada al recolector · Hoja de ruta
imprimible · Canje desde el chat · Dictado del coordinador · Resumen semanal con IA
NO AHORA Botón físico IoT · Predicción de demanda · Integración real con Triple A · Pagos a recicladores
### Entregables
15
Dos listas: lo que debemos tener listo al llegar el viernes 20 y lo que entregaremos al cierre del
sábado 21. Los entregables oficiales llegan con el reto el viernes; esta lista es nuestra
propuesta y se ajusta ese día.
Para llegar listos el viernes 20 (preparación del 17 al 19)
**Entregable Responsable Está listo cuando…**
E1 Documento de propuesta (este plan Líder de producto Todo el equipo lo leyó y aprobó nombre,
maestro) roles y alcance «DEBE».
E2 Prototipo navegable en Figma: chat de UX y contenido Las 4 pantallas se pueden recorrer con clics.
Brisa (registro y pedir), bandeja de la
tablet, Tiquete Vivo, panel de la
Fundación
E3 Guion conversacional de Brisa: todos UX + Bot e IA Se leyó en voz alta con una persona de más
los mensajes, botones y respuestas de de 50 años y lo entendió.
error

## Página 23

E4 Modelo de datos y contrato de la API Backend Tablas y endpoints acordados entre
(borrador OpenAPI) backend, frontend y bot.
E5 Diagramas: casos de uso, flujo de datos Líder de producto Están en las diapositivas, en versión legible.
y arquitectura
E6 Repositorio con estructura, README y Backend Cualquier integrante lo clona y levanta en
docker-compose base* menos de 10 minutos.
E7 Cuentas y accesos: Meta for Bot e IA El número de prueba envía un mensaje a
Developers con número de prueba, llave nuestros celulares autorizados.
del modelo de IA, VPS con dominio y
HTTPS
E8 Datos semilla: torres de Brisas, Backend CSV revisado (los valores de la lista de
materiales y lista de precios de precios confirmados).
Asorescatar, recolectores ficticios
E9 Prompts probados con la foto real del Bot e IA Anotado qué porcentaje de campos lee bien.
tiquete n.º 38298 y 5 audios de ejemplo
E10 2 o 3 videos educativos de 30 s (cartón, UX y contenido Exportados en MP4 liviano.
plástico, orgánicos)
E11 Esqueleto del pitch y guion de la demo Líder de producto Se recorre en 5 minutos con cronómetro.
E12 Matriz de alineación lista para llenar y Líder de producto Impresas para la reunión del viernes por la
preguntas para los organizadores mañana.
* Solo si el reglamento permite llegar con código preparado. Si no, E6 queda en diseño y todo lo demás sigue igual.
Entregables del hackatón (cierre del sábado 21)
**Entregable Contenido mínimo**
F1 Prototipo funcional desplegado URL de la tablet y el panel + número de WhatsApp de prueba.
Recorrido completo: pedir → asignar → confirmar → pesar → puntos
→ panel.
F2 Repositorio de código Código fuente, README de instalación, docker-compose, datos de
demo, pruebas básicas.
F3 Documentación técnica Arquitectura, modelo de datos, API (Swagger), casos de uso y flujo
de datos.
F4 Manual de una página por rol Residente, coordinadora y Fundación, con capturas y lenguaje
sencillo.
F5 Presentación y video de respaldo Diapositivas del pitch + video de 90 s de la demo por si falla internet.
F6 Evidencia de validación Prueba con una persona mayor (video corto o fotos con su permiso)
y qué se ajustó después.
F7 Ejemplos de salida Certificado Verde en PDF, exportación a Excel y hoja de ruta
imprimible con datos de demo.
Regla del equipo: F1 manda sobre todo lo demás. Un recorrido completo que funciona vale más que diez pantallas
sueltas.

## Página 24

### Métricas y matriz de alineación
16
Indicadores del producto (propuestos para el piloto)
Valores meta de ejemplo para discutir con la Fundación. Los ajustamos cuando conozcamos su línea base.
⏱ 10 s 30 % 📊 10 % 100 %
Tiempo para pedir una de los ≈550 hogares de de solicitudes de los pesajes del acopio
recolección, en 2 toques Brisas registrados a los 3 rechazadas por calidad al y la huerta registrados en
meses mes 3 digital
kg/mes $ / mes 1 • 80 %
aprovechados y ingreso adicional de los Certificado Verde de solicitudes asignadas
compostados, por torre y recicladores (movilidad mensual por conjunto, el mismo día
por negocio social) listo para la asamblea
Matriz para cruzar con los criterios del jurado (viernes 20)
Los criterios de la izquierda son una hipótesis basada en lo que suelen evaluar los hackatones sociales. Cuando llegue la
matriz oficial, reemplazamos la primera columna y revisamos que cada criterio tenga una prueba concreta en la demo.
Criterio probable Nuestra evidencia Dónde se ve
Facilidad de uso 2 toques en WhatsApp sin instalar nada; audios; Demo en vivo con el celular del jurado +
prueba con persona de 50+ años video de la prueba
Innovación Cero pantallas nuevas; Papel Inteligente; Ojo Foto del tiquete real leída en vivo
Verde; modo sin señal
Impacto social Ingreso de recicladores; huerta productiva; Panel de la Fundación
educación ambiental
Impacto ambiental Kilos desviados; menos puntos críticos; Certificado Verde
compostaje
Viabilidad técnica Arquitectura por capas; Docker; IA local Diapositiva de arquitectura
opcional; stack conocido
Sostenibilidad Lo operan recicladores y huerteros; reglas Hoja de ruta 2027 y estrategia de salida
configurables; tarifa multiusuario como
incentivo económico
Escalabilidad Etapas 1 a 4; nuevos lotes con programa Cierre del pitch
ambiental; Ciudad del Bicentenario
Pertinencia con el Tabla hallazgo → decisión → funcionalidad; Sección 02 en una diapositiva
levantamiento ideas de los huerteros con crédito
### Riesgos y plan B
17
Riesgo Prob. Mitigación

## Página 25

La aprobación o configuración Media Número de prueba de la Cloud API listo desde el miércoles; plan B
de WhatsApp se demora con Twilio Sandbox; plan C con una página web de un botón (mismo
backend).
Recolectores sin celular no Alta No dependen del sistema: la coordinadora registra por ellos y los
pueden registrar nada puntos se dan por entrega válida.
El stack obligatorio es distinto Media Arquitectura desacoplada; el equipo ya domina varios stacks; se
al plan A priorizan lógica y flujos, que no cambian.
No se permiten APIs externas Media Modelo local con Ollama en un portátil con buena RAM o GPU; si no
de IA alcanza, la IA queda como maqueta grabada y el flujo manual
funciona.
La IA lee mal la letra del tiquete Media Campos con baja confianza en amarillo; siempre hay confirmación;
demo con foto ya probada.
Falla el internet durante la Alta Lo convertimos en ventaja: demostramos el modo offline. Además,
presentación video de respaldo y datos locales.
Alcance demasiado grande Alta Hilo de acero el viernes; congelamiento el sábado al mediodía; el
resto se muestra como «visión».
Datos personales mal Baja Mínimos datos, consentimiento, roles, retención corta, datos de demo
manejados ficticios.
Cansancio del equipo Alta Turnos de descanso, comidas planeadas, nadie trabaja solo en algo
crítico.
### El pitch y la demo
18
Una historia, una persona, una demo que el jurado toca con sus manos. Guion pensado para 5
minutos; si es más corto, se recorta el bloque 4.
Tiempo Bloque Qué se dice y qué se muestra
0:00-0:30 Gancho Levantamos un tiquete de papel: «Esta es hoy la base de datos del reciclaje
en Villas de San Pablo». Silencio de dos segundos.
0:30-1:00 Problema con datos 33,9 % ve los residuos como su principal problema ambiental; todo se
registra en papel; recolectores adultos mayores; el call center que cerró por
la conexión.
1:00-1:30 La idea «Cero pantallas nuevas». Presentamos a Carmen (residente) y a Viviana
(coordinadora) y lo que cada una ya usa.
1:30-3:30 Demo en vivo 1) Un jurado escribe «hola» a Brisa desde su celular, se registra y toca ♻
Reciclable. 2) La solicitud aparece en la tablet proyectada; «llamamos» a
Rosa y la asignamos. 3) Suena el celular del jurado: «Rosa pasa a las 4». 4)
Foto al tiquete real → la IA llena los kilos → confirmar. 5) Apagamos el wifi,
registramos baldes, encendemos y sincroniza. 6) Puntos, Liga de Torres y
Certificado Verde.
3:30-4:15 Impacto Evidencia para gestionar la tarifa multiusuario, ingreso para recicladores,
abono que vuelve al barrio, capacidad instalada cuando la Fundación se
retire.

## Página 26

4:15-4:45 Escala Etapas 1 a 4, nuevos lotes con programa ambiental incluido, Ciudad del
Bicentenario. Mapa de calor y botón verde como visión 2027.
4:45-5:00 Cierre «En Villas de San Pablo nadie tiene que aprender tecnología. La tecnología
aprendió del barrio. Porque aquí, lo que separas, brota.»
Checklist de la demo Preguntas difíciles que debemos ensayar
✓ Número de Brisa en una tarjeta grande para que el ¿Y quien no tiene WhatsApp? Llamada, SMS, hoja
jurado escriba impresa y entrega directa en la huerta.
✓ Número del jurado autorizado antes en el número ¿Cuánto cuesta operarlo? Infraestructura de la
de prueba (o un celular nuestro como respaldo) Fundación + mensajería e IA de bajo costo; tenemos
✓ Tablet cargada, con la PWA instalada y datos de opción local sin costo por uso.
demo realistas ¿Qué pasa si la IA se equivoca? Nunca decide sola;
✓ Foto del tiquete probada; copia impresa del tiquete siempre hay confirmación.
en la mano ¿Quién paga los premios? Abono y plántulas de la
✓ Video de respaldo de 90 s por si algo falla huerta, aliados del corredor y el ahorro de la tarifa.
✓ Diapositiva de arquitectura y de «hallazgo → ¿Cómo protegen los datos? Ley 1581, datos
funcionalidad» mínimos, consentimiento, roles.
✓ Video de 20 s de la prueba con una persona mayor
### Hoja de ruta 2027 y sostenibilidad
19
El recurso hace parte de un proyecto de 24 meses (diciembre de 2025 a noviembre de 2027),
con prototipo en noviembre de 2026 y operación de enero a octubre de 2027. Proponemos
esta evolución:
Ene–Mar 2027 Abr–Jun 2027 Jul–Sep 2027 Oct 2027
Arranque. Brisas de Crecer. Resto de la Inteligencia. Ojo Verde Entrega. Informe de
San Pablo y corredor etapa 4 (Mirasol, en producción, mapa operatividad, manual
comercial. Registro Portobelo, Aurora). de puntos críticos, sencillo, coordinadores
asistido en las jornadas Canje activo con rutas sugeridas. autónomos. La
de sensibilización de 5 negocios aliados. Extensión a etapas 1 a 3 Fundación deja
a 8 p. m. Capacitación Primer Certificado con sus hábitos capacidad instalada.
de coordinadores. Verde presentado en propios.
asamblea.
Por qué sobrevive cuando la Fundación se retire
Lo operan quienes ganan con él. Tiene un incentivo económico Es barato de mantener. Pocas
Los recicladores registran porque propio. La tarifa multiusuario piezas, empaquetado en Docker,
eso les da evidencia de su puede bajar el costo de aseo del reglas configurables sin
trabajo; la huerta, porque recibe conjunto; los datos del sistema programador.
material constante. apoyan esa gestión ante la
empresa de aseo.
Siguiente paso inmediato: esta noche, 30 minutos de equipo para aprobar el nombre, los roles y el alcance
«DEBE». Mañana arrancan las tareas del miércoles.

## Página 27

Fuente
Todos los datos del territorio, del proyecto y de los actores provienen del informe interno «NeuralSprint · Informe Día 1 -
Hackatón Villas de San Pablo» (17 de noviembre de 2026). Esta versión incorpora los ajustes discutidos por el equipo: sin QR
ni imanes, recolectores sin celular y aportes de una propuesta alternativa (solicitud mixta, Pasaporte Circular, rechazo
parcial). Las metas, reglas de puntos y criterios de evaluación de este documento son propuestas del equipo para validar con
la Fundación y con la matriz oficial del 20 de noviembre.
