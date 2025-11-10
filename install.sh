#!/bin/bash
# nuGateway Installation and Deployment Script
# Version 2.0

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║         nuGateway Deployment Script v2.0             ║"
    echo "║            Automated Installation Tool               ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        echo "Please run as a regular user (pi recommended)"
        exit 1
    fi
}

check_system() {
    print_step "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    print_step "Python version: $PYTHON_VERSION"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        exit 1
    fi
    
    print_step "System check passed"
}

install_dependencies() {
    print_step "Installing Python dependencies..."
    
    # Upgrade pip
    pip3 install --upgrade pip
    
    # Install requirements
    pip3 install -r requirements.txt --break-system-packages
    
    print_step "Dependencies installed"
}

setup_permissions() {
    print_step "Setting up permissions..."
    
    # Add user to required groups
    sudo usermod -a -G dialout $USER
    sudo usermod -a -G gpio $USER
    
    # Make scripts executable
    chmod +x bms_debugger.py
    chmod +x env_debugger.py
    chmod +x automation_engine.py
    
    print_step "Permissions configured"
    print_warning "You may need to reboot for group changes to take effect"
}

configure_serial() {
    print_step "Configuring serial port..."
    
    # Check if serial is already enabled
    if grep -q "enable_uart=1" /boot/config.txt; then
        print_step "UART already enabled"
    else
        print_warning "UART needs to be enabled"
        echo "Please run: sudo raspi-config"
        echo "Navigate to: Interface Options → Serial Port"
        echo "  - Login shell over serial: NO"
        echo "  - Serial port hardware: YES"
    fi
}

create_config() {
    print_step "Creating configuration files..."
    
    # Create default gateway settings if not exists
    if [ ! -f gateway_settings.json ]; then
        cat > gateway_settings.json << 'EOF'
{
  "gateway_name": "nuGateway",
  "serial_port": "/dev/ttyAMA0",
  "baudrate": 9600,
  "interval": 10,
  "data_bits": 8,
  "stop_bits": 1,
  "parity": "N",
  "location": "",
  "mac_address": "",
  "ip_address": "",
  "enable_auth": false,
  "api_token": "",
  "mqtt_enabled": false,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883,
  "mqtt_topic": "nugateway/sensors",
  "mqtt_username": "",
  "mqtt_password": "",
  "log_level": "INFO",
  "log_file": "nugateway.log",
  "enable_data_logging": true,
  "data_log_file": "sensor_data.log",
  "alarm_enabled": true,
  "temp_alarm_high": 35.0,
  "temp_alarm_low": 5.0,
  "humidity_alarm_high": 85.0,
  "co2_alarm_high": 2000.0,
  "battery_soc_alarm_low": 20,
  "use_simulator": false,
  "modbus_in_flask": false
}
EOF
        print_step "Created gateway_settings.json"
    else
        print_step "gateway_settings.json already exists"
    fi
}

install_service() {
    print_step "Installing systemd service..."
    
    # Copy service file
    sudo cp nugateway.service /etc/systemd/system/
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable service
    sudo systemctl enable nugateway
    
    print_step "Service installed and enabled"
}

run_tests() {
    print_step "Running basic tests..."
    
    # Test imports
    python3 -c "import flask, serial, gpiozero" 2>/dev/null && \
        print_step "All required Python modules are importable" || \
        print_warning "Some Python modules failed to import"
    
    # Test GPIO (if not in mock mode)
    if groups $USER | grep -q gpio; then
        print_step "User is in GPIO group"
    else
        print_warning "User is not in GPIO group yet (reboot required)"
    fi
    
    # Test serial port
    if [ -e /dev/ttyAMA0 ]; then
        print_step "Serial port /dev/ttyAMA0 exists"
    else
        print_warning "Serial port /dev/ttyAMA0 not found"
    fi
}

show_next_steps() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}          Installation Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. ${YELLOW}Reboot the system${NC} (required for group permissions):"
    echo "   sudo reboot"
    echo ""
    echo "2. After reboot, ${YELLOW}start the service${NC}:"
    echo "   sudo systemctl start nugateway"
    echo ""
    echo "3. ${YELLOW}Check service status${NC}:"
    echo "   sudo systemctl status nugateway"
    echo ""
    echo "4. ${YELLOW}View logs${NC}:"
    echo "   sudo journalctl -u nugateway -f"
    echo ""
    echo "5. ${YELLOW}Access web interface${NC}:"
    IP=$(hostname -I | awk '{print $1}')
    echo "   http://$IP:5000"
    echo ""
    echo "6. Run debug tools if needed:"
    echo "   python3 bms_debugger.py"
    echo "   python3 env_debugger.py"
    echo ""
    echo -e "${BLUE}Documentation:${NC}"
    echo "  - Comprehensive guide: README_COMPREHENSIVE.md"
    echo "  - Quick start: QUICKSTART.md"
    echo ""
}

# Main installation flow
main() {
    print_header
    
    check_root
    check_system
    install_dependencies
    setup_permissions
    configure_serial
    create_config
    install_service
    run_tests
    show_next_steps
}

# Run main function
main