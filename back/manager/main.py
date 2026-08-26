import os
import requests
import pymupdf
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import Response

app = FastAPI()

OCR_API_URL = "http://ocr:8001/extract-layout"
TRANSLATOR_API_URL = "http://translate:8002/translate"
FONT_PATH = "./fonts/arial.ttf"


@app.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...), language: str = Form("pl")):
    if not os.path.exists(FONT_PATH):
        raise HTTPException(status_code=500, detail=f"Font not found: {FONT_PATH}")

    pdf_bytes = await file.read()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    for page_num in range(1, len(doc) + 1):
        files = {"file": (file.filename, pdf_bytes, "application/pdf")}
        data = {"page": page_num}
        ocr_response = requests.post(OCR_API_URL, files=files, data=data)

        if ocr_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"OCR service error (page {page_num}): {ocr_response.text}",
            )

        extracted_json = ocr_response.json()

        trans_response = requests.post(
            TRANSLATOR_API_URL,
            json=extracted_json,
            params={"target_lang": language},
        )

        if trans_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Translate service error (page {page_num}): {trans_response.text}",
            )

        translated_json = trans_response.json()
        blocks = translated_json.get("blocks", [])

        page = doc[page_num - 1]
        page.insert_font(fontname="arial", fontfile=FONT_PATH)
        page_width = page.rect.width

        valid_blocks = [b for b in blocks if "bbox" in b]
        sorted_blocks = sorted(valid_blocks, key=lambda b: b["bbox"][1])
        chains = []

        for b in sorted_blocks:
            added = False
            for chain in chains:
                last_b = chain[-1]
                bx0, by0, bx1, by1 = b["bbox"]
                lx0, ly0, lx1, ly1 = last_b["bbox"]

                y_gap = by0 - ly1
                x_overlap = min(bx1, lx1) - max(bx0, lx0)

                if -10 <= y_gap <= 25 and x_overlap > 0:
                    chain.append(b)
                    added = True
                    break

            if not added:
                chains.append([b])

        text_labels = [
            "text",
            "header",
            "doc_title",
            "paragraph_title",
            "vision_footnote",
            "number",
            "abstract",
            "references",
            "footnotes",
            "table_of_contents",
            "figure_caption",
            "table_caption",
            "figure_title",
            "list",
        ]

        for block in blocks:
            if (
                block.get("type") in text_labels
                and block.get("text")
                and "bbox" in block
            ):
                x0, y0, x1, y1 = block["bbox"]

                my_chain = next((c for c in chains if block in c), [block])
                chain_max_x1 = max((b["bbox"][2] for b in my_chain), default=x1)

                max_x = page_width - 10
                for other in blocks:
                    if (
                        other.get("id") != block.get("id")
                        and "bbox" in other
                        and other not in my_chain
                    ):
                        bx0, by0, bx1, by1 = other["bbox"]
                        if max(y0, by0) < min(y1, by1):
                            if bx0 >= x1:
                                max_x = min(max_x, bx0 - 5)

                if len(my_chain) > 1:
                    limit_x1 = min(chain_max_x1, max_x)
                else:
                    limit_x1 = max_x

                box_height = y1 - y0

                if block["type"] in ["header", "doc_title", "paragraph_title"]:
                    font_size = max(8.0, box_height * 0.75)
                else:
                    font_size = 11.0

                current_x1 = x1

                while True:
                    expanded_rect = pymupdf.Rect(x0 - 1, y0 - 2, current_x1 + 2, y1 + 2)
                    page.draw_rect(
                        expanded_rect, color=(1, 0, 0), fill=(1, 1, 1), width=0.5
                    )

                    rc = page.insert_textbox(
                        expanded_rect,
                        block["text"],
                        fontsize=font_size,
                        fontname="arial",
                        color=(0, 0, 0),
                        align=0,
                    )

                    if rc >= 0:
                        break

                    if current_x1 < limit_x1 - 1:
                        current_x1 = min(current_x1 + 15, limit_x1)
                    elif font_size >= 4.5:
                        font_size -= 0.5
                    else:
                        break
            elif "bbox" in block:
                if block.get("type") in text_labels:
                    page.draw_rect(
                        block["bbox"], color=(0, 0, 1), fill=(1, 1, 1), width=0.5
                    )
                    print(block.get("text"))
    output_pdf_bytes = doc.write()

    return Response(
        content=output_pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=translated_document.pdf"},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
