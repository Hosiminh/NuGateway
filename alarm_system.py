import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class AlarmLevel(Enum):
    """Alarm severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alarm:
    """Alarm data structure"""
    level: AlarmLevel
    message: str
    timestamp: str
    sensor: str
    value: float
    threshold: float

class AlarmSystem:
    """Alarm monitoring and notification system"""
    
    def __init__(self, config):
        self.config = config
        self.active_alarms: List[Alarm] = []
        self.alarm_history: List[Alarm] = []
        self.max_history = 100
        
    def check_alarms(self, data: Dict[str, Any]) -> List[Alarm]:
        """Check sensor data against alarm thresholds"""
        new_alarms = []
        
        if not self.config.get('alarm_enabled', True):
            return new_alarms
        
        # Temperature alarms
        temp = data.get('temperature')
        if temp is not None:
            temp_high = self.config.get('temp_alarm_high', 35.0)
            temp_low = self.config.get('temp_alarm_low', 5.0)
            
            if temp > temp_high:
                alarm = Alarm(
                    level=AlarmLevel.WARNING,
                    message=f"Yüksek sıcaklık: {temp}°C (eşik: {temp_high}°C)",
                    timestamp=datetime.now().isoformat(),
                    sensor="temperature",
                    value=temp,
                    threshold=temp_high
                )
                new_alarms.append(alarm)
                
            elif temp < temp_low:
                alarm = Alarm(
                    level=AlarmLevel.WARNING,
                    message=f"Düşük sıcaklık: {temp}°C (eşik: {temp_low}°C)",
                    timestamp=datetime.now().isoformat(),
                    sensor="temperature",
                    value=temp,
                    threshold=temp_low
                )
                new_alarms.append(alarm)
        
        # Humidity alarm
        humidity = data.get('humidity')
        if humidity is not None:
            hum_high = self.config.get('humidity_alarm_high', 85.0)
            if humidity > hum_high:
                alarm = Alarm(
                    level=AlarmLevel.WARNING,
                    message=f"Yüksek nem: {humidity}% (eşik: {hum_high}%)",
                    timestamp=datetime.now().isoformat(),
                    sensor="humidity",
                    value=humidity,
                    threshold=hum_high
                )
                new_alarms.append(alarm)
        
        # CO2 alarm
        co2 = data.get('co2')
        if co2 is not None:
            co2_high = self.config.get('co2_alarm_high', 2000.0)
            if co2 > co2_high:
                alarm = Alarm(
                    level=AlarmLevel.CRITICAL,
                    message=f"Yüksek CO2 seviyesi: {co2} ppm (eşik: {co2_high} ppm)",
                    timestamp=datetime.now().isoformat(),
                    sensor="co2",
                    value=co2,
                    threshold=co2_high
                )
                new_alarms.append(alarm)
        
        # Battery SOC alarm
        soc = data.get('battery_soc')
        if soc is not None:
            soc_low = self.config.get('battery_soc_alarm_low', 20)
            if soc < soc_low:
                alarm = Alarm(
                    level=AlarmLevel.CRITICAL,
                    message=f"Düşük batarya: %{soc} (eşik: %{soc_low})",
                    timestamp=datetime.now().isoformat(),
                    sensor="battery_soc",
                    value=soc,
                    threshold=soc_low
                )
                new_alarms.append(alarm)
        
        # PM2.5 alarm (air quality)
        pm25 = data.get('pm2_5')
        if pm25 is not None:
            pm25_high = 55.0  # Unhealthy threshold
            if pm25 > pm25_high:
                alarm = Alarm(
                    level=AlarmLevel.WARNING,
                    message=f"Yüksek partikül seviyesi (PM2.5): {pm25} µg/m³",
                    timestamp=datetime.now().isoformat(),
                    sensor="pm2_5",
                    value=pm25,
                    threshold=pm25_high
                )
                new_alarms.append(alarm)
        
        # Process new alarms
        for alarm in new_alarms:
            self._add_alarm(alarm)
            self._log_alarm(alarm)
        
        return new_alarms
    
    def _add_alarm(self, alarm: Alarm):
        """Add alarm to active list"""
        # Check if similar alarm already exists
        existing = next((a for a in self.active_alarms 
                        if a.sensor == alarm.sensor and a.level == alarm.level), None)
        
        if not existing:
            self.active_alarms.append(alarm)
            
        # Add to history
        self.alarm_history.append(alarm)
        if len(self.alarm_history) > self.max_history:
            self.alarm_history.pop(0)
    
    def _log_alarm(self, alarm: Alarm):
        """Log alarm to system logger"""
        log_msg = f"[ALARM {alarm.level.value.upper()}] {alarm.message}"
        
        if alarm.level == AlarmLevel.CRITICAL:
            logging.critical(log_msg)
        elif alarm.level == AlarmLevel.WARNING:
            logging.warning(log_msg)
        else:
            logging.info(log_msg)
    
    def clear_alarms(self, sensor: str = None):
        """Clear active alarms for a sensor or all"""
        if sensor:
            self.active_alarms = [a for a in self.active_alarms if a.sensor != sensor]
        else:
            self.active_alarms.clear()
    
    def get_active_alarms(self) -> List[Dict[str, Any]]:
        """Get list of active alarms"""
        return [
            {
                'level': a.level.value,
                'message': a.message,
                'timestamp': a.timestamp,
                'sensor': a.sensor,
                'value': a.value,
                'threshold': a.threshold
            }
            for a in self.active_alarms
        ]
    
    def get_alarm_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alarm history"""
        history = self.alarm_history[-limit:] if limit else self.alarm_history
        return [
            {
                'level': a.level.value,
                'message': a.message,
                'timestamp': a.timestamp,
                'sensor': a.sensor,
                'value': a.value,
                'threshold': a.threshold
            }
            for a in history
        ]