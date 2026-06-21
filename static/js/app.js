/* ══════════════════════════════════════════════════════════
   RETIE Assistant Pro — Lógica del chat
   ══════════════════════════════════════════════════════════ */

const chatContainer = document.getElementById("chatContainer");
const messagesEl    = document.getElementById("messages");
const welcomeMsg    = document.getElementById("welcomeMsg");
const inputEl       = document.getElementById("inputPregunta");
const btnEnviar     = document.getElementById("btnEnviar");
const headerStatus  = document.getElementById("headerStatus");
const statConsultas = document.getElementById("statConsultas");
const statPaginas   = document.getElementById("statPaginas");

let esperandoRespuesta = false;
let contadorConsultas = 0;
let totalPaginas = 0;

// ── Auto-resize textarea ─────────────────────────────────────
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
});

// ── Enter para enviar (Shift+Enter = salto de línea) ─────────
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    enviarPregunta();
  }
});

// ── Verificar estado del servidor ────────────────────────────
async function verificarEstado() {
  try {
    const res = await fetch("/estado");
    const data = await res.json();
    const dot  = headerStatus.querySelector(".status-dot");
    const txt  = headerStatus.querySelector("span:last-child");

    if (data.indice_disponible) {
      dot.classList.remove("offline");
      dot.classList.add("online");
      txt.textContent = "En línea";
    } else {
      dot.classList.remove("online");
      dot.classList.add("offline");
      txt.textContent = "Sin índice";
    }
  } catch {
    const dot = headerStatus.querySelector(".status-dot");
    dot.classList.remove("online");
    dot.classList.add("offline");
    headerStatus.querySelector("span:last-child").textContent = "Sin conexión";
  }
}

// ── Enviar pregunta ───────────────────────────────────────────
async function enviarPregunta() {
  const pregunta = inputEl.value.trim();
  if (!pregunta || esperandoRespuesta) return;

  // Ocultar welcome
  if (welcomeMsg) welcomeMsg.style.display = "none";

  // Mostrar mensaje usuario
  agregarMensajeUsuario(pregunta);

  // Limpiar input
  inputEl.value = "";
  inputEl.style.height = "auto";

  // Bloquear UI
  esperandoRespuesta = true;
  btnEnviar.disabled = true;
  inputEl.disabled   = true;

  // Indicador de carga
  const loadingId = agregarTypingIndicator();

  try {
    const res = await fetch("/preguntar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta })
    });

    const data = await res.json();
    eliminarElemento(loadingId);

    if (!res.ok || data.error) {
      agregarMensajeError(data.error || "Error en el servidor. Por favor, intenta nuevamente.");
    } else {
      agregarMensajeAsistente(data.respuesta, data.paginas || []);
      
      // Actualizar estadísticas
      contadorConsultas++;
      if (statConsultas) statConsultas.textContent = contadorConsultas;
      
      if (data.paginas && data.paginas.length > 0) {
        totalPaginas += data.paginas.length;
        if (statPaginas) statPaginas.textContent = totalPaginas;
      }
    }

  } catch (err) {
    eliminarElemento(loadingId);
    agregarMensajeError("No se pudo conectar con el servidor. Verifica que Flask esté corriendo.");
  } finally {
    esperandoRespuesta = false;
    btnEnviar.disabled = false;
    inputEl.disabled   = false;
    inputEl.focus();
  }
}

// ── Mensaje del usuario ───────────────────────────────────────
function agregarMensajeUsuario(texto) {
  const msg = document.createElement("div");
  msg.className = "msg user";
  msg.innerHTML = `
    <div class="msg-avatar">👤</div>
    <div class="msg-bubble">${escaparHTML(texto)}</div>
  `;
  messagesEl.appendChild(msg);
  scrollAbajo();
}

// ── Mensaje del asistente ─────────────────────────────────────
function agregarMensajeAsistente(texto, paginas) {
  const msg = document.createElement("div");
  msg.className = "msg assistant";

  const sourcesHTML = paginas.length
    ? `<div class="msg-sources">
        <span class="sources-label">📚 Referencias</span>
        ${paginas.map(p => `<span class="source-chip">Pág. ${p}</span>`).join("")}
      </div>`
    : "";

  msg.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-bubble">
      <div class="msg-content">
        <div class="msg-text">${formatearTexto(texto)}</div>
        ${sourcesHTML}
      </div>
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollAbajo();
}

// ── Mensaje de error ──────────────────────────────────────────
function agregarMensajeError(texto) {
  const msg = document.createElement("div");
  msg.className = "msg assistant";
  msg.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-bubble">
      <div class="msg-error">⚠️ ${escaparHTML(texto)}</div>
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollAbajo();
}

// ── Typing indicator ──────────────────────────────────────────
function agregarTypingIndicator() {
  const id  = "typing-" + Date.now();
  const msg = document.createElement("div");
  msg.className = "msg assistant";
  msg.id = id;
  msg.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-bubble">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollAbajo();
  return id;
}

// ── Eliminar elemento por ID ──────────────────────────────────
function eliminarElemento(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Scroll al fondo ───────────────────────────────────────────
function scrollAbajo() {
  setTimeout(() => {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }, 50);
}

// ── Limpiar chat ──────────────────────────────────────────────
function limpiarChat() {
  messagesEl.innerHTML = "";
  if (welcomeMsg) welcomeMsg.style.display = "block";
  
  // Reiniciar contadores
  contadorConsultas = 0;
  totalPaginas = 0;
  if (statConsultas) statConsultas.textContent = "0";
  if (statPaginas) statPaginas.textContent = "0";
  
  // Mostrar bienvenida del chatbot nuevamente
  mostrarBienvenidaChatbot();
}

// ── Usar ejemplo ──────────────────────────────────────────────
function usarEjemplo(btn) {
  // Limpiar emoji del texto si existe
  let texto = btn.textContent.trim();
  // Remover emojis al inicio si los hay
  texto = texto.replace(/^[^\w\s]+/, '').trim();
  inputEl.value = texto;
  inputEl.dispatchEvent(new Event("input"));
  enviarPregunta();
}

// ── Toggle sidebar (móvil) ────────────────────────────────────
function toggleSidebar() {
  document.querySelector(".sidebar").classList.toggle("open");
}

// ── Escapar HTML ──────────────────────────────────────────────
function escaparHTML(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── Formato básico del texto (negritas y saltos) ──────────────
function formatearTexto(texto) {
  return escaparHTML(texto)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

// ── Mensaje de bienvenida del chatbot ──────────────────────
function mostrarBienvenidaChatbot() {
  // Verificar si ya hay mensajes en el chat
  if (messagesEl.children.length === 0) {
    const mensajeBienvenida = `¡Hola! Soy **RETIE Pro** 👋\n\nTu asistente técnico especializado en el **Reglamento Técnico de Instalaciones Eléctricas (RETIE)** de Colombia.\n\n📌 **¿Cómo puedo ayudarte?**\n• Consultar requisitos técnicos y normativas\n• Buscar definiciones y especificaciones del RETIE\n• Responder preguntas sobre instalaciones eléctricas\n• Proporcionar referencias de páginas del documento\n\n💡 **Consejo:** Sé específico en tus preguntas para obtener respuestas más precisas.`;
    
    agregarMensajeAsistente(mensajeBienvenida, []);
  }
}

// ── Init ──────────────────────────────────────────────────────
verificarEstado();
mostrarBienvenidaChatbot();

// Verificar estado periódicamente (cada 30 segundos)
setInterval(verificarEstado, 30000);