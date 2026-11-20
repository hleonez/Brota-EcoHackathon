"""Textos de Brisa. Reglas: frases cortas, tuteo cálido, un emoji como ícono, sin tecnicismos."""

BIENVENIDA = "¡Hola, vecino! 👋 Soy Brisa, de los recicladores y la huerta de Villas de San Pablo.\n¿Cómo te llamas?"
PIDE_NOMBRE_OTRA_VEZ = "Cuéntame tu nombre escribiéndolo, por favor 🙂"
ELIGE_TORRE = "Gracias, {nombre}. ¿En qué torre vives?"
ELIGE_TORRE_TEXTO = "Gracias, {nombre}. Escribe el número de tu torre (por ejemplo: 3)."
TORRE_NO_VALIDA = "No reconocí esa torre. Elige una de la lista o escribe su número 🙂"
PIDE_APTO = "Perfecto, {torre}. ¿Cuál es tu apartamento? (por ejemplo: 402)"
APTO_NO_ENCONTRADO = "No encontré el apartamento {apto} en {torre}. Escríbelo solo con números, por ejemplo 402."
CONSENTIMIENTO = (
    "Gracias, {nombre}. Usamos tu nombre, tu número y tu apartamento ({unidad}) solo para coordinar "
    "la recolección y darte tus puntos.\n¿Estás de acuerdo?"
)
POLITICA = (
    "📄 Solo guardamos tu nombre, tu número de WhatsApp y tu torre y apartamento. No pedimos cédula. "
    "Los usamos para coordinar la recolección, darte puntos y medir el impacto del barrio. "
    "Si nos mandas fotos o audios, una IA (Google Gemini) los revisa para entender qué materiales tienes; "
    "no los guardamos. "
    "Puedes pedir que borremos tus datos cuando quieras escribiendo BORRAR MIS DATOS. "
    "(Ley 1581 de 2012, política {version})"
)
SIN_CONSENTIMIENTO = "Entiendo 💚 Sin tu autorización no podemos registrarte. Si cambias de opinión, escribe «hola»."
REGISTRADO = "¡Listo, {nombre}! 💚 Ya quedaste registrado. Cuando quieras, escribe «hola» y te ayudo."
YA_REGISTRADO = "Ya tenías tu registro hecho 💚"

MENU = "¡Hola, {nombre}! ¿Qué quieres que recojamos?"
MENU_PIE = "Escribe PUNTOS, ESTADO o LIGA"
SOLICITUD_CREADA = "¡Recibido, {nombre}! 💚 Tu recolección de {servicios} quedó registrada ({codigo}). Te aviso quién pasa."
SOLICITUD_ABIERTA = "Ya tienes una solicitud en camino ({codigo}) 🚲 Te aviso cuando sepamos quién pasa."
PUNTOS = "⭐ Tienes {saldo} puntos. Ganas puntos cada vez que tu material llega bien separado."
PUNTOS_DETALLE = "• {modalidad} · {puntos_por_entrega} puntos por entrega · total {total}"
PILOTO_NO = (
    "El piloto todavía no está habilitado para tu unidad 🌱 "
    "Mientras tanto te explico qué se recicla y cómo prepararlo."
)
SIN_SOLICITUDES = "No tienes recolecciones pendientes 🙂 Escribe «hola» para pedir una."
LIGA_POSICION = "🏆 {torre} va de {posicion}.ª en la Liga de Torres este mes ({porcentaje} % de los hogares participan)."
LIGA_NO_DISPONIBLE = "🏆 La Liga de Torres todavía no está disponible. ¡Pronto!"
BORRAR_CONFIRMA = "¿Quieres que borremos tus datos de Brota? Esto cancela tu registro."
BORRAR_OK = "Listo, recibimos tu solicitud para borrar tus datos. La coordinación la atenderá pronto 💚"
BORRAR_CANCELADO = "Perfecto, no borramos nada 💚"
SOLO_BOTONES = "Por ahora entiendo texto y botones 🙂 Muy pronto también audios y fotos. Mientras tanto, escríbeme qué tienes."
ERROR = "Uy, tuve un problema para procesar eso 🙏 Intenta de nuevo en un momento."

SERVICIOS = {"RECICLABLES": "reciclables ♻", "ORGANICOS": "orgánicos 🍌"}

