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
REGISTRADO = "¡Listo, {nombre}! 💚 Ya quedaste registrado. Para pedir una recolección, solo escribe «hola»."
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
SOLO_BOTONES = "Por ahora entiendo botones y mensajes de texto 🙂 Pronto también audios y fotos."
ERROR = "Uy, tuve un problema para procesar eso 🙏 Intenta de nuevo en un momento."

SERVICIOS = {"RECICLABLES": "reciclables ♻", "ORGANICOS": "orgánicos 🍌"}

ESTADO_ORDEN = {
    "nueva": "recibida, buscando quién pase",
    "asignada": "asignada",
    "recogida": "recogida ✅",
    "rechazada": "no se pudo recoger",
}
