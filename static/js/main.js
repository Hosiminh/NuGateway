// Sayfa yüklendiğinde verileri getir
document.addEventListener("DOMContentLoaded", () => {
    fetchSensorData();
    fetchRelayStates();
});

// Sensör verilerini al ve kartları oluştur
function fetchSensorData() {
    fetch('/api/sensors')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById("sensor-data");
            container.innerHTML = '';
            data.forEach(sensor => {
                const card = document.createElement("div");
                card.className = "card";
                card.innerHTML = `
                    <h3>${sensor.name}</h3>
                    <p>${sensor.value} ${sensor.unit}</p>
                `;
                container.appendChild(card);
            });
        })
        .catch(err => console.error("Sensör verileri alınamadı:", err));
}

// Röle durumlarını al ve butonları oluştur
function fetchRelayStates() {
    fetch('/api/relays')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById("relay-controls");
            container.innerHTML = '';
            data.forEach((relay, index) => {
                const card = document.createElement("div");
                card.className = "card";
                card.innerHTML = `
                    <h3>Röle ${index + 1}</h3>
                    <p>Durum: <strong>${relay.state ? "Açık" : "Kapalı"}</strong></p>
                    <button class="relay-btn" onclick="toggleRelay(${index})">
                        ${relay.state ? "Kapat" : "Aç"}
                    </button>
                `;
                container.appendChild(card);
            });
        })
        .catch(err => console.error("Röle verileri alınamadı:", err));
}

// Röleyi aç/kapat
function toggleRelay(relayIndex) {
    fetch(`/api/relay/${relayIndex}/toggle`, {
        method: 'POST'
    })
    .then(res => {
        if (res.ok) {
            fetchRelayStates();
        } else {
            console.error("Röle durumu değiştirilemedi.");
        }
    });
}

// Periyodik olarak verileri yenile
setInterval(() => {
    fetchSensorData();
    fetchRelayStates();
}, 10000); // her 10 saniyede bir yenile
