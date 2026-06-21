import os
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("❌ No se encontró GOOGLE_API_KEY en el archivo .env")

PDF_PATH       = "RETIE.pdf"
CHROMA_PATH    = "chroma_db"
COLLECTION_NAME = "retie"
CHUNK_SIZE     = 1500
CHUNK_OVERLAP  = 300
BATCH_SIZE     = 10   # fragmentos por lote (respeta rate-limit de Gemini)

def main():
    print("=" * 60)
    print("  RETIE Pro — Indexador del RETIE (ChromaDB)")
    print("=" * 60)

    # ── 1. Verificar PDF ─────────────────────────────────────
    if not os.path.exists(PDF_PATH):
        print(f"\n❌ No se encontró '{PDF_PATH}'")
        print("   Coloca el PDF del RETIE en la raíz del proyecto.")
        return

    print(f"\n📄 Cargando {PDF_PATH}...")
    loader = PyPDFLoader(PDF_PATH)
    pages  = loader.load()
    print(f"   ✅ {len(pages)} páginas cargadas.")

    # ── 2. Crear chunks ──────────────────────────────────────
    print(f"\n✂️  Dividiendo en chunks (tamaño={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(pages)
    print(f"   ✅ {len(chunks)} fragmentos generados.")

    # ── 3. Embeddings con Gemini ─────────────────────────────
    print("\n🔢 Inicializando embeddings locales...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    # ── 4. Eliminar colección previa si existe ────────────────
    if os.path.exists(CHROMA_PATH):
        print(f"\n🗑️  Eliminando colección ChromaDB anterior en '{CHROMA_PATH}'...")
        import shutil
        shutil.rmtree(CHROMA_PATH)
        print("   ✅ Colección anterior eliminada.")

    # ── 5. Insertar en ChromaDB por lotes ────────────────────
    print(f"\n📦 Generando embeddings e insertando en ChromaDB...")
    print("   (Esto puede tomar varios minutos según el tamaño del PDF)\n")

    vectorstore = None
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(chunks), BATCH_SIZE):
        batch     = chunks[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"   Lote {batch_num}/{total_batches} — "
              f"fragmentos {i+1}–{min(i+BATCH_SIZE, len(chunks))}...")

        try:
            if vectorstore is None:
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    collection_name=COLLECTION_NAME,
                    persist_directory=CHROMA_PATH
                )
            else:
                vectorstore.add_documents(batch)

            # Pausa entre lotes para respetar el rate-limit de la API
            if batch_num < total_batches:
                time.sleep(10)

        except Exception as e:
            print(f"   ⚠️  Error en lote {batch_num}: {e}")
            print("   Esperando 15 segundos antes de reintentar...")
            time.sleep(60)
            try:
                if vectorstore is None:
                    vectorstore = Chroma.from_documents(
                        documents=batch,
                        embedding=embeddings,
                        collection_name=COLLECTION_NAME,
                        persist_directory=CHROMA_PATH
                    )
                else:
                    vectorstore.add_documents(batch)
            except Exception as e2:
                print(f"   ❌ Error fatal en lote {batch_num}: {e2}")
                raise

    count = vectorstore._collection.count()
    print(f"\n✅ ChromaDB guardado en '{CHROMA_PATH}/' ({count} fragmentos)")
    print(f"\n{'=' * 60}")
    print("  Indexación completada. Inicia la app con:")
    print("  python app.py   ó   iniciar.bat")
    print("=" * 60)

if __name__ == "__main__":
    main()
