/**
 * Smart EV Charging Optimization Dashboard
 * Real-time HiveMQ WebSockets MQTT Client & Optimization Analytics Engine
 */

// --- Global State & Defaults ---
const state = {
    connected: false,
    mqttClient: null,
    broker: "broker.hivemq.com",
    port: 8884, // WSS port for HTTPS
    path: "/mqtt",
    useSSL: true,
    clientId: "WebDashboard_" + Math.random().toString(16).substr(2, 8),
    topicPrefix: "smart_ev",
    demoMode: false,
    demoInterval: null,

    // EV Specs & Grid Config
    batteryCapacity: 60, // kWh
    currentSoc: 24.5,    // %
    targetSoc: 85.0,     // %
    maxPowerKw: 7.4,     // kW
    arrivalHour: 18,     // 18:00
    departureHour: 7,    // 07:00
    tariffType: "standard_tou", // "standard_tou", "solar_tou", "dynamic_spot"
    solarPeakKw: 4.5,
    gridLimitKw: 11.0,

    // Live Sensor Telemetry
    telemetry: {
        voltage: 230.2,
        current: 0.0,
        power_kw: 0.0,
        energy_kwh: 14.82,
        temperature_c: 28.5,
        battery_soc: 24.5,
        relay_state: "OFF",
        mode: "AUTO",
        target_current: 16.0,
        plug_connected: true,
        sensor_type: "WAITING_DATA"
    },

    // Optimization Data
    schedule: null,
    chartInstance: null
};

// --- DOM Elements ---
const elements = {
    // Status
    connectionStatus: document.getElementById("connection-status"),
    statusDot: document.getElementById("status-dot"),
    brokerBadge: document.getElementById("broker-badge"),
    
    // Telemetry display
    valBatterySoc: document.getElementById("val-battery-soc"),
    valEstRange: document.getElementById("val-est-range"),
    batteryFill: document.getElementById("battery-fill"),
    batteryGlow: document.getElementById("battery-glow"),
    chargingPulseText: document.getElementById("charging-pulse-text"),
    
    valPower: document.getElementById("val-power"),
    valVoltage: document.getElementById("val-voltage"),
    valCurrent: document.getElementById("val-current"),
    valEnergy: document.getElementById("val-energy"),
    valTemperature: document.getElementById("val-temperature"),
    badgeTemp: document.getElementById("badge-temp"),
    valCurrentTariff: document.getElementById("val-current-tariff"),
    
    // Controls
    btnRelayToggle: document.getElementById("btn-relay-toggle"),
    relayStatusText: document.getElementById("relay-status-text"),
    relayLed: document.getElementById("relay-led"),
    btnModeAuto: document.getElementById("btn-mode-auto"),
    btnModeManual: document.getElementById("btn-mode-manual"),
    sliderCurrent: document.getElementById("slider-current"),
    valTargetCurrent: document.getElementById("val-target-current"),
    btnEmergencyStop: document.getElementById("btn-emergency-stop"),
    btnTriggerOptimize: document.getElementById("btn-trigger-optimize"),
    switchDemo: document.getElementById("switch-demo"),

    // Configuration Inputs
    inputBatteryCap: document.getElementById("input-battery-cap"),
    valBatteryCapDisp: document.getElementById("val-battery-cap-disp"),
    inputTargetSoc: document.getElementById("input-target-soc"),
    valTargetSocDisp: document.getElementById("val-target-soc-disp"),
    inputArrival: document.getElementById("input-arrival"),
    inputDeparture: document.getElementById("input-departure"),
    selectTariff: document.getElementById("select-tariff"),
    
    // Savings Metrics
    costUncontrolled: document.getElementById("cost-uncontrolled"),
    costOptimized: document.getElementById("cost-optimized"),
    costSavings: document.getElementById("cost-savings"),
    savingsPercent: document.getElementById("savings-percent"),
    co2Saved: document.getElementById("co2-saved"),
    peakShaved: document.getElementById("peak-shaved"),

    // Terminal
    mqttLogs: document.getElementById("mqtt-logs"),
    btnClearLogs: document.getElementById("btn-clear-logs"),

    // Settings Modal
    btnOpenSettings: document.getElementById("btn-open-settings"),
    btnCloseSettings: document.getElementById("btn-close-settings"),
    modalSettings: document.getElementById("modal-settings"),
    formSettings: document.getElementById("form-settings"),
    inputBrokerHost: document.getElementById("input-broker-host"),
    inputBrokerPort: document.getElementById("input-broker-port"),
    inputTopicPrefix: document.getElementById("input-topic-prefix")
};