# --------------------------------------------------------------------------- menú y pedido guiado
MENU_SALUDO = "¡{hola}, {nombre}! 👋 Soy Brisa, tu asistente de reciclaje de Brota 🌱\n{frase}\n\n¿En qué te puedo ayudar hoy?"
MENU_CORTO = "¿En qué más te puedo ayudar, {nombre}? 🌱"
MENU_LISTA_PIE = "Puedes escribirme o mandarme una nota de voz 🎤"
FRASES_SALUDO = [
    "Espero que estés muy bien 💚",
    "¡Qué gusto saludarte! 💚",
    "Gracias por ayudar a que el barrio esté más limpio 💚",
    "Cada cosa que separas bien le sirve a los recicladores y a la huerta 💚",
]
P_QUE_TIENES = (
    "♻ ¿Qué vas a entregar? Elige de la lista o escríbelo, por ejemplo: «cajas y botellas».\n"
    "Te digo cómo prepararlo para que el reciclador sí lo pueda llevar."
)
P_OTRO = "Escríbeme qué tienes, por ejemplo «cajas de cartón y cáscaras» 🙂"
P_NO_ENTENDI = "No reconocí ese material 🤔 Elige de la lista o escríbelo de otra forma."
P_ENTENDI = "Entendí: {lista}. ¿Es correcto?"
P_YA_ESTA = "{emoji} {nombre} ya está en tu pedido."
P_LISTO = "✅ {emoji} {nombre}: listo."
P_REVISION = "🔎 {consejo}"
P_PREPARAR = "💡 {consejo}\nPor ahora lo dejo por fuera; cuando esté listo, lo pides."
P_NO_SE_RECIBE = "🚫 {emoji} *{nombre}* no va en la ruta de recolección. {evitar}\n👉 {alternativa}"
P_SIN_CHEQUEO_REVISION = "Lo incluyo para que el equipo confirme si lo recibe."
P_TOCA_OPCION = "Toca una de las opciones de arriba 🙂 o escribe CANCELAR."
P_ALGO_MAS = "¿Tienes algo más para entregar?"
P_RESUMEN = "🌱 Esto vamos a pedir:\n{incluidos}\n📍 {ubicacion}{fuera}\n\n{pregunta}"
P_PREGUNTA_PREFERENCIA = "¿Cuándo podemos pasar?"
P_PREGUNTA_ENVIO = "¿La envío?"
P_PREGUNTA_FRANJA = "🕐 {franja}. ¿La envío?"
P_PIDE_HORARIO = "Escríbeme hoy o mañana y la franja, por ejemplo: mañana 9 a 12."
P_HORARIO_NO = "No entendí esa franja 🙂 Escríbela así: hoy 14 a 17, o mañana 9 a 12."
P_RESUMEN_FUERA = "\n\nQueda por fuera: {lista}. Cuando lo tengas listo, lo pides."
P_RESUMEN_NO_VA = "\n🚫 No va en la ruta: {lista}."
P_NADA_LISTO = "Por ahora no quedó ningún material listo para recoger 🌱{fuera}\nCuando lo prepares, escríbeme y lo pedimos."
P_ENVIADA = "¡Listo, {nombre}! 💚 Tu solicitud {codigo} quedó registrada. Te aviso cuando el equipo confirme quién pasa y cuándo."
P_CANCELADA = "Listo, no envié nada 🌱 Cuando quieras, escribe «hola»."
P_SIN_BORRADOR = "No tengo un pedido pendiente 🙂 Empecemos de nuevo."
P_CORREGIR = "¿Qué quieres cambiar?"
P_INVALIDO = "No pude enviar la solicitud: {mensaje} 🙏"

DUDA_PREGUNTA = (
    "❓ Cuéntame qué material tienes y te digo si se recibe y cómo prepararlo.\n"
    "Por ejemplo: «icopor», «aceite usado» o «cajas de pizza»."
)
DUDA_NO_SE = (
    "Ese material no está en mi lista todavía 🌱 Podría aprovecharse, pero necesito verificar si nuestro "
    "equipo lo recibe. Escríbelo de otra forma o pregúntale al reciclador cuando pase."
)
DUDA_SIGUE = "¿Te ayudo con algo más?"
FICHA_SI = "{emoji} *{nombre}*: ✅ se recibe en la ruta.\n👉 {preparacion}"
FICHA_REVISION = "{emoji} *{nombre}*: 🔎 podría recibirse; el equipo lo confirma al recoger.\n👉 {preparacion}"
FICHA_NO = "{emoji} *{nombre}*: 🚫 no va en la ruta. {evitar}\n👉 {alternativa}"
FICHA_EVITAR = "\n⚠ Evita: {evitar}"

