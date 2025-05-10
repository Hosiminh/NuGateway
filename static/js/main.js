// main.js - dashboard'a sensors.json'dan veri çekme ve kartlara yazma

document.addEventListener("DOMContentLoaded", () => {
  fetch("/sensors")
    .then((response) => response.json())
    .then((data) => {
      const container = document.getElementById("sensor-cards");
      container.innerHTML = "";

      data.forEach((sensor) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
          <h4>${sensor.name}</h4>
          <div class="value">${sensor.value} ${sensor.unit || ""}</div>
        `;
        container.appendChild(card);
      });

      // örnek grafik çizimi (sadece sıcaklık için demo)
      const temp = data.find((d) => d.name.includes("Sıcaklık"));
      if (temp) drawTemperatureChart([temp.value]);

      const hum = data.find((d) => d.name.includes("Nem"));
      if (hum) drawHumidityChart(hum.value);
    })
    .catch((err) => console.error("Veri yükleme hatası:", err));
});

function drawTemperatureChart(values) {
  const ctx = document.getElementById("tempChart").getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: ["Şu an"],
      datasets: [
        {
          label: "Sıcaklık (°C)",
          data: values,
          borderColor: "#004080",
          backgroundColor: "rgba(0, 64, 128, 0.1)",
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: {
          beginAtZero: false,
        },
      },
    },
  });
}

function drawHumidityChart(value) {
  const ctx = document.getElementById("humidityDoughnut").getContext("2d");
  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Nem", "Boşluk"],
      datasets: [
        {
          data: [value, 100 - value],
          backgroundColor: ["#00ADEF", "#e0e0e0"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      cutout: "70%",
      plugins: {
        legend: { display: false },
      },
    },
  });
}