// ==============================================================================
// 1. MQTT CLIENT VIA HIVEMQ WEBSOCKETS
// ==============================================================================
function initMQTT() {
    logTerminal("SYS", `Initiating WebSockets connection to ${state.broker}:${state.port}${state.path}...`);
    
    state.mqttClient = new Paho.MQTT.Client(
        state.broker,
        Number(state.port),
        state.path,
        state.clientId
    );

    state.mqttClient.onConnectionLost = onConnectionLost;
    state.mqttClient.onMessageArrived = onMessageArrived;

    const connectOptions = {
        timeout: 10,
        useSSL: state.useSSL,
        cleanSession: true,
        keepAliveInterval: 60,
        onSuccess: onConnectSuccess,
        onFailure: onConnectFailure
    };

    try {
        state.mqttClient.connect(connectOptions);
    } catch (e) {
        logTerminal("ERR", `MQTT Connect Error: ${e.message}`);
        setConnectionState(false);
    }
}

function onConnectSuccess() {
    setConnectionState(true);
    logTerminal("SYS", `Connected to HiveMQ WebSockets Broker! Subscribing to topics...`);
    
    const prefix = state.topicPrefix;
    state.mqttClient.subscribe(`${prefix}/telemetry`);
    state.mqttClient.subscribe(`${prefix}/schedule`);
    state.mqttClient.subscribe(`${prefix}/status`);
    logTerminal("SYS", `Subscribed to: ${prefix}/telemetry, ${prefix}/schedule, ${prefix}/status`);

    // Request initial optimization calculation
    publishMQTT(`${prefix}/trigger_optimize`, { request: "INIT" });
}

function onConnectFailure(response) {
    setConnectionState(false);
    logTerminal("ERR", `Connection failed: ${response.errorMessage || response}. Retrying in 5s...`);
    setTimeout(initMQTT, 5000);
}

function onConnectionLost(response) {
    setConnectionState(false);
    if (response.errorCode !== 0) {
        logTerminal("WARN", `Connection lost: ${response.errorMessage}. Reconnecting...`);
        setTimeout(initMQTT, 4000);
    }
}

function onMessageArrived(message) {
    const topic = message.destinationName;
    const payloadStr = message.payloadString;
    logTerminal("IN", `[${topic}] ${payloadStr.length > 120 ? payloadStr.substr(0, 120) + "..." : payloadStr}`);

    try {
        const payload = JSON.parse(payloadStr);
        if (topic.endsWith("/telemetry")) {
            handleTelemetry(payload);
        } else if (topic.endsWith("/schedule")) {
            handleSchedule(payload);
        } else if (topic.endsWith("/status")) {
            logTerminal("STATUS", `Device ${payload.device_id || ''} status: ${payload.status || 'OK'}`);
        }
    } catch (e) {
        console.error("Failed to parse incoming JSON:", e);
    }
}

function publishMQTT(topic, payloadObj) {
    if (!state.connected || !state.mqttClient) {
        logTerminal("WARN", `Cannot publish: Broker not connected. Updating locally.`);
        return;
    }
    const message = new Paho.MQTT.Message(JSON.stringify(payloadObj));
    message.destinationName = topic;
    message.qos = 1;
    state.mqttClient.send(message);
    logTerminal("OUT", `[${topic}] ${JSON.stringify(payloadObj)}`);
}

function setConnectionState(isConnected) {
    state.connected = isConnected;
    if (isConnected) {
        elements.connectionStatus.innerText = "Connected";
        elements.connectionStatus.className = "text-emerald-400 font-semibold";
        elements.statusDot.className = "w-3 h-3 rounded-full bg-emerald-500 animate-pulse";
        elements.brokerBadge.innerText = state.broker;
    } else {
        elements.connectionStatus.innerText = "Disconnected";
        elements.connectionStatus.className = "text-rose-400 font-semibold";
        elements.statusDot.className = "w-3 h-3 rounded-full bg-rose-500";
    }
}

// ==============================================================================
// 2. TELEMETRY & UI UPDATES
// ==============================================================================
function handleTelemetry(data) {
    Object.assign(state.telemetry, data);
    updateTelemetryUI();
}

