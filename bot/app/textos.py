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
MENU_LISTA = "¡Hola, {nombre}! 🌱 ¿En qué te ayudo hoy?"
MENU_LISTA_PIE = "Puedes escribirme lo que necesites."
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
P_RESUMEN = "🌱 Esto vamos a pedir:\n{incluidos}\n📍 {ubicacion}{fuera}\n\n¿La envío?"
P_RESUMEN_FUERA = "\n\nQueda por fuera: {lista}. Cuando lo tengas listo, lo pides."
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
