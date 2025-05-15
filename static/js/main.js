document.addEventListener("DOMContentLoaded", () => {
  const cardContainer = document.getElementById("sensor-cards");
  const tempChartCtx = document.getElementById("tempChart")?.getContext("2d");
  const humidityDoughnutCtx = document.getElementById("humidityDoughnut")?.getContext("2d");

  let tempChart, humidityDoughnut;
  const tempHistory = [];

  function updateCharts(temp, humidity) {
    const now = new Date().toLocaleTimeString();
    if (tempChart) {
      tempChart.data.labels.push(now);
      tempChart.data.datasets[0].data.push(temp);
      if (tempChart.data.labels.length > 10) {
        tempChart.data.labels.shift();
        tempChart.data.datasets[0].data.shift();
      }
      tempChart.update();
    }

    if (humidityDoughnut) {
      humidityDoughnut.data.datasets[0].data = [humidity, 100 - humidity];
      humidityDoughnut.update();
    }
  }

  async function loadSensorData() {
    const res = await fetch("/sensors");
    const data = await res.json();
    if (cardContainer) {
      cardContainer.innerHTML = "";
      for (const key in data) {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
          <h4>${key.replace(/_/g, " ").toUpperCase()}</h4>
          <p>${data[key]}</p>
        `;
        cardContainer.appendChild(card);
      }
    }
    if (data.temperature !== undefined && data.humidity !== undefined) {
      updateCharts(data.temperature, data.humidity);
    }
  }

  async function loadDeviceList() {
    const deviceTable = document.querySelector(".device-table tbody");
    if (!deviceTable) return;
    const res = await fetch("/device-list");
    const devices = await res.json();
    deviceTable.innerHTML = "";
    devices.forEach(dev => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${dev.name}</td>
        <td>${dev.id}</td>
        <td>${dev.protocol}</td>
        <td class="${dev.status === 'Bağlı' ? 'status-ok' : 'status-error'}">${dev.status}</td>
        <td>${dev.description}</td>
      `;
      deviceTable.appendChild(row);
    });
  }

  // Grafikler oluşturuluyor
  if (tempChartCtx) {
    tempChart = new Chart(tempChartCtx, {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: "Sıcaklık (°C)",
          borderColor: "#42A5F5",
          backgroundColor: "rgba(66, 165, 245, 0.2)",
          data: [],
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });
  }

  if (humidityDoughnutCtx) {
    humidityDoughnut = new Chart(humidityDoughnutCtx, {
      type: "doughnut",
      data: {
        labels: ["Nem (%)", ""],
        datasets: [{
          data: [0, 100],
          backgroundColor: ["#66BB6A", "#EEEEEE"]
        }]
      },
      options: {
        responsive: true,
        cutout: "70%"
      }
    });
  }

  loadSensorData();
  loadDeviceList();
  setInterval(loadSensorData, 10000);
});