function updateTelemetryUI() {
    const t = state.telemetry;

    // Battery State of Charge
    const soc = Math.max(0, Math.min(100, t.battery_soc || state.currentSoc));
    elements.valBatterySoc.innerText = `${soc.toFixed(1)}%`;
    elements.batteryFill.style.width = `${soc}%`;

    // Estimated driving range (assuming ~6.5 km per kWh, 60 kWh battery)
    const rangeKm = Math.round((soc / 100) * state.batteryCapacity * 6.5);
    elements.valEstRange.innerText = `~${rangeKm} km Range`;

    // Power, Voltage, Current, Energy
    elements.valPower.innerText = (t.power_kw || 0).toFixed(2);
    elements.valVoltage.innerText = (t.voltage || 230).toFixed(1);
    elements.valCurrent.innerText = (t.current || 0).toFixed(1);
    elements.valEnergy.innerText = (t.energy_kwh || 0).toFixed(2);
    elements.valTemperature.innerText = `${(t.temperature_c || 25).toFixed(1)}°C`;

    // Temperature safety badge
    const temp = t.temperature_c || 25;
    if (temp > 55) {
        elements.badgeTemp.innerText = "CRITICAL";
        elements.badgeTemp.className = "px-2 py-0.5 text-xs font-bold rounded bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse";
    } else if (temp > 42) {
        elements.badgeTemp.innerText = "WARM";
        elements.badgeTemp.className = "px-2 py-0.5 text-xs font-bold rounded bg-amber-500/20 text-amber-400 border border-amber-500/40";
    } else {
        elements.badgeTemp.innerText = "NORMAL";
        elements.badgeTemp.className = "px-2 py-0.5 text-xs font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40";
    }

    // Dynamic current tariff rate display
    const currentHour = new Date().getHours();
    const tariff = getTariffRateForHour(currentHour, state.tariffType);
    elements.valCurrentTariff.innerText = `₹${tariff.toFixed(2)}/kWh`;

    // Contactor Relay State
    const isRelayOn = t.relay_state === "ON" || t.relay_state === true;
    if (isRelayOn) {
        elements.btnRelayToggle.innerText = "DISCONNECT CHARGER";
        elements.btnRelayToggle.className = "w-full py-3 px-4 rounded-xl font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30 transition-all flex items-center justify-center gap-2";
        elements.relayStatusText.innerText = "CHARGING ACTIVE (ON)";
        elements.relayStatusText.className = "text-emerald-400 font-bold";
        elements.relayLed.className = "w-3.5 h-3.5 rounded-full bg-emerald-400 shadow-[0_0_12px_#34d399] animate-ping";
        elements.batteryGlow.className = "absolute inset-0 rounded-2xl bg-cyan-500/10 animate-pulse pointer-events-none";
        elements.chargingPulseText.classList.remove("hidden");
    } else {
        elements.btnRelayToggle.innerText = "START CHARGING (RELAY ON)";
        elements.btnRelayToggle.className = "w-full py-3 px-4 rounded-xl font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/30 transition-all flex items-center justify-center gap-2";
        elements.relayStatusText.innerText = "STANDBY (OFF)";
        elements.relayStatusText.className = "text-slate-400 font-semibold";
        elements.relayLed.className = "w-3.5 h-3.5 rounded-full bg-slate-500";
        elements.batteryGlow.className = "hidden";
        elements.chargingPulseText.classList.add("hidden");
    }

    // Mode Toggle UI
    const isAuto = (t.mode || "AUTO").toUpperCase() === "AUTO";
    if (isAuto) {
        elements.btnModeAuto.className = "flex-1 py-2 px-3 rounded-lg font-semibold text-sm bg-cyan-600 text-white shadow-md shadow-cyan-600/30";
        elements.btnModeManual.className = "flex-1 py-2 px-3 rounded-lg font-semibold text-sm bg-slate-800 text-slate-400 hover:text-white";
    } else {
        elements.btnModeManual.className = "flex-1 py-2 px-3 rounded-lg font-semibold text-sm bg-cyan-600 text-white shadow-md shadow-cyan-600/30";
        elements.btnModeAuto.className = "flex-1 py-2 px-3 rounded-lg font-semibold text-sm bg-slate-800 text-slate-400 hover:text-white";
    }
}

