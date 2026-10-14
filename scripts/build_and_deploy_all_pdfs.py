import os
import sys
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
DOWNLOADS_DIR = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\lenovo"), "Downloads")

os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Import the 3 builders
sys.path.insert(0, SCRIPT_DIR)
from generate_pdf_part1_ai import build_part1_pdf
from generate_pdf_part2a_frontend import build_part2a_pdf
from generate_pdf_part2b_backend_logic import build_part2b_pdf

pdf_targets = [
    ("ESP32_SmartGrid_Part1_AI_Machine_Learning.pdf", build_part1_pdf),
    ("ESP32_SmartGrid_Part2A_Frontend_SCADA_Dashboard.pdf", build_part2a_pdf),
    ("ESP32_SmartGrid_Part2B_Backend_Logic_Infrastructure.pdf", build_part2b_pdf),
]

def main():
    print("=" * 70)
    print("  COMPILING ALL 3 SPECIALIZED SMART GRID TECHNICAL SPECIFICATION PDFS")
    print("=" * 70)
    
    for filename, builder_fn in pdf_targets:
        docs_target = os.path.join(DOCS_DIR, filename)
        downloads_target = os.path.join(DOWNLOADS_DIR, filename)
        
        print(f"\n[Compiling] {filename}...")
        builder_fn(docs_target)
        
        shutil.copy2(docs_target, downloads_target)
        print(f"-> Saved in Docs     : {docs_target}")
        print(f"-> Deployed Downloads: {downloads_target} ({os.path.getsize(downloads_target):,} bytes)")

    print("\n" + "=" * 70)
    print("  ALL 3 PDFS GENERATED & DEPLOYED TO DOWNLOADS SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
