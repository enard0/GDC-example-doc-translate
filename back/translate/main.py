from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import traceback
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


app = FastAPI(title="Translation API Service")


@app.post("/translate", response_model=PageData)
async def translate_page(data: PageData, target_lang: str):
    local_model_path = "./Hy-MT2-7B"
    torch
    tokenizer = AutoTokenizer.from_pretrained(local_model_path, local_files_only=True)
    quantization_config = BitsAndBytesConfig(load_in_8bit=True)

    model = AutoModelForCausalLM.from_pretrained(
        local_model_path,
        device_map="auto",
        quantization_config=quantization_config,
        torch_dtype=torch.float16,
        local_files_only=True,
    )

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

            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            print(f"Prompt: {source_text}")
            inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

            outputs = model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
            input_length = inputs.input_ids.shape[1]
            generated_tokens = outputs[0][input_length:]
            translated_texts = tokenizer.decode(
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
