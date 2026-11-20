"""Fichas de residuos de EJEMPLO para la demo.

⚠ Por validar con Asorescatar y la Huerta Ecorazón antes del piloto: qué se recibe, cómo lo
quieren y a dónde va lo que no se recibe. Ninguna regla de aquí es oficial todavía.

Reglas de redacción (las lee el vecino por WhatsApp):
- Texto de opción ≤ 20 caracteres (es un botón); nombre ≤ 21 si va en el menú (fila de lista).
- Máximo 3 opciones por pregunta y 1–2 preguntas por residuo.
- `resultado`: listo (entra a la solicitud; si trae consejo, se muestra: «saca los rotos») · preparar (queda por fuera con el consejo) ·
  no (no va en la ruta) · revision (entra marcado para que el equipo lo confirme).
"""

from __future__ import annotations

from typing import Any


def _op(id_: str, texto: str, resultado: str, consejo: str | None = None) -> dict[str, Any]:
    assert len(texto) <= 20, texto
    d: dict[str, Any] = {"id": id_, "texto": texto, "resultado": resultado}
    if consejo:
        d["consejo"] = consejo
    return d


def _v(id_: str, pregunta: str, *opciones: dict[str, Any]) -> dict[str, Any]:
    assert 2 <= len(opciones) <= 3
    return {"id": id_, "pregunta": pregunta, "opciones": list(opciones)}


_SI = _op("si", "Sí, está listo", "listo")

