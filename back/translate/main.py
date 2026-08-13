from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from deep_translator import GoogleTranslator
import traceback


class Block(BaseModel):
    id: str
    type: str
    text: Optional[str]
    bbox: List[float]


class PageData(BaseModel):
    page: int
    blocks: List[Block]


app = FastAPI(title="Translation API Service")
translator = GoogleTranslator(source="auto", target="pl")


@app.post("/translate", response_model=PageData)
async def translate_page(data: PageData):
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

    try:
        # 1. Zbierz wszystkie teksty z bloków pasujących do etykiet w jedną listę
        blocks_to_translate = [
            b for b in data.blocks if b.type in text_labels and b.text
        ]

        if blocks_to_translate:
            texts = [b.text for b in blocks_to_translate]

            # 2. Przetłumacz wszystkie teksty naraz (zachowując kontekst dokumentu)
            translated_texts = translator.translate_batch(texts)

            # 3. Przypisz przetłumaczone teksty z powrotem do odpowiednich bloków
            for block, translated_text in zip(blocks_to_translate, translated_texts):
                original_text = block.text
                block.text = translated_text
        return data

    except Exception:
        print("CRITICAL ERROR ENCOUNTERED:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Błąd podczas tłumaczenia tekstu.")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
