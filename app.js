/**
 * app.js — Frontend de Nexus FI
 * Facultad de Ingeniería UAEMéx — Equipo 404
 * Avance 2: WBS 1.3.5 (IP Filter) / WBS 1.4.2 (Rate Limiter)
 */

"use strict";

// ===========================================================================
// 1. Gestión de identidad de sesión y huella de dispositivo
// ===========================================================================

/**
 * Obtiene o genera un UUID persistente para la sesión del usuario.
 * Almacenado en localStorage con clave "nexus_session_uuid".
 * @returns {string} UUID de sesión
 */
function getOrCreateSessionUUID() {
  const STORAGE_KEY = "nexus_session_uuid";
  let uuid = localStorage.getItem(STORAGE_KEY);
  if (!uuid) {
    // Generar UUID v4 compatible con todos los navegadores
    uuid =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            const v = c === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
          });
    localStorage.setItem(STORAGE_KEY, uuid);
  }
  return uuid;
}

/**
 * Genera una huella de dispositivo liviana y la persiste en localStorage.
 * Utiliza: resolución de pantalla, userAgent, idioma, zona horaria y
 * canvas fingerprint con los colores institucionales UAEMéx.
 * Almacenado en localStorage con clave "nexus_device_fingerprint".
 * @returns {string} Huella hexadecimal del dispositivo
 */
function getDeviceFingerprint() {
  const STORAGE_KEY = "nexus_device_fingerprint";
  let fp = localStorage.getItem(STORAGE_KEY);
  if (fp) return fp;

  // Recopilar señales del dispositivo
  const signals = [
    `${screen.width}x${screen.height}x${screen.colorDepth}`,
    navigator.userAgent,
    navigator.language || navigator.userLanguage || "unknown",
    Intl.DateTimeFormat().resolvedOptions().timeZone || "unknown",
    navigator.hardwareConcurrency || "unknown",
    navigator.platform || "unknown",
  ];

  // Canvas fingerprint con identidad visual UAEMéx
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 220;
    canvas.height = 40;
    const ctx = canvas.getContext("2d");

    // Fondo con color UAEMéx
    ctx.fillStyle = "#007A3D";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Texto con color dorado UAEMéx
    ctx.fillStyle = "#D4A017";
    ctx.font = "bold 18px Arial";
    ctx.fillText("NexusFI-UAEMex", 10, 26);

    // Agregar un rectángulo decorativo
    ctx.fillStyle = "rgba(0,122,61,0.5)";
    ctx.fillRect(160, 5, 50, 30);

    signals.push(canvas.toDataURL());
  } catch (e) {
    signals.push("canvas-unavailable");
  }

  // Crear hash simple (djb2) de las señales concatenadas
  const raw = signals.join("|");
  let hash = 5381;
  for (let i = 0; i < raw.length; i++) {
    hash = ((hash << 5) + hash) ^ raw.charCodeAt(i);
    hash = hash >>> 0; // convertir a uint32
  }
  fp = "fp_" + hash.toString(16).padStart(8, "0");

  localStorage.setItem(STORAGE_KEY, fp);
  return fp;
}

// ===========================================================================
// 2. Headers de seguridad
// ===========================================================================

/**
 * Retorna los headers de seguridad para todas las peticiones a la API.
 * Incluye fingerprint de dispositivo y UUID de sesión.
 * @returns {Object} Headers HTTP de seguridad
 */
function getSecurityHeaders() {
  return {
    "Content-Type": "application/json",
    "X-Device-Fingerprint": getDeviceFingerprint(),
    "X-Session-ID": getOrCreateSessionUUID(),
  };
}

// ===========================================================================
// 3. Gestión de UI — Badges de estado
// ===========================================================================

/**
 * Actualiza los badges de estado en la barra superior con la información
 * de perímetro de red y cuota de consultas.
 * @param {Object} data - Datos de /api/session/info
 */
