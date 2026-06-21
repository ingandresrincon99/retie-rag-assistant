import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("No se encontró GOOGLE_API_KEY en el archivo .env")

genai.configure(api_key=GOOGLE_API_KEY)

app = Flask(__name__)

# ── Cargar colección ChromaDB ────────────────────────────────────────────────
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "retie"

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
print("TIPO EMBEDDINGS:", type(embeddings))
vectorstore = None

def cargar_vectorstore():
    global vectorstore
    if os.path.exists(CHROMA_PATH) and os.listdir(CHROMA_PATH):
        vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_PATH
        )
        count = vectorstore._collection.count()
        print(f"✅ ChromaDB cargado correctamente ({count} fragmentos).")
    else:
        print("⚠️  No se encontró ChromaDB. Ejecuta indexar_retie.py primero.")

cargar_vectorstore()

# ── Prompt del sistema ───────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres RETIE Pro, un asistente técnico especializado exclusivamente en el
Reglamento Técnico de Instalaciones Eléctricas (RETIE) de Colombia.

REGLAS ESTRICTAS QUE DEBES CUMPLIR SIN EXCEPCIÓN:
1. Responde ÚNICAMENTE con información que esté presente en los fragmentos del RETIE proporcionados.
2. NO uses tu conocimiento previo ni información externa al contexto dado.
3. NO inventes datos, cifras, artículos ni requerimientos.
4. NO completes información que no esté explícita en el contexto.
5. NO hagas suposiciones sobre lo que podría decir el RETIE.
6. Si la respuesta no se encuentra en el contexto recuperado, responde exactamente:
   "No encontré información suficiente en el RETIE para responder esa pregunta."

FORMATO OBLIGATORIO DE RESPUESTA:
Respuesta:
[Tu respuesta basada únicamente en el contexto del RETIE]

Fuentes consultadas:
[Lista de páginas del documento donde encontraste la información]

Contexto recuperado del RETIE:
{context}

Pregunta del usuario:
{question}"""

# ── Función RAG ──────────────────────────────────────────────────────────────
def obtener_respuesta_rag(pregunta: str) -> dict:
    print("PREGUNTA:", pregunta)
    print("EMBEDDING FUNCTION:", type(vectorstore._embedding_function))
    if vectorstore is None:
        return {
            "respuesta": "La base de datos ChromaDB no está disponible. Por favor ejecuta indexar_retie.py primero.",
            "paginas": [],
            "error": True
        }

    # Recuperar fragmentos relevantes
    docs = vectorstore.max_marginal_relevance_search(
    pregunta,
    k=7,
    fetch_k=20
)

    if not docs:
        return {
            "respuesta": "No encontré información suficiente en el RETIE para responder esa pregunta.",
            "paginas": [],
            "error": False
        }

    # Construir contexto con páginas
    context_parts = []
    paginas = set()
    for doc in docs:
        page = doc.metadata.get("page", "desconocida")
        if isinstance(page, int):
            page = page + 1  # PyPDF usa base 0
        paginas.add(str(page))
        context_parts.append(f"[Página {page}]\n{doc.page_content}")

    context = "\n\n---\n\n".join(context_parts)

    # Construir prompt completo
    prompt = SYSTEM_PROMPT.format(context=context, question=pregunta)

    # Llamar a Gemini
    # Llamar a Gemini
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        respuesta_texto = response.text

    except Exception as e:
        if "429" in str(e):
            return {
                "respuesta": "Se alcanzó temporalmente el límite de consultas de Gemini. Intenta nuevamente en unos segundos.",
                "paginas": [],
                "error": True
            }

        return {
            "respuesta": f"Error al generar la respuesta: {str(e)}",
            "paginas": [],
            "error": True
        }

    paginas_ordenadas = sorted(
        paginas,
        key=lambda x: int(x) if x.isdigit() else 0
    )

    return {
        "respuesta": respuesta_texto,
        "paginas": paginas_ordenadas,
        "error": False
    }
    

# ── Rutas Flask ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/preguntar", methods=["POST"])
def preguntar():
    data = request.get_json()

    if not data or "pregunta" not in data:
        return jsonify({"error": "No se recibió ninguna pregunta."}), 400

    pregunta = data["pregunta"].strip()

    if not pregunta:
        return jsonify({"error": "La pregunta no puede estar vacía."}), 400

    if len(pregunta) > 1000:
        return jsonify({"error": "La pregunta es demasiado larga (máximo 1000 caracteres)."}), 400

    try:
        resultado = obtener_respuesta_rag(pregunta)
        return jsonify(resultado)
    except Exception as e:
        print(f"Error al procesar la pregunta: {e}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@app.route("/estado")
def estado():
    estado_index = vectorstore is not None
    count = 0
    if vectorstore:
        try:
            count = vectorstore._collection.count()
        except Exception:
            pass
    return jsonify({
        "indice_disponible": estado_index,
        "fragmentos": count,
        "modelo_llm": "gemini-2.5-flash",
        "modelo_embeddings": "all-MiniLM-L6-v2",
        "base_vectorial": "ChromaDB"
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)