# --------------------------------------------------------------------------- modo coordinación
C_SOLO_PANEL = (
    "¡Hola, {nombre}! 👋 {cuantas}\nLas solicitudes se asignan y se cierran en el panel de coordinación{enlace}. "
    "Por aquí te aviso cada solicitud nueva."
)
C_ALERTA_PANEL = "👉 Asígnala en el panel de coordinación{enlace}."
C_MENU = "¡Hola, {nombre}! 👋 {cuantas}\n¿Qué quieres revisar?"
C_MENU_PIE = "También puedes escribir BANDEJA o ASIGNADAS"
C_LISTA_NUEVAS = "📋 Solicitudes nuevas. Elige una para asignarla:"
C_LISTA_ASIGNADAS = "🚲 Solicitudes asignadas. Elige una para registrar cómo le fue:"
C_SIN_NUEVAS = "✅ No hay solicitudes nuevas por ahora."
C_SIN_ASIGNADAS = "No hay solicitudes asignadas pendientes."
C_SIN_RECOLECTORES = "No hay recolectores activos en tu gremio. Pide a administración que los registre."
C_ELIGE_RECOLECTOR = "{codigo} · {ubicacion}\n¿Quién la recoge?"
C_ELIGE_FRANJA = "¿En qué horario pasa?"
C_LLAMAR = "📞 Llama a {nombre}: {telefono}"
C_RECADO = "📞 Avísale al recolector por llamada o recado."
C_ASIGNADA = "✅ {codigo} asignada a {recolector} ({horario}).\n{llamar}\nYa le avisé al vecino 💚"
C_COMO_LE_FUE = "{codigo} · {ubicacion}\nCuando {recolector} vuelva, dime cómo le fue:"
C_ELIGE_MOTIVO = "¿Por qué no se pudo recoger?"
C_RECOGIDA = "✅ {codigo} registrada como recogida."
C_RECHAZADA = "Registrado: {codigo} no se pudo recoger. Le envié al vecino el consejo para la próxima 📘"
C_ORDEN_CAMBIO = "Esa solicitud ya cambió (otra persona la atendió o ya se cerró). Escribe BANDEJA para ver la actual."
C_ORDEN_NO_ENCONTRADA = "No encontré esa solicitud en tu gremio. Escribe BANDEJA para ver la actual."

ESTADO_ORDEN = {
    "nueva": "recibida, buscando quién pase",
    "asignada": "asignada",
    "recogida": "recogida ✅",
    "rechazada": "no se pudo recoger",
}

# --------------------------------------------------------------------------- IA (audios, fotos, texto libre)
IA_TE_ESCUCHE = "🎤 Te escuché: «{texto}»"
IA_VI = "📸 En la foto veo: {texto}"
IA_PELIGRO = "⚠ {texto}"
IA_NO_ENTENDI_FOTO = "No alcanzo a identificar bien el material 🤔 ¿Me mandas otra foto más de cerca o me escribes qué es?"
IA_NO_ENTENDI_AUDIO = "No alcancé a entender el audio 🙏 ¿Me lo repites o me lo escribes?"
IA_MEDIA_SIN_IA = "Ahora mismo no puedo escuchar audios ni ver fotos 🙏 Escríbeme qué tienes, por ejemplo «cajas y botellas»."
IA_DESCARGA = "No pude abrir ese archivo 🙏 ¿Me lo envías de nuevo o me escribes qué tienes?"
IA_PESADO = "Ese archivo es muy pesado para mí 🙏 Mándame una foto o un audio más corto."
# --------------------------------------------------------------------------- soporte (casos y cancelar)
CASO_QUEJA_PIDE = (
    "Lamento que algo haya salido mal 😔 Cuéntame qué pasó en un mensaje (puede ser nota de voz). Si es sobre una "
    "solicitud, incluye su código, por ejemplo BR-00018."
)
CASO_AYUDA_PIDE = "Claro 🙋 Escríbeme en un mensaje qué necesitas y una persona del equipo te responde por aquí."
CASO_REGISTRADO = "✅ Listo, lo dejé registrado ({codigo}). El equipo de coordinación lo revisa y te responde por aquí."
CANCELAR_NADA = "No tienes solicitudes pendientes por cancelar 🙂"
CANCELAR_CONFIRMA = "¿Cancelo tu solicitud {codigo}? ({detalle})"
CANCELAR_CUAL = "¿Cuál solicitud quieres cancelar?"
CANCELADA = "Listo, cancelé tu solicitud {codigo} ✅ Ya le avisé a la coordinación. Cuando quieras, pides otra."
CANCELAR_NO_SE_PUEDE = "Esa solicitud ya no se puede cancelar: ya fue atendida o cancelada 🙂"
ESTADO_PIE = "\nPara cancelar una, escribe CANCELAR."