// ==============================================================================
// 3. OPTIMIZATION ENGINE & SCHEDULE VISUALIZER
// ==============================================================================
function getTariffRateForHour(hour, tariffType) {
    if (tariffType === "solar_tou") {
        if (hour >= 10 && hour < 15) return 2.80; // Solar sponge
        if (hour < 6 || hour >= 22) return 4.20;  // Off-peak
        if (hour >= 17 && hour < 21) return 13.50; // Peak
        return 7.00; // Shoulder
    } else if (tariffType === "dynamic_spot") {
        // Deterministic diurnal spot model
        const bump = 3.0 * Math.pow(Math.sin((hour - 8) * Math.PI / 12), 2) + 5.0 * Math.exp(-Math.pow(hour - 19, 2) / 6);
        return Math.max(2.0, 5.0 + bump);
    } else {
        // Standard 3-Tier TOU
        if (hour < 6 || hour >= 23) return 3.50;
        if (hour >= 17 && hour < 21) return 11.80;
        return 6.20;
    }
}

function calculateClientOptimization() {
    const cap = Number(state.batteryCapacity);
    const startSoc = Number(state.telemetry.battery_soc || state.currentSoc);
    const targetSoc = Number(state.targetSoc);
    const maxP = Number(state.maxPowerKw);
    const arr = Number(state.arrivalHour);
    const dep = Number(state.departureHour);
    const efficiency = 0.92;

    const energyNeeded = Math.max(0, ((targetSoc - startSoc) / 100) * cap / efficiency);

    // Active charging window hours
    let activeHours = [];
    if (arr < dep) {
        for (let h = arr; h < dep; h++) activeHours.push(h);
    } else {
        for (let h = arr; h < 24; h++) activeHours.push(h);
        for (let h = 0; h < dep; h++) activeHours.push(h);
    }

    // Generate solar curve (peaking at noon)
    const solarCurve = Array(24).fill(0).map((_, h) => {
        if (h >= 6 && h <= 18) {
            return Number((state.solarPeakKw * Math.pow(Math.sin((h - 6) * Math.PI / 12), 2)).toFixed(2));
        }
        return 0;
    });

    // 1. Uncontrolled Charging Benchmark
    let uncontrolledEnergyLeft = energyNeeded;
    const uncontrolledPower = Array(24).fill(0);
    const uncontrolledSoc = Array(24).fill(startSoc);
    let runSocUn = startSoc;

    for (let h of activeHours) {
        if (uncontrolledEnergyLeft > 0.01) {
            const p = Math.min(maxP, uncontrolledEnergyLeft);
            uncontrolledPower[h] = Number(p.toFixed(2));
            uncontrolledEnergyLeft -= p;
        }
        runSocUn += (uncontrolledPower[h] * efficiency / cap) * 100;
        uncontrolledSoc[h] = Math.min(100, runSocUn);
    }

    // 2. Smart Optimized Charging (Water-filling cheapest hours first)
    let optEnergyLeft = energyNeeded;
    const optPower = Array(24).fill(0);
    const optSoc = Array(24).fill(startSoc);

    // Sort active hours by effective net cost (tariff - solar credit)
    const sortedHours = [...activeHours].sort((a, b) => {
        const costA = getTariffRateForHour(a, state.tariffType) - solarCurve[a] * 0.8;
        const costB = getTariffRateForHour(b, state.tariffType) - solarCurve[b] * 0.8;
        return costA - costB;
    });

    for (let h of sortedHours) {
        if (optEnergyLeft > 0.01) {
            const p = Math.min(maxP, optEnergyLeft);
            optPower[h] = Number(p.toFixed(2));
            optEnergyLeft -= p;
        }
    }

    // Compute continuous SoC trajectory for optimized schedule
    let runSocOpt = startSoc;
    for (let h of activeHours) {
        runSocOpt += (optPower[h] * efficiency / cap) * 100;
        optSoc[h] = Math.min(100, runSocOpt);
    }

    // Calculate Costs & Carbon
    let costUncontrolled = 0;
    let costOptimized = 0;
    let carbonUncontrolled = 0;
    let carbonOptimized = 0;

    for (let h = 0; h < 24; h++) {
        const rate = getTariffRateForHour(h, state.tariffType);
        // Carbon: higher in peak hours
        const carbonFactor = (h >= 17 && h <= 21) ? 0.72 : 0.45;

        costUncontrolled += uncontrolledPower[h] * rate;
        costOptimized += optPower[h] * rate;

        carbonUncontrolled += uncontrolledPower[h] * carbonFactor;
        carbonOptimized += optPower[h] * carbonFactor;
    }

    const savings = Math.max(0, costUncontrolled - costOptimized);
    const savingsPct = costUncontrolled > 0 ? (savings / costUncontrolled) * 100 : 0;
    const co2Saved = Math.max(0, carbonUncontrolled - carbonOptimized);

    const scheduleData = {
        energy_needed_kwh: energyNeeded.toFixed(2),
        uncontrolled: { total_cost: costUncontrolled.toFixed(2) },
        optimized: { total_cost: costOptimized.toFixed(2) },
        comparison: {
            cost_savings: savings.toFixed(2),
            savings_percent: savingsPct.toFixed(1),
            co2_saved_kg: co2Saved.toFixed(2),
            peak_power_shaved_kw: (Math.max(...uncontrolledPower) - Math.max(...optPower)).toFixed(1)
        },
        timeline: Array(24).fill(0).map((_, h) => ({
            hour: h,
            hour_label: `${String(h).padStart(2, "0")}:00`,
            tariff: getTariffRateForHour(h, state.tariffType),
            solar_kw: solarCurve[h],
            opt_power_kw: optPower[h],
            opt_soc_percent: optSoc[h],
            uncontrolled_power_kw: uncontrolledPower[h]
        }))
    };

    handleSchedule(scheduleData);
}

