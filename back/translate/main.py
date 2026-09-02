from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import traceback
import gc
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch


class Block(BaseModel):
    id: str
    type: str
    text: Optional[str]
    bbox: List[float]


class PageData(BaseModel):
    page: int
    blocks: List[Block]


class TranslationEngine:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.local_model_path = "./Hy-MT2-7B"

    def _init_models(self):
        if self.tokenizer is None:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.local_model_path, local_files_only=True
            )
        if self.model is None:
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.local_model_path,
                device_map="auto",
                quantization_config=quantization_config,
                torch_dtype=torch.float16,
                local_files_only=True,
            )

    def unload_models(self):
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


app = FastAPI(title="Translation API Service")
engine = TranslationEngine()


@app.post("/translate", response_model=PageData)
async def translate_page(data: PageData, target_lang: str):
    engine._init_models()

    text_labels = [
        "text",
        "header",
        "doc_title",
        "paragraph_title",
        "vision_footnote",
        "number",
        "abstract",
        "references",
        "reference",
        "footnotes",
        "footnote",
        "table_of_contents",
        "figure_caption",
        "table_caption",
        "figure_title",
        "list",
        "table",
    ]

    try:
        blocks_to_translate = [
            b for b in data.blocks if b.type in text_labels and b.text
        ]

        if blocks_to_translate:
            source_text = ""
            for b in blocks_to_translate:
                source_text += b.text.replace("‡", "") + " ‡ "

            messages = [
                {
                    "role": "system",
                    "content": "You are a professional translation engine.",
                },
                {
                    "role": "user",
                    "content": f"Please accurately translate the following text into {target_lang}. You must retain the exact same number of delimiters '‡' in the translation. Strictly do not omit, escape, or translate these symbols, and pay close attention to their placement.\n\n{source_text}",
                },
            ]

            prompt = engine.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            print(f"Prompt: {source_text}")
            inputs = engine.tokenizer(prompt, return_tensors="pt").to("cuda")

            outputs = engine.model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
                pad_token_id=engine.tokenizer.eos_token_id,
            )
            input_length = inputs.input_ids.shape[1]
            generated_tokens = outputs[0][input_length:]
            translated_texts = engine.tokenizer.decode(
                generated_tokens, skip_special_tokens=True
            ).split("‡")
            print(f"Translated Texts: {translated_texts}")
            for block, translated_text in zip(blocks_to_translate, translated_texts):
                block.text = translated_text
        return data

    except Exception:
        print("CRITICAL ERROR ENCOUNTERED:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error during translation.")


@app.post("/shutdown-models")
async def shutdown_models():
    try:
        engine.unload_models()
        return {"detail": "Translator models unloaded successfully, VRAM cleared."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
