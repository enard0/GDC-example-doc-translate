import pymupdf
import numpy as np
import cv2
import json
import tempfile
import os
import gc
from paddleocr import PaddleOCRVL


class PDFExtractor:
    def __init__(self):
        # Usunięto stałe ładowanie modelu do pamięci
        pass

    def extract_page(self, file_bytes: bytes, page_num: int) -> dict:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")

        if page_num < 1 or page_num > len(doc):
            raise ValueError(
                f"Nieprawidłowy numer strony. Dokument ma {len(doc)} stron."
            )

        page = doc[page_num - 1]
        pix = page.get_pixmap()

        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.h, pix.w, pix.n
        )

        if pix.n == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        elif pix.n == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Inicjalizacja modelu w momencie otrzymania żądania
        pipeline = PaddleOCRVL()
        output = pipeline.predict(img_array)

        parsed_data = {}

        for res in output:
            with tempfile.TemporaryDirectory() as temp_dir:
                json_path = os.path.join(temp_dir, "temp_res.json")
                res.save_to_json(save_path=json_path)

                with open(json_path, "r", encoding="utf-8") as f:
                    parsed_data = json.load(f)

            break

        mapped_blocks = []
        for block in parsed_data.get("parsing_res_list", []):
            print(
                block.get("block_content", ""),
            )
            mapped_blocks.append(
                {
                    "id": f"block_{block.get('block_id')}",
                    "type": block.get("block_label"),
                    "text": block.get("block_content", ""),
                    "bbox": block.get("block_bbox", []),
                }
            )

        # Usunięcie instancji modelu i wymuszenie zwolnienia pamięci systemowej
        del pipeline
        gc.collect()

        # Opróżnienie bufora pamięci VRAM karty graficznej dla środowiska PaddlePaddle
        try:
            import paddle

            paddle.device.cuda.empty_cache()
        except Exception:
            pass

        return {"page": page_num, "blocks": mapped_blocks}