function updateSecurityUI(data) {
  const perimeterBadge = document.getElementById("perimeter-status-badge");
  const rateLimitBadge = document.getElementById("rate-limit-badge");

  if (!perimeterBadge || !rateLimitBadge) return;

  // --- Badge de perímetro ---
  if (data.in_perimeter) {
    perimeterBadge.textContent = `✅ FI UAEMéx (IP: ${data.client_ip})`;
    perimeterBadge.className = "badge ok";
  } else {
    perimeterBadge.textContent = `🚫 Fuera de Perímetro (IP: ${data.client_ip})`;
    perimeterBadge.className = "badge blocked";
  }

  // --- Badge de cuota ---
  if (data.quota) {
    const { hourly_remaining, hourly_limit, daily_remaining, daily_limit } = data.quota;
    const hourlyUsed = hourly_limit - hourly_remaining;
    const dailyUsed = daily_limit - daily_remaining;

    rateLimitBadge.textContent = `⚡ Cuota: ${hourlyUsed}/${hourly_limit} hr (${dailyUsed}/${daily_limit} día)`;

    if (hourly_remaining === 0 || daily_remaining === 0) {
      rateLimitBadge.className = "badge blocked";
    } else if (hourly_remaining <= 5 || daily_remaining <= 10) {
      rateLimitBadge.className = "badge warning";
    } else {
      rateLimitBadge.className = "badge ok";
    }
  }

  // Actualizar panel de información de sesión
  const ipEl = document.getElementById("session-ip");
  const deviceEl = document.getElementById("session-device-id");
  if (ipEl) ipEl.textContent = data.client_ip || "—";
  if (deviceEl) deviceEl.textContent = (data.device_id || "—").substring(0, 20) + "...";
}

// ===========================================================================
// 4. Gestión de errores HTTP 403 y 429
// ===========================================================================

let countdownInterval = null;

/**
 * Muestra el modal de alerta de seguridad.
 * @param {number} statusCode - 403 o 429
 * @param {Object} data - Cuerpo de la respuesta de error
 */
function showSecurityModal(statusCode, data) {
  const modal = document.getElementById("security-alert-modal");
  const modalIcon = document.getElementById("modal-icon");
  const modalTitle = document.getElementById("modal-title");
  const modalMessage = document.getElementById("modal-message");
  const modalDetail = document.getElementById("modal-detail");
  const modalCountdown = document.getElementById("modal-countdown");
  const modalCountdownLabel = document.getElementById("modal-countdown-label");

  if (!modal) return;

  // Limpiar countdown anterior
  if (countdownInterval) clearInterval(countdownInterval);
  modalCountdown.style.display = "none";
  modalCountdownLabel.style.display = "none";

  // Actualizar badge de perímetro si aplica
  const perimeterBadge = document.getElementById("perimeter-status-badge");
  const rateLimitBadge = document.getElementById("rate-limit-badge");

  if (statusCode === 403) {
    modalIcon.textContent = "🔒";
    modalTitle.textContent = "Acceso Restringido — Fuera de Perímetro";
    modalTitle.className = "modal-title error-403";
    modalMessage.textContent =
      "Tu conexión proviene de fuera de la red institucional de la " +
      "Facultad de Ingeniería UAEMéx. El acceso a Nexus FI está restringido " +
      "exclusivamente a las subredes institucionales autorizadas (148.215.X.X / 172.17.18.X).";
    modalDetail.innerHTML =
      `<strong>IP detectada:</strong> ${data.client_ip || "—"}<br>` +
      `<strong>Red requerida:</strong> ${data.required_network || "148.215.X.X / 172.17.18.X"}<br>` +
      `<strong>WBS:</strong> ${data.wbs || "1.3.5"}`;

    if (perimeterBadge) {
      perimeterBadge.textContent = `🚫 Fuera de Perímetro (IP: ${data.client_ip || "?"})`;
      perimeterBadge.className = "badge blocked";
    }
  } else if (statusCode === 429) {
    const quota = data.quota || {};
    const retryAfter = quota.retry_after || 60;

    modalIcon.textContent = "⚠️";
    modalTitle.textContent = "Límite de Consultas Alcanzado";
    modalTitle.className = "modal-title error-429";
    modalMessage.textContent =
      "Has alcanzado el límite de consultas permitidas para tu dispositivo/sesión. " +
      "Este límite protege los créditos de inferencia de Nexus FI.";
    modalDetail.innerHTML =
      `<strong>Límite horario:</strong> ${quota.hourly_limit || 20} consultas/hora<br>` +
      `<strong>Restantes en hora:</strong> ${quota.hourly_remaining ?? 0}<br>` +
      `<strong>Límite diario:</strong> ${quota.daily_limit || 60} consultas/día<br>` +
      `<strong>Restantes hoy:</strong> ${quota.daily_remaining ?? 0}<br>` +
      `<strong>WBS:</strong> ${data.wbs || "1.4.2"}`;

    if (rateLimitBadge) {
      rateLimitBadge.className = "badge blocked";
    }

    // Cuenta regresiva
    modalCountdown.style.display = "block";
    modalCountdownLabel.style.display = "block";
    let secondsLeft = retryAfter;

    function updateCountdown() {
      const minutes = Math.floor(secondsLeft / 60);
      const seconds = secondsLeft % 60;
      modalCountdown.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
      if (secondsLeft <= 0) {
        clearInterval(countdownInterval);
        modalCountdown.textContent = "00:00";
        modalCountdownLabel.textContent = "¡Ya puedes volver a consultar!";
      }
      secondsLeft--;
    }
    updateCountdown();
    countdownInterval = setInterval(updateCountdown, 1000);
  }

  modal.classList.add("visible");
}

