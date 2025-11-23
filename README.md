# Powersoft Amplifier Integration for Home Assistant

Esta integración personalizada permite monitorizar y controlar amplificadores Powersoft a través de su API HTTP y protocolo UDP.

## Características

- ✅ Control de volumen (ganancia) por canal
- ✅ Mute/Unmute de canales individuales
- ✅ Control de polaridad (inversión de fase)
- ✅ Ajuste de delay por canal
- ✅ Monitorización en tiempo real:
  - Temperatura del amplificador
  - Voltaje, corriente y potencia por canal
  - Impedancia de carga
  - Detección de señal
  - Detección de clipping
- ✅ Control de encendido/standby
- ✅ Carga de snapshots/presets
- ✅ Soporte para múltiples canales

## Modelos compatibles

Esta integración ha sido probada con los siguientes modelos de Powersoft:

- Serie Ottocanali (DSP+D)
- Serie X (X4, X8)
- Serie T (T Series DSP+D)
- Serie UNICA (4M, 8M, 1K8, 2K8, 4K8, 8K8)
- Serie MEZZO
- Serie Quattrocanali

**Nota:** Otros modelos con API HTTP pueden funcionar, pero las rutas y características pueden variar según el modelo y firmware.

## Instalación

### HACS (Recomendado)

1. Abre HACS en tu Home Assistant
2. Ve a "Integraciones"
3. Haz clic en el menú de tres puntos (arriba a la derecha)
4. Selecciona "Repositorios personalizados"
5. Añade la URL de este repositorio
6. Busca "Powersoft" e instala

### Manual

1. Copia la carpeta `custom_components/powersoft` en tu directorio `config/custom_components/`
2. Reinicia Home Assistant

## Configuración

1. Ve a **Configuración** → **Dispositivos y servicios**
2. Haz clic en **Añadir integración**
3. Busca "Powersoft"
4. Introduce los datos de conexión:
   - **Host**: Dirección IP del amplificador
   - **Puerto**: Puerto HTTP (por defecto 80)
   - **Usuario** (opcional): Si el amplificador tiene autenticación habilitada
   - **Contraseña** (opcional): Si el amplificador tiene autenticación habilitada

## Entidades creadas

Para cada amplificador Powersoft configurado, la integración creará:

### Media Player (por canal)
- Control de volumen (ganancia)
- Mute/Unmute
- Estado de reproducción
- Atributos adicionales:
  - Ganancia en dB
  - Polaridad
  - Delay
  - Temperatura
  - Impedancia
  - Voltaje, corriente
  - Estado de clipping
  - Presencia de señal

### Sensores
- **Temperatura del amplificador** (°C)
- Por canal:
  - **Voltaje** (V)
  - **Corriente** (A)
  - **Potencia** (W)
  - **Impedancia** (Ω)

### Switches
- **Power**: Encendido/Standby del amplificador
- **Polaridad invertida** (por canal): Inversión de fase

### Controles numéricos
- **Ganancia** (por canal): -80 a 0 dB
- **Delay** (por canal): 0 a 500 ms

## Servicios

### `powersoft.set_gain`
Ajusta la ganancia de un canal específico.

```yaml
service: powersoft.set_gain
data:
  entity_id: media_player.powersoft_channel_1
  channel: 1
  gain: -10.0
```

### `powersoft.set_mute`
Silencia o activa un canal.

```yaml
service: powersoft.set_mute
data:
  entity_id: media_player.powersoft_channel_1
  channel: 1
  mute: true
```

### `powersoft.set_polarity`
Invierte la polaridad de un canal.

```yaml
service: powersoft.set_polarity
data:
  entity_id: media_player.powersoft_channel_1
  channel: 1
  inverted: true
```

### `powersoft.set_delay`
Ajusta el delay de un canal.

```yaml
service: powersoft.set_delay
data:
  entity_id: media_player.powersoft_channel_1
  channel: 1
  delay: 25.5
```

### `powersoft.load_snapshot`
Carga un snapshot/preset guardado.

```yaml
service: powersoft.load_snapshot
data:
  entity_id: media_player.powersoft_channel_1
  snapshot: 1
```

## Ejemplos de automatización

### Apagar el amplificador automáticamente
```yaml
automation:
  - alias: "Apagar amplificador por la noche"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.powersoft_power
```

### Alerta de temperatura alta
```yaml
automation:
  - alias: "Alerta temperatura amplificador"
    trigger:
      - platform: numeric_state
        entity_id: sensor.powersoft_temperature
        above: 70
    action:
      - service: notify.mobile_app
        data:
          message: "¡Temperatura del amplificador alta: {{ states('sensor.powersoft_temperature') }}°C!"
```

### Control de volumen por hora del día
```yaml
automation:
  - alias: "Volumen automático mañana"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: powersoft.set_gain
        data:
          entity_id: media_player.powersoft_channel_1
          channel: 1
          gain: -20.0
```

## API HTTP del amplificador

La integración utiliza principalmente el protocolo HTTP para comunicarse con el amplificador. Los endpoints típicos incluyen:

- `/api/system` - Información del sistema
- `/api/channels` - Estado de los canales
- `/api/channels/{n}/mute` - Control de mute
- `/api/channels/{n}/gain` - Control de ganancia
- `/api/channels/{n}/polarity` - Control de polaridad
- `/api/channels/{n}/delay` - Control de delay
- `/api/power` - Control de encendido
- `/api/snapshots` - Gestión de snapshots

## Protocolo UDP

La integración también soporta el protocolo UDP (puerto 8002) para comandos avanzados que no están disponibles en la API HTTP.

## Troubleshooting

### El amplificador no se detecta
- Verifica que el amplificador esté en la misma red
- Comprueba que el puerto 80 (HTTP) esté accesible
- Verifica que la API HTTP esté habilitada en el amplificador (en algunos modelos se debe habilitar desde ArmoníaPlus)

### Los valores no se actualizan
- Comprueba los logs de Home Assistant para errores
- Verifica que el amplificador responde correctamente navegando a `http://IP_DEL_AMPLIFICADOR` en tu navegador
- Algunos modelos requieren autenticación - asegúrate de configurar usuario y contraseña

### Comandos no funcionan
- Verifica que tu usuario tenga permisos de control en el amplificador
- Algunos amplificadores tienen un modo "Control Lock" que debe estar desactivado
- Comprueba que ArmoníaPlus no esté conectado simultáneamente (puede causar conflictos)

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue o pull request en GitHub.

## Licencia

MIT License

## Créditos

Desarrollado para la comunidad de Home Assistant.
Basado en la documentación oficial de la API de Powersoft.

## Soporte

Si encuentras algún problema o tienes sugerencias, por favor abre un issue en GitHub.

---

**Nota importante:** Esta integración no está afiliada ni respaldada oficialmente por Powersoft. Úsala bajo tu propia responsabilidad.
