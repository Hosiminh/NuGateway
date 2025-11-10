import json
import random
import time

while True:
    data = {
        "ldr_lux": random.randint(10000, 40000),
        "is_dark": random.choice([True, False]),
        "co2": round(random.uniform(400, 1500), 2),
        "temperature": round(random.uniform(18, 28), 2),
        "humidity": round(random.uniform(40, 80), 2),
        "pm2_5": round(random.uniform(5, 50), 2),
        "pm10": round(random.uniform(10, 100), 2),
        "illumination": round(random.uniform(5000, 40000), 2),
        "air_quality": random.choice(["Mükemmel", "Orta", "Kötü"]),
        "air_quality_score": random.randint(0, 100),
        "weather_status": "Güneşli ve sıcak",
        "pv_voltage": round(random.uniform(16, 19), 2),
        "pv_current": round(random.uniform(3, 7), 2),
        "pv_power": round(random.uniform(48, 133), 2),
        "mppt_status": "Charging",
        "motion_detected": random.choice([True, False]),
        "display_should_be_on": random.choice([True, False]),
        "battery_voltage": round(random.uniform(12, 12.8), 2),
        "battery_current": round(random.uniform(1, 4), 2),
        "battery_power": round(random.uniform(12, 51), 2),
        "battery_soc": random.randint(40, 95),
        "battery_soh": random.randint(85, 100),
        "battery_temp": round(random.uniform(22, 35), 1),
        "discharge_time": random.randint(60, 150),
        "charge_time": random.randint(30, 90),
        "bms_low_power_mode": False
    }
    
    with open('sensors.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Generated data: T={data['temperature']}°C, SOC={data['battery_soc']}%")
    time.sleep(5)