import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class SensorDataLogger:
    """Logger for sensor data with rotation support"""
    
    def __init__(self, log_file: str = "sensor_data.log", max_size_mb: int = 10):
        self.log_file = Path(log_file)
        self.max_size = max_size_mb * 1024 * 1024
        
    def log(self, data: Dict[str, Any]):
        """Log sensor data with timestamp"""
        try:
            # Check file size and rotate if needed
            if self.log_file.exists() and self.log_file.stat().st_size > self.max_size:
                self._rotate()
            
            # Append data with timestamp
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            logging.error(f"Data logging failed: {e}")
    
    def _rotate(self):
        """Rotate log file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_name = self.log_file.with_name(f"{self.log_file.stem}_{timestamp}.log")
            self.log_file.rename(rotated_name)
            logging.info(f"Log rotated to {rotated_name}")
        except Exception as e:
            logging.error(f"Log rotation failed: {e}")

def setup_logging(log_level: str = "INFO", log_file: str = "nugateway.log"):
    """Setup application logging"""
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# Create global sensor data logger
sensor_logger = SensorDataLogger()