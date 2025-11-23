# Powersoft Amplifiers Integration

Integración para Home Assistant que permite monitorizar y controlar amplificadores Powersoft a través de su API HTTP.

## Características

- Control de volumen (ganancia) por canal
- Mute/Unmute de canales individuales
- Monitorización en tiempo real de temperatura, voltaje, corriente y potencia
- Control de encendido/standby
- Soporte para múltiples canales

## Configuración

1. Instala la integración a través de HACS
2. Reinicia Home Assistant
3. Ve a Configuración → Dispositivos y servicios
4. Haz clic en "Añadir integración"
5. Busca "Powersoft"
6. Introduce la IP de tu amplificador

## Modelos compatibles

- Serie Ottocanali (DSP+D)
- Serie X (X4, X8)
- Serie T (T Series DSP+D)
- Serie UNICA
- Serie MEZZO
- Serie Quattrocanali

**Nota:** La API puede variar según el modelo. Puede requerir ajustes en el código.