function handleSchedule(data) {
    state.schedule = data;
    const comp = data.comparison || {};
    const opt = data.optimized || {};
    const un = data.uncontrolled || {};

    elements.costUncontrolled.innerText = `₹${un.total_cost || "0.00"}`;
    elements.costOptimized.innerText = `₹${opt.total_cost || "0.00"}`;
    elements.costSavings.innerText = `₹${comp.cost_savings || "0.00"}`;
    elements.savingsPercent.innerText = `${comp.savings_percent || "0.0"}% SAVED`;
    elements.co2Saved.innerText = `${comp.co2_saved_kg || "0.0"} kg`;
    elements.peakShaved.innerText = `${comp.peak_power_shaved_kw || "0.0"} kW`;

    renderScheduleChart(data.timeline || []);
}

function renderScheduleChart(timeline) {
    const ctx = document.getElementById("schedule-chart").getContext("2d");
    const labels = timeline.map(t => t.hour_label);
    const optPower = timeline.map(t => t.opt_power_kw);
    const unPower = timeline.map(t => t.uncontrolled_power_kw || 0);
    const tariffs = timeline.map(t => t.tariff);
    const solar = timeline.map(t => t.solar_kw);

    if (state.chartInstance) {
        state.chartInstance.destroy();
    }

    state.chartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Smart Scheduled Power (kW)",
                    data: optPower,
                    backgroundColor: "rgba(6, 182, 212, 0.75)",
                    borderColor: "#06b6d4",
                    borderWidth: 1.5,
                    borderRadius: 4,
                    yAxisID: "yPower",
                    order: 2
                },
                {
                    label: "Uncontrolled Power (kW)",
                    data: unPower,
                    backgroundColor: "rgba(244, 63, 94, 0.25)",
                    borderColor: "rgba(244, 63, 94, 0.6)",
                    borderWidth: 1,
                    borderDash: [4, 4],
                    borderRadius: 4,
                    yAxisID: "yPower",
                    order: 3
                },
                {
                    label: "TOU Electricity Tariff (₹/kWh)",
                    data: tariffs,
                    type: "line",
                    borderColor: "#f59e0b",
                    backgroundColor: "transparent",
                    borderWidth: 2.5,
                    stepped: true,
                    pointRadius: 2,
                    yAxisID: "yTariff",
                    order: 1
                },
                {
                    label: "Rooftop Solar PV (kW)",
                    data: solar,
                    type: "line",
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    yAxisID: "yPower",
                    order: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        color: "#94a3b8",
                        usePointStyle: true,
                        boxWidth: 8,
                        font: { size: 11, family: "Inter, sans-serif" }
                    }
                },
                tooltip: {
                    backgroundColor: "rgba(15, 23, 42, 0.95)",
                    titleColor: "#38bdf8",
                    borderColor: "rgba(255, 255, 255, 0.1)",
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#64748b", font: { size: 10 } }
                },
                yPower: {
                    type: "linear",
                    position: "left",
                    title: { display: true, text: "Power (kW)", color: "#06b6d4" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#06b6d4" },
                    min: 0,
                    max: 10
                },
                yTariff: {
                    type: "linear",
                    position: "right",
                    title: { display: true, text: "Tariff (₹/kWh)", color: "#f59e0b" },
                    grid: { drawOnChartArea: false },
                    ticks: { color: "#f59e0b" },
                    min: 0,
                    max: 16
                }
            }
        }
    });
}

