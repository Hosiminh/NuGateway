async function fetchSensorData() {
  try {
    const res = await fetch("/sensors");
    const data = await res.json();

    // Kart verilerini güncelle
    document.querySelector("#ldr span").textContent = `${data.ldr_lux} Lux (${data.is_dark ? "Karanlık" : "Aydınlık"})`;
    document.querySelector("#weather span").textContent = data.weather_status || "-";
    document.querySelector("#air span").textContent = `${data.air_quality || "-"} (%${data.air_quality_score || 0})`;
    document.querySelector("#pv span").textContent = `${data.pv_power || 0} W (${data.pv_voltage}V / ${data.pv_current}A)`;
    document.querySelector("#bms span").textContent = `${data.battery_soc || 0}%`;
    document.querySelector("#pir span").textContent = data.motion_detected ? "Hareket Var" : "Hareket Yok";

    // Grafiklere veri ekle
    updateCharts(data);
  } catch (err) {
    console.error("Veri alınamadı:", err);
  }
}

// Grafik nesneleri
let tempChart;
let humidityDoughnut;
let powerChart;
let tempData = [];
let timeLabels = [];

function updateCharts(data) {
  const now = new Date().toLocaleTimeString();
  if (tempData.length > 10) {
    tempData.shift();
    timeLabels.shift();
  }
  tempData.push(data.temperature || 0);
  timeLabels.push(now);

  tempChart.data.labels = timeLabels;
  tempChart.data.datasets[0].data = tempData;
  tempChart.update();

  humidityDoughnut.data.datasets[0].data = [data.humidity || 0, 100 - (data.humidity || 0)];
  humidityDoughnut.update();

  powerChart.data.labels.push(now);
  powerChart.data.datasets[0].data.push(data.pv_power || 0);
  if (powerChart.data.labels.length > 10) {
    powerChart.data.labels.shift();
    powerChart.data.datasets[0].data.shift();
  }
  powerChart.update();
}

function setupCharts() {
  const ctxTemp = document.getElementById("tempChart").getContext("2d");
  tempChart = new Chart(ctxTemp, {
    type: "line",
    data: {
      labels: [],
      datasets: [{ label: "Sıcaklık (°C)", data: [], borderColor: "#ff6b6b" }]
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } }
  });

  const ctxHum = document.getElementById("humidityDoughnut").getContext("2d");
  humidityDoughnut = new Chart(ctxHum, {
    type: "doughnut",
    data: {
      labels: ["Nem", "Kalan"],
      datasets: [{ data: [0, 100], backgroundColor: ["#4ecdc4", "#cccccc"] }]
    },
    options: { responsive: true, cutout: "70%" }
  });

  const ctxPower = document.getElementById("powerChart").getContext("2d");
  powerChart = new Chart(ctxPower, {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ label: "PV Güç (W)", data: [], backgroundColor: "#ffa502" }]
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } }
  });
}

setupCharts();
fetchSensorData();
setInterval(fetchSensorData, 10000);
