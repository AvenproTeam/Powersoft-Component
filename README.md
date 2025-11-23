# Powersoft Amplifiers Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/AvenproTeam/Powersoft-Component.svg)](https://github.com/AvenproTeam/Powersoft-Component/releases)

Integración personalizada para Home Assistant que permite monitorizar y controlar amplificadores Powersoft a través de su API HTTP.

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
   - **Usuario** (opcional): Si el amplificador tiene autenticación
   - **Contraseña** (opcional): Si el amplificador tiene autenticación

## Entidades creadas

### Media Player (por canal)
- Control de volumen (ganancia en dB)
- Mute/Unmute
- Estado de reproducción

### Sensores
- Temperatura del amplificador (°C)
- Voltaje por canal (V)
- Corriente por canal (A)
- Potencia por canal (W)
- Impedancia por canal (Ω)

### Switches
- Power: Encendido/Standby del amplificador
- Polaridad invertida por canal

### Controles numéricos
- Ganancia por canal: -80 a 0 dB
- Delay por canal: 0 a 500 ms

## Uso

### Control básico

```yaml
# Ajustar volumen del canal 1 al 50%
service: media_player.volume_set
target:
  entity_id: media_player.powersoft_channel_1
data:
  volume_level: 0.5

# Silenciar canal 2
service: media_player.volume_mute
target:
  entity_id: media_player.powersoft_channel_2
data:
  is_volume_muted: true
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

### Necesitas adaptar la API
Este componente usa endpoints genéricos. Si tu modelo de amplificador usa diferentes rutas API, edita el archivo `powersoft_api.py` con los endpoints correctos para tu hardware.

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