// ==============================================================================
// 4. USER CONTROLS & EVENT LISTENERS
// ==============================================================================
function setupEventListeners() {
    // Master Relay Contactor Toggle
    elements.btnRelayToggle.addEventListener("click", () => {
        const isCurrentOn = state.telemetry.relay_state === "ON" || state.telemetry.relay_state === true;
        const newCmd = isCurrentOn ? "RELAY_OFF" : "RELAY_ON";
        const payload = {
            command: newCmd,
            state: isCurrentOn ? "OFF" : "ON",
            mode: "MANUAL",
            target_current: Number(elements.sliderCurrent.value),
            timestamp: new Date().toISOString()
        };
        publishMQTT(`${state.topicPrefix}/control`, payload);
        // Optimistic UI update
        state.telemetry.relay_state = isCurrentOn ? "OFF" : "ON";
        state.telemetry.current = isCurrentOn ? 0 : Number(elements.sliderCurrent.value);
        state.telemetry.power_kw = isCurrentOn ? 0 : (230 * state.telemetry.current * 0.98) / 1000;
        updateTelemetryUI();
    });

    // Operation Mode Buttons
    elements.btnModeAuto.addEventListener("click", () => {
        state.telemetry.mode = "AUTO";
        publishMQTT(`${state.topicPrefix}/control`, { mode: "AUTO" });
        updateTelemetryUI();
    });

    elements.btnModeManual.addEventListener("click", () => {
        state.telemetry.mode = "MANUAL";
        publishMQTT(`${state.topicPrefix}/control`, { mode: "MANUAL" });
        updateTelemetryUI();
    });

    // Target Current Slider
    elements.sliderCurrent.addEventListener("input", (e) => {
        const val = e.target.value;
        elements.valTargetCurrent.innerText = `${val} A`;
    });

    elements.sliderCurrent.addEventListener("change", (e) => {
        const val = Number(e.target.value);
        publishMQTT(`${state.topicPrefix}/control`, { target_current: val });
    });

    // Emergency Stop
    elements.btnEmergencyStop.addEventListener("click", () => {
        publishMQTT(`${state.topicPrefix}/control`, {
            command: "RELAY_OFF",
            state: "OFF",
            mode: "EMERGENCY_STOP",
            reason: "MANUAL_E_STOP"
        });
        state.telemetry.relay_state = "OFF";
        state.telemetry.current = 0;
        state.telemetry.power_kw = 0;
        updateTelemetryUI();
        logTerminal("WARN", "EMERGENCY STOP TRIGGERED BY USER!");
    });

    // Trigger Optimizer
    elements.btnTriggerOptimize.addEventListener("click", () => {
        calculateClientOptimization();
        publishMQTT(`${state.topicPrefix}/trigger_optimize`, { trigger: "UI_CLICK" });
        logTerminal("SYS", "Optimization recalculated and dispatched.");
    });

    // Configuration Sliders & Selects
    elements.inputBatteryCap.addEventListener("input", (e) => {
        state.batteryCapacity = Number(e.target.value);
        elements.valBatteryCapDisp.innerText = `${state.batteryCapacity} kWh`;
        calculateClientOptimization();
    });

    elements.inputTargetSoc.addEventListener("input", (e) => {
        state.targetSoc = Number(e.target.value);
        elements.valTargetSocDisp.innerText = `${state.targetSoc}%`;
        calculateClientOptimization();
    });

    elements.inputArrival.addEventListener("change", (e) => {
        state.arrivalHour = Number(e.target.value);
        calculateClientOptimization();
    });

    elements.inputDeparture.addEventListener("change", (e) => {
        state.departureHour = Number(e.target.value);
        calculateClientOptimization();
    });

    elements.selectTariff.addEventListener("change", (e) => {
        state.tariffType = e.target.value;
        calculateClientOptimization();
    });

    // Browser Demo Simulation Switch
    elements.switchDemo.addEventListener("change", (e) => {
        state.demoMode = e.target.checked;
        if (state.demoMode) {
            startDemoSimulation();
        } else {
            stopDemoSimulation();
        }
    });

    // Clear Terminal Logs
    elements.btnClearLogs.addEventListener("click", () => {
        elements.mqttLogs.innerHTML = "";
    });

    // Settings Modal
    elements.btnOpenSettings.addEventListener("click", () => {
        elements.inputBrokerHost.value = state.broker;
        elements.inputBrokerPort.value = state.port;
        elements.inputTopicPrefix.value = state.topicPrefix;
        elements.modalSettings.classList.remove("hidden");
    });

    elements.btnCloseSettings.addEventListener("click", () => {
        elements.modalSettings.classList.add("hidden");
    });

    elements.formSettings.addEventListener("submit", (e) => {
        e.preventDefault();
        state.broker = elements.inputBrokerHost.value.trim();
        state.port = Number(elements.inputBrokerPort.value.trim());
        state.topicPrefix = elements.inputTopicPrefix.value.trim();
        elements.modalSettings.classList.add("hidden");
        logTerminal("SYS", `Settings saved. Reconnecting to ${state.broker}...`);
        if (state.mqttClient && state.connected) {
            state.mqttClient.disconnect();
        }
        initMQTT();
    });
}

