# Estado de la API EcoConecta

Contrato: `0.3-ecoconecta.2`. Implementación en `feat/implementar-api-update`. Sin clave, `POST /v1/ia/interpretar` responde `503` y no llama al proveedor. Con clave, llama a Gemini.

## Qué deben enviar el bot y el panel

La entrada de preferencia es incompatible con `0.3-ecoconecta.1`.

- Dejar de enviar `preferencia_horaria` al crear la solicitud. Enviar una sola alternativa: `preferencia_sin_restriccion: true` sin fechas, o `preferencia_inicio` y `preferencia_fin`.
- Seguir leyendo `preferencia_horaria` como texto derivado. Si las tres columnas vienen nulas, la preferencia no fue capturada.
- `tipo_generador` es de salida (`hogar` o `negocio`) y no otorga permisos.
- Programar con `acuerdo_canal` (`whatsapp`, `llamada` o `presencial`). `acuerdo_observacion` es opcional. Sin franja la orden queda `asignada` y no hereda el horario anterior.
- Cerrar solo una orden `programada`, con `materiales_confirmados`: UUID del catálogo y del mismo gremio. Un rechazo lleva lista vacía. `ocurrido_at` no puede estar en el futuro.
- Aceptar `programada`, `cancelada`, `rechazada` y `finalizada_con_novedades`. Cancelada y rechazada no son recogidas.
- Mostrar `tema` y `version` en educación, y `habilitaciones` en `GET /v1/me`.
- No pedir el directorio `GET /v1/unidades` con admin, fundación o la cuenta del trabajador. El trabajador atiende desde su asignación. En sync, un trabajador solo puede `registrar_resultado_orden`; coordinar sigue pudiendo usar el resto, incluido `programar_orden`.
- Un aviso en outbox con estado `pendiente` no es un mensaje ya enviado por WhatsApp.

Las rutas `/recolectores` se mantienen para no romper referencias. Reciclador y huertero son los perfiles de trabajo.

## Matriz RN

| Regla | Qué queda certificado | Prueba |
| --- | --- | --- |
| RN-01 Separación | Orgánicos van a huerta y huertero; reciclables van a reciclaje y reciclador. El otro gremio no ve la orden | `test_recorrido_oficial` |
| RN-02 Programación | Sin canal, `422`. Sin responsable, `409` en HTTP y en `programar_orden`. Asignar sin franja deja `asignada` | `test_inactivos_programacion_y_sync_rechazan_igual`, `test_recorrido_oficial` |
| RN-03 Asignación | Reasignar cambia el responsable, revoca el acceso anterior y no copia el horario. El contador sube solo cuando cambia la persona | `test_reasignar_no_hereda_horario_ni_acceso` |
| RN-04 Trazabilidad | El pasaporte conserva `orden_programada`, `orden_reprogramada` y una sola `orden_reasignada`. Cancelar no suma recogidas ni puntos | `test_reasignar_no_hereda_horario_ni_acceso`, `test_cancelada_no_cuenta_como_recogida_y_hay_educacion` |
| RN-05 Cierre | El cierre exige programación. Un material de otro gremio responde `422`. Repetir el cierre responde `409` y deja un solo movimiento | `test_recorrido_oficial`, `test_reasignar_no_hereda_horario_ni_acceso` |
| RN-06 Puntos | La recogida acredita una vez, con `detalle_calculo.total` de la regla de demostración (`10`). El valor es propuesta del equipo, no una tarifa aprobada por la Fundación | `test_recorrido_oficial` |
| RN-07 Privacidad | Admin y fundación no listan unidades. Fundación no entra a sync. El resumen agregado no trae celular ni nombre de contacto. El trabajador no programa una orden que no es suya | `test_privacidad_directorio_y_sync`, `test_reasignar_no_hereda_horario_ni_acceso` |
| RN-08 Piloto | Vencida, revocada o inexistente responde `403 PILOT_NOT_ENABLED`. Otro residente de la misma unidad no hereda la habilitación. `revocada_at` queda registrado | `test_piloto_vencido_revocado_y_no_se_hereda`, `test_recorrido_oficial` |

Huerta o huertero inactivos rechazan la asignación. La educación pública devuelve separación, huerta y horarios/rutas, y el admin puede editar el texto con versión.

## Migraciones

`0005` distingue trabajadores y clasifica como `huertero` a los de demostración del gremio de orgánicos: es un supuesto de semilla, no un dato histórico nuevo. `0006` crea el piloto. `0007` vincula cuentas. `0008` incorpora programación. `0009` conserva evidencias y cálculo. `0010` publica contenidos y etiqueta el histórico desconocido como `separacion` y publicado; no se reescribe. `0011` añade huertas, vigencias, ejecutor, asignación y canal; `vigente_desde` se copia de `created_at`. `0012` normaliza preferencia, `tipo_generador`, acuerdo, `resultado_material`, `revocada_at` y vigencia de contenidos.

## Validación

El 20 de noviembre de 2026 la suite completa de `api/tests` terminó con código 0 contra PostgreSQL 18.7 local del Compose de desarrollo. Incluye `upgrade head` sobre una base vacía y sobre una copia del esquema `0004` con filas históricas (`tests/verificar_migracion.py`, invocado por `test_upgrade_vacio_y_desde_el_esquema_anterior`).

Esas comprobaciones usan solo bases cuyo nombre termina en `_test` (`brota_test`, `brota_vacia_test`, `brota_migrate_test`). No se usó la base `brota`. El contenedor publica `127.0.0.1:5432` dentro de WSL; desde Windows ese puerto no se mantuvo accesible, así que la suite corrió dentro de WSL contra el mismo localhost del contenedor. No hay despliegue en nube ni cambios de bot o panel en este cierre.