# (código, nombre, emoji, categoría, acepta, gremio, en_menu, sinónimos, preparación, evitar, alternativa, verificaciones)
RESIDUOS: list[tuple[Any, ...]] = [
    # ------------------------------------------------------------------ reciclables · Asorescatar
    (
        "CARTON", "Cartón", "📦", "reciclable", "si", "ASORESCATAR", True,
        ["carton", "caja", "cajas de carton", "cajita", "empaque de carton", "cartulina"],
        "Limpio, seco y aplanado, sin restos de comida ni grasa.",
        "Cartón mojado, con grasa (cajas de pizza) o con comida.",
        None,
        [_v("seco", "¿Tu cartón está limpio y seco?",
            _SI,
            _op("mojado", "Está mojado", "preparar",
                "Déjalo secar bajo techo y lo pides cuando esté seco. Si tiene grasa o comida, no lo reciben."),
            _op("nose", "No estoy seguro", "revision",
                "Revísalo: debe estar seco al tacto y sin manchas de grasa. Lo marco para que el reciclador lo confirme."))],
    ),
    (
        "PAPEL", "Papel y periódico", "📄", "reciclable", "si", "ASORESCATAR", True,
        ["papel", "hoja", "hojas", "cuaderno", "periodico", "revista", "archivo", "folleto", "libreta", "papel blanco"],
        "Seco y limpio, separado de la basura.",
        "Servilletas, papel higiénico, papel con grasa, plastificado o metalizado.",
        None,
        [_v("limpio", "¿Está seco y sin grasa ni comida?",
            _op("si", "Sí, está limpio", "listo"),
            _op("sucio", "Tiene grasa o comida", "preparar",
                "El papel con grasa o comida no se aprovecha; ese va a la basura. Si solo está húmedo, sécalo primero."))],
    ),
    (
        "PET", "Botellas plásticas", "🧴", "reciclable", "si", "ASORESCATAR", True,
        ["botella", "botellita", "pet", "botella de agua", "botella de gaseosa", "envase de gaseosa", "botella plastica"],
        "Vacías y escurridas; aplástalas para que ocupen menos.",
        "Botellas con líquido o que tuvieron aceite, químicos o veneno.",
        None,
        [_v("vacias", "¿Están vacías y escurridas?",
            _op("si", "Sí, vacías", "listo"),
            _op("no", "Todavía no", "preparar",
                "Vacíalas y escúrrelas; no hace falta lavarlas a fondo ni gastar mucha agua.")),
         _v("quimicos", "¿Alguna tuvo aceite, químicos o veneno?",
            _op("no", "No, ninguna", "listo"),
            _op("si", "Sí, alguna", "listo",
                "Saca esas: no van en la ruta. Las de agua, gaseosa o jugo sí las entregas."))],
    ),
    (
        "PLASTICO", "Plástico de aseo", "🧺", "reciclable", "si", "ASORESCATAR", True,
        ["plastico", "tarro", "envase", "frasco plastico", "shampoo", "champu", "jabon", "detergente", "garrafa",
         "envase de yogurt", "suavizante"],
        "Vacíos y escurridos.",
        "Bolsas sucias, icopor y envases de químicos fuertes.",
        None,
        [_v("vacios", "¿Están vacíos y escurridos?",
            _op("si", "Sí, vacíos", "listo"),
            _op("no", "Todavía no", "preparar", "Vacíalos y escúrrelos; con un enjuague rápido basta."))],
    ),
    (
        "VIDRIO", "Vidrio (botellas)", "🍾", "reciclable", "si", "ASORESCATAR", True,
        ["vidrio", "botella de vidrio", "frasco", "frasco de vidrio", "envase de vidrio", "botella de cerveza",
         "botella de vino"],
        "Enteros, vacíos y sin tapa.",
        "Vidrio roto, espejos, bombillos, vidrio de ventana y vasos.",
        None,
        [_v("enteros", "¿Están enteros, sin romper?",
            _op("si", "Sí, todos enteros", "listo"),
            _op("algunos", "Algunos rotos", "listo",
                "Saca los rotos: envuélvelos en papel grueso, márcalos «vidrio roto» y van con la basura. "
                "Los enteros sí los entregas."),
            _op("rotos", "Todos rotos", "no",
                "El vidrio roto no va en la ruta: envuélvelo en papel grueso, márcalo «vidrio roto» y sácalo con "
                "la basura."))],
    ),
    (
        "METAL", "Latas y metal", "🥫", "reciclable", "si", "ASORESCATAR", True,
        ["lata", "latica", "aluminio", "lata de cerveza", "enlatado", "metal", "chatarra", "olla vieja", "hierro",
         "cobre"],
        "Latas vacías y aplastadas; metal sin restos.",
        "Aerosoles y latas de pintura o químicos.",
        None,
        [_v("vacias", "¿Están vacías?",
            _op("si", "Sí, vacías", "listo"),
            _op("no", "Todavía no", "preparar", "Vacíalas y aplástalas; así ocupan menos.")),
         _v("aerosol", "¿Hay aerosoles o latas de pintura?",
            _op("no", "No", "listo"),
            _op("si", "Sí, hay", "listo",
                "Sepáralos: los aerosoles y la pintura no van en la ruta porque pueden ser peligrosos. "
                "Las demás latas sí las entregas."))],
    ),
    (
        "TETRAPAK", "Cajas de leche y jugo", "🧃", "reciclable", "revision", "ASORESCATAR", False,
        ["tetra pak", "tetrapak", "caja de leche", "caja de jugo", "cajita de jugo"],
        "Vacías, enjuagadas y aplastadas.",
        "Con restos de leche o jugo (huelen mal y dañan el resto).",
        None,
        [],
    ),
    # ------------------------------------------------------------------ orgánicos · Huerta Ecorazón
    (
        "FRUVER", "Frutas y verduras", "🍌", "organico", "si", "ECORAZON", True,
        ["organico", "organicos", "cascara", "concha", "fruta", "verdura", "banano", "platano", "mango", "papa",
         "yuca", "aguacate", "cebolla", "tomate", "restos de fruta", "restos de verdura"],
        "Solo restos crudos de frutas y verduras, en un recipiente con tapa y sin bolsa plástica.",
        "Bolsas, servilletas, plástico o vidrio mezclados.",
        None,
        [_v("separados", "¿Están separados de bolsas, plástico y vidrio?",
            _op("si", "Sí, separados", "listo"),
            _op("no", "Necesito separarlos", "preparar",
                "Sepáralos en un recipiente con tapa, sin bolsa. Cuando estén listos, me escribes."),
            _op("duda", "Tengo una duda", "revision", "Lo marco para que el equipo de la huerta lo revise."))],
    ),
    (
        "CAFE_HUEVO", "Borra de café y huevo", "☕", "organico", "si", "ECORAZON", True,
        ["cafe", "borra", "cuncho", "posos", "cascara de huevo", "cascaras de huevo", "huevo"],
        "Borra de café escurrida y cáscaras de huevo, junto con tus restos de frutas.",
        "Filtros con grapas o bolsitas de té de plástico.",
        None,
        [],
    ),
    (
        "PODA", "Hojas y poda", "🍂", "organico", "si", "ECORAZON", True,
        ["hoja seca", "hojas secas", "poda", "rama", "pasto", "grama", "cesped", "jardin", "hojarasca"],
        "Hojas secas y ramas pequeñas, sin tierra ni basura.",
        "Ramas gruesas o mezcladas con plástico.",
        None,
        [],
    ),
    # ------------------------------------------------------------------ no se reciben en la ruta
    (
        "COMIDA", "Comida cocinada, carne y lácteos", "🍲", "organico", "no", None, False,
        ["comida", "comida cocinada", "sobras", "carne", "pollo", "pescado", "hueso", "leche", "queso", "lacteo",
         "arroz", "grasa de cocina"],
        None,
        "En el compost de la huerta atraen plagas y malos olores.",
        "Van a la basura común, en bolsa cerrada. Si dudas, pregúntale a la huerta.",
        [],
    ),
    (
        "ACEITE", "Aceite de cocina usado", "🛢", "no_aprovechable", "no", None, False,
        ["aceite", "aceite usado", "aceite de cocina", "aceite de freir"],
        None,
        "Nunca por el lavaplatos ni el inodoro: tapa las tuberías y contamina el agua.",
        "Déjalo enfriar, guárdalo en una botella plástica cerrada y llévalo a un punto de recolección de aceite usado.",
        [],
    ),
    (
        "PILAS", "Pilas y baterías", "🔋", "peligroso", "no", None, False,
        ["pila", "bateria", "pilas usadas", "bateria de celular"],
        None,
        "Contienen metales pesados: no van con los reciclables ni con la basura.",
        "Guárdalas en una caja seca y llévalas a un punto posconsumo de pilas (muchos supermercados tienen uno).",
        [],
    ),
    (
        "MEDICAMENTOS", "Medicamentos", "💊", "peligroso", "no", None, False,
        ["medicamento", "remedio", "pastilla", "jarabe", "droga vencida", "medicina", "jeringa", "aguja"],
        None,
        "No van en la ruta ni por el inodoro.",
        "Llévalos a un punto posconsumo de medicamentos; muchas droguerías tienen uno.",
        [],
    ),
    (
        "BOMBILLOS", "Bombillos", "💡", "peligroso", "no", None, False,
        ["bombillo", "foco", "lampara", "tubo fluorescente", "luminaria"],
        None,
        "Algunos tienen mercurio: no los rompas.",
        "Llévalos a un punto posconsumo de bombillos.",
        [],
    ),
    (
        "QUIMICOS", "Químicos, aerosoles y pintura", "☣", "peligroso", "no", None, False,
        ["quimico", "aerosol", "spray", "insecticida", "veneno", "pintura", "thinner", "solvente", "lata de pintura"],
        None,
        "Pueden ser tóxicos o inflamables.",
        "Guárdalos cerrados, lejos de los niños, y pregunta por un punto posconsumo.",
        [],
    ),
    (
        "ELECTRONICOS", "Aparatos eléctricos y electrónicos", "📱", "peligroso", "no", None, False,
        ["celular", "cargador", "computador", "electronico", "electrodomestico", "cable", "televisor", "licuadora"],
        None,
        "No van en la ruta de reciclables.",
        "Llévalos a un punto posconsumo de aparatos eléctricos y electrónicos (RAEE).",
        [],
    ),
    (
        "ICOPOR", "Icopor", "⬜", "no_aprovechable", "no", None, False,
        ["icopor", "poliestireno", "bandeja de icopor", "plato desechable", "vaso desechable"],
        None,
        "Por ahora no se recibe en la ruta.",
        "Si está limpio, guárdalo aparte y pregunta a la coordinación; si tiene comida, va a la basura.",
        [],
    ),
    (
        "SANITARIOS", "Papel higiénico, servilletas y pañales", "🧻", "no_aprovechable", "no", None, False,
        ["papel higienico", "servilleta", "pañal", "panal", "toalla higienica", "tapabocas", "papel de baño"],
        None,
        "No se aprovechan.",
        "Van a la basura común, en bolsa cerrada.",
        [],
    ),
]
