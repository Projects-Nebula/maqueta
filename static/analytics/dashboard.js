(function () {
  "use strict";

  var templateSelect = document.getElementById("analyticsTemplate");
  var daysSelect = document.getElementById("analyticsDays");
  var kindSelect = document.getElementById("analyticsHeatmapKind");
  var refreshButton = document.getElementById("analyticsRefresh");
  var sessionsBody = document.getElementById("sessionsBody");
  var sessionsEmpty = document.getElementById("sessionsEmpty");
  var heatmap = document.getElementById("analyticsHeatmap");
  var heatmapEmpty = document.getElementById("heatmapEmpty");
  var latestHeatmapPoints = [];
  if (!templateSelect || !daysSelect || !kindSelect || !refreshButton) return;

  function feedback(message, tone) {
    if (window.AppFeedback) window.AppFeedback.show(message, { tone: tone || "info" });
  }

  function queryString() {
    var params = new URLSearchParams({ days: daysSelect.value });
    if (templateSelect.value) params.set("template", templateSelect.value);
    return params.toString();
  }

  function formatDuration(seconds) {
    var total = Math.max(0, Math.round(Number(seconds) || 0));
    var minutes = Math.floor(total / 60);
    var remaining = String(total % 60).padStart(2, "0");
    return minutes + ":" + remaining;
  }

  function formatDate(value) {
    try {
      return new Intl.DateTimeFormat("es", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
    } catch (error) {
      return value;
    }
  }

  async function getJson(url) {
    var response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) throw new Error("No se pudo cargar la analítica.");
    return response.json();
  }

  function renderTemplates(templates) {
    var selected = templateSelect.value;
    templateSelect.innerHTML = "";
    var all = document.createElement("option");
    all.value = "";
    all.textContent = "Todas las páginas";
    templateSelect.appendChild(all);
    templates.forEach(function (template) {
      if (!template.slug) return;
      var option = document.createElement("option");
      option.value = template.slug;
      option.textContent = template.name + (template.is_published ? "" : " (no publicada)");
      templateSelect.appendChild(option);
    });
    templateSelect.value = selected;
  }

  function renderMetrics(metrics) {
    document.getElementById("metricVisitors").textContent = metrics.visitors;
    document.getElementById("metricSessions").textContent = metrics.sessions;
    document.getElementById("metricPageviews").textContent = metrics.pageviews;
    document.getElementById("metricDuration").textContent = formatDuration(metrics.average_duration_seconds);
    document.getElementById("metricClicks").textContent = metrics.clicks;
  }

  function drawHeatmap(points) {
    latestHeatmapPoints = points;
    var context = heatmap.getContext("2d");
    var width = heatmap.clientWidth || 960;
    var height = heatmap.clientHeight || 420;
    var ratio = window.devicePixelRatio || 1;
    heatmap.width = width * ratio;
    heatmap.height = height * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "rgba(255, 255, 255, .45)";
    context.fillRect(0, 0, width, height);
    context.strokeStyle = "rgba(101, 114, 135, .14)";
    context.lineWidth = 1;
    for (var column = 1; column < 10; column += 1) {
      context.beginPath();
      context.moveTo((width / 10) * column, 0);
      context.lineTo((width / 10) * column, height);
      context.stroke();
    }
    for (var row = 1; row < 10; row += 1) {
      context.beginPath();
      context.moveTo(0, (height / 10) * row);
      context.lineTo(width, (height / 10) * row);
      context.stroke();
    }
    if (!points.length) {
      heatmap.classList.add("hidden");
      heatmapEmpty.classList.remove("hidden");
      return;
    }
    heatmap.classList.remove("hidden");
    heatmapEmpty.classList.add("hidden");
    var maxWeight = Math.max.apply(null, points.map(function (point) { return point.weight; }));
    points.forEach(function (point) {
      var intensity = Math.max(.18, point.weight / maxWeight);
      var radius = 14 + (intensity * 28);
      var gradient = context.createRadialGradient(
        point.x * width, point.y * height, 0,
        point.x * width, point.y * height, radius,
      );
      gradient.addColorStop(0, "rgba(225, 29, 72, " + (0.72 * intensity) + ")");
      gradient.addColorStop(1, "rgba(225, 29, 72, 0)");
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(point.x * width, point.y * height, radius, 0, Math.PI * 2);
      context.fill();
    });
  }

  function renderSessions(sessions) {
    sessionsBody.innerHTML = "";
    sessionsEmpty.classList.toggle("hidden", sessions.length > 0);
    sessions.forEach(function (session) {
      var row = document.createElement("tr");
      var values = [
        session.template,
        formatDate(session.started_at),
        formatDuration(session.duration_seconds),
        session.pageviews,
        session.clicks,
        session.move_samples,
        session.exit_target || "—",
        session.viewport.width && session.viewport.height
          ? session.viewport.width + "×" + session.viewport.height
          : "—",
      ];
      values.forEach(function (value) {
        var cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      sessionsBody.appendChild(row);
    });
  }

  async function load() {
    refreshButton.disabled = true;
    document.getElementById("sessionsStatus").textContent = "Cargando…";
    document.getElementById("heatmapStatus").textContent = "Cargando…";
    var query = queryString();
    try {
      var data = await Promise.all([
        getJson("/api/analytics/overview/?" + query),
        getJson("/api/analytics/sessions/?" + query),
        getJson("/api/analytics/heatmap/?" + query + "&kind=" + encodeURIComponent(kindSelect.value)),
      ]);
      renderTemplates(data[0].templates);
      renderMetrics(data[0].metrics);
      renderSessions(data[1].sessions);
      drawHeatmap(data[2].points);
      document.getElementById("sessionsStatus").textContent = data[1].sessions.length + " sesiones";
      document.getElementById("heatmapStatus").textContent = data[2].points.length + " zonas";
    } catch (error) {
      feedback(error.message, "error");
      document.getElementById("sessionsStatus").textContent = "No disponible";
      document.getElementById("heatmapStatus").textContent = "No disponible";
    } finally {
      refreshButton.disabled = false;
    }
  }

  templateSelect.addEventListener("change", load);
  daysSelect.addEventListener("change", load);
  kindSelect.addEventListener("change", load);
  refreshButton.addEventListener("click", load);
  window.addEventListener("resize", function () { drawHeatmap(latestHeatmapPoints); });
  load();
})();