/**
 * Cierra el modal de alerta de seguridad.
 */
function closeSecurityModal() {
  const modal = document.getElementById("security-alert-modal");
  if (modal) modal.classList.remove("visible");
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
}

// ===========================================================================
// 5. Chat — Área de mensajes
// ===========================================================================

/**
 * Agrega un mensaje al área de chat.
 * @param {string} text - Contenido del mensaje
 * @param {"user-msg"|"ai-msg"|"system-msg"|"error-msg"} type - Tipo de mensaje
 */
function appendChatMessage(text, type = "ai-msg") {
  const chatOutput = document.getElementById("chat-output");
  if (!chatOutput) return;

  // Quitar estado vacío si existe
  const empty = chatOutput.querySelector(".chat-empty");
  if (empty) empty.remove();

  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${type}`;

  const label = {
    "user-msg": "Tú",
    "ai-msg": "Nexus FI",
    "system-msg": "Sistema",
    "error-msg": "Error",
  }[type] || "Mensaje";

  msgDiv.innerHTML = `<div class="msg-label">${label}</div>${escapeHtml(text)}`;
  chatOutput.appendChild(msgDiv);
  chatOutput.scrollTop = chatOutput.scrollHeight;
}

/**
 * Escapa caracteres HTML para prevenir XSS.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ===========================================================================
// 6. Función principal: enviar consulta al backend
// ===========================================================================

/**
 * Envía una consulta al endpoint POST /api/chat con los headers de seguridad.
 * Maneja errores 403 y 429 con modales y badges.
 * @param {string} query - Consulta del usuario
 */
async function sendQuery(query) {
  if (!query || !query.trim()) return;

  const btnSend = document.getElementById("btn-send");
  const typingIndicator = document.getElementById("typing-indicator");

  // Mostrar mensaje del usuario
  appendChatMessage(query.trim(), "user-msg");

  // Activar estado de carga
  if (btnSend) btnSend.disabled = true;
  if (typingIndicator) typingIndicator.classList.add("visible");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: getSecurityHeaders(),
      body: JSON.stringify({ query: query.trim() }),
    });

    const data = await response.json().catch(() => ({}));

    if (response.status === 403) {
      showSecurityModal(403, data);
      appendChatMessage(
        "Acceso denegado: Tu IP está fuera del perímetro institucional FI UAEMéx.",
        "error-msg"
      );
    } else if (response.status === 429) {
      showSecurityModal(429, data);
      appendChatMessage(
        "Límite de consultas alcanzado. Espera antes de enviar otra consulta.",
        "error-msg"
      );
    } else if (!response.ok) {
      appendChatMessage(`Error del servidor (${response.status}): ${data.detail || "Error desconocido"}`, "error-msg");
    } else {
      // Respuesta exitosa — actualizar cuota en headers
      updateRateLimitFromHeaders(response.headers);
      appendChatMessage(data.response || JSON.stringify(data), "ai-msg");
    }
  } catch (error) {
    appendChatMessage(
      `Error de conexión: ${error.message}. Verifica tu conexión a la red.`,
      "error-msg"
    );
  } finally {
    if (btnSend) btnSend.disabled = false;
    if (typingIndicator) typingIndicator.classList.remove("visible");
  }
}

/**
 * Actualiza el badge de cuota con los headers X-RateLimit-* de la respuesta.
 * @param {Headers} headers - Headers de la respuesta HTTP
 */
function updateRateLimitFromHeaders(headers) {
  const limitHour = parseInt(headers.get("X-RateLimit-Limit-Hour") || "20");
  const remainingHour = parseInt(headers.get("X-RateLimit-Remaining-Hour") || "20");
  const limitDay = parseInt(headers.get("X-RateLimit-Limit-Day") || "60");
  const remainingDay = parseInt(headers.get("X-RateLimit-Remaining-Day") || "60");

  const rateLimitBadge = document.getElementById("rate-limit-badge");
  if (!rateLimitBadge) return;

  const usedHour = limitHour - remainingHour;
  const usedDay = limitDay - remainingDay;

  rateLimitBadge.textContent = `⚡ Cuota: ${usedHour}/${limitHour} hr (${usedDay}/${limitDay} día)`;

  if (remainingHour === 0 || remainingDay === 0) {
    rateLimitBadge.className = "badge blocked";
  } else if (remainingHour <= 5 || remainingDay <= 10) {
    rateLimitBadge.className = "badge warning";
  } else {
    rateLimitBadge.className = "badge ok";
  }
}

// ===========================================================================
// 7. Inicialización: cargar info de sesión al inicio
// ===========================================================================

/**
 * Carga la información de sesión desde /api/session/info y actualiza la UI.
 */
async function initSessionInfo() {
  const perimeterBadge = document.getElementById("perimeter-status-badge");
  const rateLimitBadge = document.getElementById("rate-limit-badge");

  // Estado de carga inicial
  if (perimeterBadge) {
    perimeterBadge.textContent = "🔄 Verificando red...";
    perimeterBadge.className = "badge loading";
  }
  if (rateLimitBadge) {
    rateLimitBadge.textContent = "🔄 Cargando cuota...";
    rateLimitBadge.className = "badge loading";
  }

  try {
    const response = await fetch("/api/session/info", {
      method: "GET",
      headers: getSecurityHeaders(),
    });

    const data = await response.json().catch(() => ({}));

    if (response.status === 403) {
      // IP fuera del perímetro — mostrar modal solo si la ruta está protegida
      showSecurityModal(403, data);
      if (perimeterBadge) {
        perimeterBadge.textContent = `🚫 Fuera de Perímetro (IP: ${data.client_ip || "?"})`;
        perimeterBadge.className = "badge blocked";
      }
    } else if (response.status === 429) {
      showSecurityModal(429, data);
      updateRateLimitFromHeaders(response.headers);
    } else if (response.ok) {
      updateSecurityUI(data);
    }
  } catch (error) {
    if (perimeterBadge) {
      perimeterBadge.textContent = "⚠️ Sin conexión";
      perimeterBadge.className = "badge warning";
    }
    console.error("[Nexus FI] Error al cargar info de sesión:", error);
  }
}

// ===========================================================================
// 8. Event listeners
// ===========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const btnSend = document.getElementById("btn-send");
  const btnModalClose = document.getElementById("btn-modal-close");
  const modalOverlay = document.getElementById("security-alert-modal");

  // Cerrar modal al hacer clic en el botón o en el overlay
  if (btnModalClose) {
    btnModalClose.addEventListener("click", closeSecurityModal);
  }
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeSecurityModal();
    });
  }

  // Cerrar modal con tecla Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSecurityModal();
  });

  // Enviar formulario de chat
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const query = input ? input.value.trim() : "";
      if (query) {
        sendQuery(query);
        if (input) input.value = "";
      }
    });
  }

  // Enviar con Ctrl+Enter o Cmd+Enter en el textarea
  if (input) {
    input.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        const query = input.value.trim();
        if (query) {
          sendQuery(query);
          input.value = "";
        }
      }
    });
  }

  // Inicializar información de sesión al cargar la página
  initSessionInfo();
});
