#!/bin/bash
# NuReklam Video Player - Display rölesi kontrolü ile

VIDEO="/home/cafer/Desktop/NuGateway/videos/NuReklam.mp4"
RELAY_STATES="/home/cafer/Desktop/NuGateway/relay_states.json"

echo "=========================================="
echo "  NuReklam Video Player Başlatılıyor..."
echo "=========================================="
echo "Video: $VIDEO"
echo "Durdurmak için Ctrl+C"
echo ""

# Sonsuz döngüde video oynat
while true; do
    # relay_states.json'dan display durumunu oku
    DISPLAY_ON=$(python3 -c "
import json
try:
    with open('$RELAY_STATES', 'r') as f:
        states = json.load(f)
    print('1' if states.get('display', False) else '0')
except:
    print('1')
" 2>/dev/null)

    if [ "$DISPLAY_ON" = "1" ]; then
        echo "[$(date '+%H:%M:%S')] 🎬 Video oynatılıyor..."
        mpv --fullscreen --loop-file=inf --no-terminal --no-osc "$VIDEO"
    else
        echo "[$(date '+%H:%M:%S')] 📴 Display kapalı, bekleniyor..."
        sleep 2
    fi
done