// ==============================================================================
// 5. CLIENT-SIDE DEMO SIMULATION (NO BACKEND REQUIRED)
// ==============================================================================
function startDemoSimulation() {
    logTerminal("SYS", "Browser Demo Simulation active: Streaming realistic synthetic telemetry.");
    if (state.demoInterval) clearInterval(state.demoInterval);

    state.demoInterval = setInterval(() => {
        const isCharging = state.telemetry.relay_state === "ON";
        const voltage = 230 + (Math.random() * 4 - 2);
        let current = 0;
        if (isCharging) {
            current = Number(elements.sliderCurrent.value) + (Math.random() * 0.4 - 0.2);
            // Battery SoC increments gently
            state.telemetry.battery_soc = Math.min(100, (state.telemetry.battery_soc || 25) + 0.05);
            state.telemetry.temperature_c = Math.min(48, (state.telemetry.temperature_c || 28) + 0.03);
            state.telemetry.energy_kwh = (state.telemetry.energy_kwh || 14.8) + (current * voltage / 3600000);
        } else {
            state.telemetry.temperature_c = Math.max(26, (state.telemetry.temperature_c || 28) - 0.02);
        }

        const power = (voltage * current * 0.98) / 1000;
        state.telemetry.voltage = voltage;
        state.telemetry.current = current;
        state.telemetry.power_kw = power;

        updateTelemetryUI();
    }, 2000);
}

function stopDemoSimulation() {
    logTerminal("SYS", "Browser Demo Simulation stopped.");
    if (state.demoInterval) {
        clearInterval(state.demoInterval);
        state.demoInterval = null;
    }
}

// ==============================================================================
// 6. TERMINAL LOGGER
// ==============================================================================
function logTerminal(type, text) {
    const time = new Date().toLocaleTimeString();
    const row = document.createElement("div");
    row.className = "flex items-start gap-2 text-xs font-mono border-b border-slate-800/60 pb-1";

    let badgeColor = "bg-slate-700 text-slate-300";
    if (type === "IN") badgeColor = "bg-cyan-500/20 text-cyan-400";
    else if (type === "OUT") badgeColor = "bg-emerald-500/20 text-emerald-400";
    else if (type === "ERR") badgeColor = "bg-rose-500/20 text-rose-400 font-bold";
    else if (type === "WARN") badgeColor = "bg-amber-500/20 text-amber-400";
    else if (type === "SYS") badgeColor = "bg-indigo-500/20 text-indigo-400";

    row.innerHTML = `
        <span class="text-slate-500 select-none">${time}</span>
        <span class="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${badgeColor}">${type}</span>
        <span class="text-slate-300 break-all">${escapeHtml(text)}</span>
    `;

    elements.mqttLogs.appendChild(row);
    elements.mqttLogs.scrollTop = elements.mqttLogs.scrollHeight;
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ==============================================================================
// 7. INITIALIZATION
// ==============================================================================
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    calculateClientOptimization();
    updateTelemetryUI();
    initMQTT();
});
