#!/usr/bin/env python3
"""
Automation Engine - Advanced Rule-Based Automation System
"""
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class AutomationRule:
    """Represents a single automation rule"""
    
    def __init__(self, rule_id: int, name: str, sensor: str, operator: str, 
                 value: float, action_relay: str, action_state: bool, 
                 enabled: bool = True, cooldown: int = 60):
        self.id = rule_id
        self.name = name
        self.sensor = sensor
        self.operator = operator
        self.value = value
        self.action_relay = action_relay
        self.action_state = action_state
        self.enabled = enabled
        self.cooldown = cooldown  # Seconds before rule can trigger again
        self.last_trigger = 0
        self.trigger_count = 0
    
    def evaluate(self, sensor_data: Dict[str, Any]) -> bool:
        """Evaluate if rule condition is met"""
        if not self.enabled:
            return False
        
        # Check cooldown
        if time.time() - self.last_trigger < self.cooldown:
            return False
        
        # Get sensor value
        sensor_value = sensor_data.get(self.sensor)
        if sensor_value is None:
            return False
        
        # Evaluate condition
        try:
            if self.operator == '>':
                return sensor_value > self.value
            elif self.operator == '<':
                return sensor_value < self.value
            elif self.operator == '>=':
                return sensor_value >= self.value
            elif self.operator == '<=':
                return sensor_value <= self.value
            elif self.operator == '==':
                return sensor_value == self.value
            elif self.operator == '!=':
                return sensor_value != self.value
        except Exception as e:
            logger.error(f"Error evaluating rule {self.name}: {e}")
            return False
        
        return False
    
    def trigger(self):
        """Mark rule as triggered"""
        self.last_trigger = time.time()
        self.trigger_count += 1
        logger.info(f"🔔 Rule triggered: {self.name} (count: {self.trigger_count})")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'sensor': self.sensor,
            'operator': self.operator,
            'value': self.value,
            'action_relay': self.action_relay,
            'action_state': self.action_state,
            'enabled': self.enabled,
            'cooldown': self.cooldown,
            'last_trigger': self.last_trigger,
            'trigger_count': self.trigger_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutomationRule':
        """Create rule from dictionary"""
        return cls(
            rule_id=data['id'],
            name=data['name'],
            sensor=data['sensor'],
            operator=data['operator'],
            value=data['value'],
            action_relay=data['action_relay'],
            action_state=data['action_state'],
            enabled=data.get('enabled', True),
            cooldown=data.get('cooldown', 60)
        )


