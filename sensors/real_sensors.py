"""
sensors/real_sensors.py
------------------------
Real hardware reads: PCF8591 (AD/DA converter) + DHT22. Function
names match mock_sensors.py.

STATUS: stub. Rig not wired in yet.

PCF8591 @ 0x48 via smbus2: write 0x40 | channel, dummy read, then read.
  AIN0 = light, AIN1 = sound, AIN2 = bed pad, AIN3 = desk pad.
DHT22 = adafruit_dht.DHT22(board.D4), poll at most every 2s,
  catch RuntimeError -> (None, None).
"""

import time
import smbus2
import board
import adafruit_dht
 
PCF8591_ADDRESS = 0x48
 
CHANNEL_LIGHT = 0
CHANNEL_SOUND = 1
CHANNEL_BED_PAD = 2
CHANNEL_DESK_PAD = 3
 
_bus = smbus2.SMBus(1)
_dht = adafruit_dht.DHT22(board.D4)
 
_DHT_MIN_INTERVAL_S = 2.0
_last_dht_read_time = 0.0
_last_dht_reading = (None, None)
 
 
def _read_pcf8591_channel(channel: int) -> float:
    """One raw 0-255 reading from a single PCF8591 analogue channel."""
    _bus.write_byte(PCF8591_ADDRESS, 0x40 | channel)
    _bus.read_byte(PCF8591_ADDRESS)  # dummy read, lets the ADC settle
    return float(_bus.read_byte(PCF8591_ADDRESS))
 
 
def read_bed_pressure_raw() -> float:
    return _read_pcf8591_channel(CHANNEL_BED_PAD)
 
 
def read_desk_pressure_raw() -> float:
    return _read_pcf8591_channel(CHANNEL_DESK_PAD)
 
 
def read_light_level() -> float:
    return _read_pcf8591_channel(CHANNEL_LIGHT)
 
 
def read_sound_level() -> float:
    return _read_pcf8591_channel(CHANNEL_SOUND)
 
 
def read_temperature_humidity():
    """
    Rate-limited to the DHT22's own ~2 second minimum interval - a
    call made sooner than that returns the last reading instead of
    hitting the sensor again. RuntimeError on an actual failed read
    is expected and normal - returns (None, None) rather than raising,
    so it flows through main.py's existing temp_read_ok handling.
    """
    global _last_dht_read_time, _last_dht_reading
 
    now = time.monotonic()
    if now - _last_dht_read_time < _DHT_MIN_INTERVAL_S:
        return _last_dht_reading
 
    try:
        _last_dht_reading = (_dht.temperature, _dht.humidity)
    except RuntimeError as e:
        print(f"[WARN] DHT22 read failed: {e}")
        _last_dht_reading = (None, None)
 
    _last_dht_read_time = now
    return _last_dht_reading