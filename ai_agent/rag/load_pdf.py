from pathlib import Path
import pdfplumber
import json
import uuid

# -----------------------------
# INPUT PATHS (folders OR files)
# -----------------------------
INPUT_DIRS = [
    r"C:\Users\rouam\Downloads\produittunis",
    r"C:\Users\rouam\Downloads\productslistpricing",
    r"C:\Users\rouam\Downloads\ASSURMAX – SIMPLIFIED PLAN (UAE).pdf",
]

# -----------------------------
# OUTPUT
# -----------------------------
OUTPUT_DIR = Path("knowledge_base/extracted")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "documents.jsonl"


def collect_pdfs(input_paths):
    """Collect PDFs from folders and single-file paths"""
    pdfs = []

    for path in input_paths:
        p = Path(path)

        if p.is_dir():
            pdfs.extend(p.glob("*.pdf"))

        elif p.is_file() and p.suffix.lower() == ".pdf":
            pdfs.append(p)

        else:
            print(f"⚠️ Skipped (not found or not a PDF): {p}")

    return pdfs


def extract_pdfs():
    pdf_files = collect_pdfs(INPUT_DIRS)

    print(f"\n📄 Found {len(pdf_files)} PDFs\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for pdf_path in pdf_files:
            doc_id = f"{pdf_path.stem}_{uuid.uuid4().hex[:8]}"
            category = pdf_path.parent.name

            print(f"➡️ Extracting {pdf_path.name}")

            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()

                        if not text or not text.strip():
                            continue

                        record = {
                            "doc_id": doc_id,
                            "file_name": pdf_path.name,
                            "source_path": str(pdf_path),
                            "category": category,
                            "page": page_num,
                            "text": text.strip(),
                        }

                        out.write(
                            json.dumps(record, ensure_ascii=False) + "\n"
                        )

            except Exception as e:
                print(f"❌ Failed {pdf_path.name}: {e}")

    print(f"\n✅ Done. Output saved to:\n{OUTPUT_FILE.absolute()}")


if __name__ == "__main__":
    extract_pdfs()
