<p align="center"><img src="custom_components/powersoft/brand/icon@2x.png" width="128" alt="Powersoft"></p>

# Powersoft Amplifiers Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/AvenproTeam/Powersoft-Component.svg)](https://github.com/AvenproTeam/Powersoft-Component/releases)

Integración personalizada para Home Assistant que permite monitorizar y controlar amplificadores Powersoft a través de su API HTTP.

## Características

- ✅ Encendido / standby de la etapa
- ✅ Mute por canal de salida (y de entrada, desactivado por defecto)
- ✅ Ganancia y delay por canal, inversión de polaridad (si el modelo lo expone)
- ✅ Snapshot activo y servicio para cargar snapshots
- ✅ Nombre del altavoz asignado a cada canal
- ✅ **Medidores en vivo** (Socket.IO, igual que la Web App de la etapa): tensión, corriente, potencia, impedancia, reducción de ganancia, temperatura, señal, clip, limitador y fallos
- ✅ Modelo, firmware, número de serie y número de canales detectados automáticamente
- ✅ Entidades «no disponibles» cuando la etapa no responde
- ✅ Logo de Powersoft en Home Assistant (requiere HA 2026.3 o superior)

Probado en campo con una **Quattrocanali 4804 DSP** (firmware 1.12.0.696).

## Modelos compatibles

Esta integración ha sido diseñada para trabajar con:

- Serie Ottocanali (DSP+D)
- Serie X (X4, X8)
- Serie T (T Series DSP+D)
- Serie UNICA (4M, 8M, 1K8, 2K8, 4K8, 8K8)
- Serie MEZZO
- Serie Quattrocanali

**Nota:** Otros modelos con API HTTP pueden funcionar, pero las rutas y características pueden variar según el modelo y firmware.

## Instalación

### HACS (Recomendado)

1. Asegúrate de tener [HACS](https://hacs.xyz/) instalado
2. En HACS, ve a "Integraciones"
3. Haz clic en el menú de tres puntos (esquina superior derecha)
4. Selecciona "Repositorios personalizados"
5. Añade esta URL: `https://github.com/AvenproTeam/Powersoft-Component`
6. Selecciona la categoría "Integration"
7. Busca "Powersoft" en HACS e instala
8. Reinicia Home Assistant

### Manual

1. Descarga la carpeta `custom_components/powersoft` de este repositorio
2. Copia la carpeta en tu directorio `config/custom_components/`
3. Reinicia Home Assistant

## Configuración

1. Ve a **Configuración** → **Dispositivos y servicios**
2. Haz clic en **Añadir integración**
3. Busca "Powersoft"
4. Introduce los datos de conexión:
   - **Host**: Dirección IP del amplificador
   - **Puerto**: Puerto HTTP (por defecto 80)
   - **Usuario / Contraseña** (opcional): Si el amplificador tiene autenticación

La conexión se valida al añadirla, y el modelo y el número de canales se detectan solos. La etapa se identifica por su número de serie, así que si cambia de IP usa **Reconfigurar** en la tarjeta de la integración.

## Cómo se comunica

| Canal | Uso |
|---|---|
| `POST http://<ip>/am` (API Agile) | Lectura y escritura de mute, ganancia, standby, snapshot, altavoces (cada 5 s) |
| Socket.IO `ws://<ip>/socket.io/?EIO=3` | Medidores en vivo (`status-update`: `meters` y `slows`) |

## Entidades creadas

| Entidad | Tipo | Origen |
|---|---|---|
| Power | Switch | `/am` |
| Canal N mute | Switch | `/am` |
| Entrada N mute | Switch (desactivado por defecto) | `/am` |
| Canal N polaridad invertida | Switch (config) | `/am`, si el modelo lo expone |
| Canal N ganancia / delay | Number | `/am` (delay si el modelo lo expone) |
| Snapshot actual | Sensor | `/am` |
| Canal N altavoz | Sensor (diagnóstico) | `/am` |
| Temperatura | Sensor | En vivo |
| Canal N tensión / corriente / potencia / impedancia / reducción de ganancia / temperatura | Sensor | En vivo |
| Canal N señal / clip / limitador | Binary sensor | En vivo |
| Fallo | Binary sensor (diagnóstico) | En vivo |

Si la conexión Socket.IO no está disponible, las entidades en vivo aparecen como «no disponibles» y el resto sigue funcionando.

## Uso

### Ejemplos

```yaml
# Mute del canal 2
action: switch.turn_on
target:
  entity_id: switch.powersoft_192_168_1_50_channel_2_mute

# Ganancia del canal 1 a -12 dB
action: number.set_value
target:
  entity_id: number.powersoft_192_168_1_50_channel_1_gain
data:
  value: -12

# Cargar el snapshot 3
action: powersoft.load_snapshot
data:
  config_entry_id: <id de la integración>
  snapshot: 3
```

## Troubleshooting

### El amplificador no se detecta
- Verifica que el amplificador esté en la misma red
- Comprueba que el puerto 80 (HTTP) esté accesible
- Verifica que la API HTTP esté habilitada (puede requerirse desde ArmoníaPlus)

### Los comandos no funcionan
- Verifica que tu usuario tenga permisos de control
- Algunos amplificadores tienen un modo "Control Lock" que debe estar desactivado
- Comprueba que ArmoníaPlus no esté conectado simultáneamente

### Los medidores en vivo aparecen como «no disponibles»
- Comprueba que la Web App de la etapa (`http://<ip>`) funciona desde la red de Home Assistant: los medidores usan el mismo WebSocket.

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Haz fork del repositorio
2. Crea una rama para tu feature
3. Envía un Pull Request

## Licencia

MIT License

## Soporte

Si encuentras algún problema o tienes sugerencias:
- Abre un [Issue](https://github.com/AvenproTeam/Powersoft-Component/issues)
- Únete a las discusiones

---

**Nota:** Esta integración no está afiliada ni respaldada oficialmente por Powersoft. Úsala bajo tu propia responsabilidad.
