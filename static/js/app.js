function drawAttendanceChart(canvas) {
    const data = JSON.parse(canvas.dataset.daily || "[]");
    const total = Number(canvas.dataset.total || 0);
    const bounds = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const context = canvas.getContext("2d");
    if (!context || bounds.width === 0) return;

    canvas.width = Math.round(bounds.width * ratio);
    canvas.height = Math.round(bounds.height * ratio);
    context.scale(ratio, ratio);

    const width = bounds.width;
    const height = bounds.height;
    const padding = { top: 10, right: 12, bottom: 29, left: 30 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(total, 1);
    const slot = plotWidth / data.length;
    const barWidth = Math.max(3, Math.min(12, slot * 0.58));

    context.font = "10px Arial, sans-serif";
    context.textBaseline = "middle";
    for (let tick = 0; tick <= 4; tick += 1) {
        const value = Math.round(maxValue * tick / 4);
        const y = padding.top + plotHeight - plotHeight * tick / 4;
        context.strokeStyle = "#e5e5e5";
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(padding.left, y);
        context.lineTo(width - padding.right, y);
        context.stroke();
        context.fillStyle = "#666";
        context.textAlign = "right";
        context.fillText(String(value), padding.left - 8, y);
    }

    data.forEach((entry, index) => {
        const center = padding.left + slot * index + slot / 2;
        if (!entry.weekend) {
            const presentHeight = plotHeight * entry.present / maxValue;
            const absentHeight = plotHeight * entry.absent / maxValue;
            if (presentHeight > 0) {
                context.fillStyle = "#315d8a";
                context.beginPath();
                context.roundRect(center - barWidth / 2, padding.top + plotHeight - presentHeight, barWidth, presentHeight, 3);
                context.fill();
            }
            if (absentHeight > 0) {
                context.fillStyle = "#c9c9c9";
                context.beginPath();
                context.roundRect(center - barWidth / 2, padding.top + plotHeight - presentHeight - absentHeight, barWidth, absentHeight, 3);
                context.fill();
            }
        }
        context.fillStyle = entry.weekend ? "#999" : "#666";
        context.textAlign = "center";
        context.fillText(String(entry.day), center, height - 11);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const chart = document.getElementById("attendance-chart");
    if (chart) {
        drawAttendanceChart(chart);
        window.addEventListener("resize", () => drawAttendanceChart(chart));
    }
    const dateInput = document.querySelector("[data-attendance-date]");
    if (dateInput) {
        let lastWeekday = dateInput.value;
        const attendanceForm = dateInput.form;

        function isWeekend(value) {
            const day = new Date(`${value}T00:00:00`).getDay();
            return day === 0 || day === 6;
        }

        dateInput.addEventListener("change", () => {
            if (isWeekend(dateInput.value)) {
                const hint = document.querySelector("[data-date-hint]");
                if (hint) hint.textContent = "Weekends are not class days. Please choose a weekday.";
                dateInput.value = lastWeekday;
                return;
            }
            lastWeekday = dateInput.value;
            const month = dateInput.value.slice(0, 7);
            const subjectInput = document.querySelector('input[name="subject"]');
            const subject = subjectInput ? subjectInput.value : "";
            window.location.assign(`/teacher/dashboard?subject=${encodeURIComponent(subject)}&month=${encodeURIComponent(month)}&attendance_date=${encodeURIComponent(dateInput.value)}`);
        });

        if (attendanceForm) {
            attendanceForm.addEventListener("submit", (event) => {
                if (!isWeekend(dateInput.value)) return;
                event.preventDefault();
                const hint = document.querySelector("[data-date-hint]");
                if (hint) hint.textContent = "Weekends are not class days. Please choose a weekday.";
                dateInput.value = lastWeekday;
            });
        }
    }
});