class AutomationEngine:
    """Advanced automation engine with rule management"""
    
    def __init__(self, rules_file: str = 'automation_rules.json'):
        self.rules_file = rules_file
        self.rules: List[AutomationRule] = []
        self.enabled = True
        self.load_rules()
    
    def load_rules(self):
        """Load rules from file"""
        if os.path.exists(self.rules_file):
            try:
                with open(self.rules_file, 'r') as f:
                    data = json.load(f)
                    self.rules = [AutomationRule.from_dict(r) for r in data.get('rules', [])]
                    self.enabled = data.get('enabled', True)
                logger.info(f"✅ Loaded {len(self.rules)} automation rules")
            except Exception as e:
                logger.error(f"Error loading rules: {e}")
                self.rules = []
        else:
            # Create default rules
            self.create_default_rules()
            self.save_rules()
    
    def save_rules(self):
        """Save rules to file"""
        try:
            data = {
                'enabled': self.enabled,
                'rules': [r.to_dict() for r in self.rules]
            }
            with open(self.rules_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved {len(self.rules)} automation rules")
        except Exception as e:
            logger.error(f"Error saving rules: {e}")
    
    def create_default_rules(self):
        """Create default automation rules"""
        self.rules = [
            AutomationRule(
                rule_id=1,
                name='Temperature Fan Control',
                sensor='env_temperature',
                operator='>',
                value=30.0,
                action_relay='fan',
                action_state=True,
                cooldown=300  # 5 minutes
            ),
            AutomationRule(
                rule_id=2,
                name='Dark Light Control',
                sensor='ldr_lux',
                operator='<',
                value=50.0,
                action_relay='led_light',
                action_state=True,
                cooldown=180  # 3 minutes
            ),
            AutomationRule(
                rule_id=3,
                name='Low Battery Protection',
                sensor='mppt_battery_soc',
                operator='<',
                value=20.0,
                action_relay='load3',
                action_state=False,
                cooldown=600  # 10 minutes
            ),
            AutomationRule(
                rule_id=4,
                name='High Temperature Alert',
                sensor='env_temperature',
                operator='>',
                value=35.0,
                action_relay='heater',
                action_state=False,
                cooldown=300
            ),
            AutomationRule(
                rule_id=5,
                name='High CO2 Ventilation',
                sensor='env_co2',
                operator='>',
                value=1000.0,
                action_relay='fan',
                action_state=True,
                cooldown=300
            )
        ]
    
    def add_rule(self, rule: AutomationRule):
        """Add new automation rule"""
        self.rules.append(rule)
        self.save_rules()
        logger.info(f"➕ Added rule: {rule.name}")
    
    def remove_rule(self, rule_id: int):
        """Remove automation rule"""
        self.rules = [r for r in self.rules if r.id != rule_id]
        self.save_rules()
        logger.info(f"➖ Removed rule ID: {rule_id}")
    
    def update_rule(self, rule_id: int, updates: Dict[str, Any]):
        """Update automation rule"""
        for rule in self.rules:
            if rule.id == rule_id:
                for key, value in updates.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                self.save_rules()
                logger.info(f"✏️ Updated rule: {rule.name}")
                return True
        return False
    
    def enable_rule(self, rule_id: int, enabled: bool = True):
        """Enable or disable rule"""
        return self.update_rule(rule_id, {'enabled': enabled})
    
    def process(self, sensor_data: Dict[str, Any], relay_controller) -> List[Dict[str, Any]]:
        """
        Process automation rules and execute actions
        
        Returns:
            List of triggered actions
        """
        if not self.enabled:
            return []
        
        triggered_actions = []
        
        for rule in self.rules:
            if rule.evaluate(sensor_data):
                # Execute action
                try:
                    success = relay_controller.set_relay(rule.action_relay, rule.action_state)
                    if success:
                        rule.trigger()
                        action = {
                            'rule_id': rule.id,
                            'rule_name': rule.name,
                            'relay': rule.action_relay,
                            'state': rule.action_state,
                            'timestamp': datetime.now().isoformat(),
                            'sensor': rule.sensor,
                            'sensor_value': sensor_data.get(rule.sensor)
                        }
                        triggered_actions.append(action)
                        logger.info(
                            f"✅ Automation: {rule.name} → "
                            f"{rule.action_relay} = {'ON' if rule.action_state else 'OFF'}"
                        )
                except Exception as e:
                    logger.error(f"Error executing rule {rule.name}: {e}")
        
        return triggered_actions
    
    def get_active_rules(self) -> List[Dict[str, Any]]:
        """Get list of active rules"""
        return [r.to_dict() for r in self.rules if r.enabled]
    
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get list of all rules"""
        return [r.to_dict() for r in self.rules]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get automation statistics"""
        total_triggers = sum(r.trigger_count for r in self.rules)
        active_rules = sum(1 for r in self.rules if r.enabled)
        
        last_trigger = None
        for rule in self.rules:
            if rule.last_trigger > 0:
                if last_trigger is None or rule.last_trigger > last_trigger:
                    last_trigger = rule.last_trigger
        
        return {
            'enabled': self.enabled,
            'total_rules': len(self.rules),
            'active_rules': active_rules,
            'total_triggers': total_triggers,
            'last_trigger': datetime.fromtimestamp(last_trigger).isoformat() if last_trigger else None
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create automation engine
    engine = AutomationEngine()
    
    # Example sensor data
    sensor_data = {
        'env_temperature': 32.5,
        'env_humidity': 65.0,
        'env_co2': 450.0,
        'ldr_lux': 45.0,
        'mppt_battery_soc': 85
    }
    
    print("\n" + "="*70)
    print("AUTOMATION ENGINE TEST")
    print("="*70)
    
    print(f"\n📊 Statistics:")
    stats = engine.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print(f"\n📋 Active Rules:")
    for rule in engine.get_active_rules():
        print(f"  • {rule['name']}: {rule['sensor']} {rule['operator']} {rule['value']}")
    
    print(f"\n🔍 Testing with sensor data:")
    for key, value in sensor_data.items():
        print(f"  {key}: {value}")
    
    # Mock relay controller
    class MockRelayController:
        def set_relay(self, name, state):
            print(f"  [RELAY] {name} → {'ON' if state else 'OFF'}")
            return True
    
    relay_controller = MockRelayController()
    
    print(f"\n⚡ Processing automation rules...")
    triggered = engine.process(sensor_data, relay_controller)
    
    if triggered:
        print(f"\n✅ {len(triggered)} action(s) triggered:")
        for action in triggered:
            print(f"  • {action['rule_name']}: {action['relay']} → {'ON' if action['state'] else 'OFF'}")
    else:
        print("\n  No rules triggered")
    
    print("\n" + "="*70)