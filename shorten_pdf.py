import os
import argparse
from pypdf import PdfReader, PdfWriter

def shorten_pdf(input_path: str, output_path: str, max_pages: int = 15):
    print(f"Reading {input_path}...")
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        num_pages = min(max_pages, len(reader.pages))
        for i in range(num_pages):
            writer.add_page(reader.pages[i])

        with open(output_path, "wb") as f:
            writer.write(f)

        print(f"Successfully created short PDF at {output_path} with {num_pages} pages.")
    except Exception as e:
        print(f"Failed to shorten PDF: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shorten a PDF file to a maximum number of pages.")
    parser.add_argument("input_pdf", type=str, help="Absolute path to the original PDF file.")
    parser.add_argument("output_pdf", type=str, help="Absolute path to save the shortened PDF file.")
    parser.add_argument("--max_pages", type=int, default=15, help="Maximum number of pages to keep (default: 15).")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_pdf):
        print(f"Error: Could not find file at {args.input_pdf}")
    else:
        shorten_pdf(args.input_pdf, args.output_pdf, max_pages=args.max_pages)
