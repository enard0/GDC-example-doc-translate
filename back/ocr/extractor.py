import pymupdf
import numpy as np
import cv2
import json
import tempfile
import os
import gc
from paddleocr import PaddleOCRVL, PaddleOCR


class PDFExtractor:
    def __init__(self):
        self.pipeline = None
        self.ocr = None
        self.model_base_path = "/models"

    def _init_models(self):
        if self.pipeline is None:
            self.pipeline = PaddleOCRVL(
                layout_detection_model_dir=os.path.join(
                    self.model_base_path, "PP-DocLayoutV3"
                ),
                vl_rec_model_dir=os.path.join(self.model_base_path, "PaddleOCR-VL-1.6"),
            )
        if self.ocr is None:
            self.ocr = PaddleOCR(
                det_model_dir=os.path.join(self.model_base_path, "PP-OCRv6_medium_det"),
                rec_model_dir=os.path.join(self.model_base_path, "PP-OCRv6_medium_rec"),
                cls_model_dir=os.path.join(
                    self.model_base_path, "PP-LCNet_x1_0_textline_ori"
                ),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                engine="paddle",
            )

    def extract_page(self, file_bytes: bytes, page_num: int) -> dict:
        self._init_models()
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")

        if page_num < 1 or page_num > len(doc):
            raise ValueError(f"Invalid page. Max page number: {len(doc)}")

        page = doc[page_num - 1]
        pix = page.get_pixmap()

        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.h, pix.w, pix.n
        )

        if pix.n == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        elif pix.n == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        output = self.pipeline.predict(img_array)

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
            mapped_blocks.append(
                {
                    "id": f"block_{block.get('block_id')}",
                    "type": block.get("block_label"),
                    "text": block.get("block_content", ""),
                    "bbox": block.get("block_bbox", []),
                }
            )

        h, w = img_array.shape[:2]

        for block in mapped_blocks:
            text = block.get("text", "")

            if (not text.strip() or "\n" in text) and block.get("bbox"):
                x0, y0, x1, y1 = [int(v) for v in block["bbox"]]

                pad = 10
                crop_img = img_array[
                    max(0, y0 - pad) : min(h, y1 + pad),
                    max(0, x0 - pad) : min(w, x1 + pad),
                ]

                if crop_img.size > 0:
                    result = self.ocr.predict(crop_img)

                    if result and result[0]:
                        valid_texts = []
                        for res_item in result:
                            if isinstance(res_item, dict) and "rec_texts" in res_item:
                                texts = res_item.get("rec_texts", [])
                                scores = res_item.get("rec_scores", [])

                                for t, score in zip(texts, scores):
                                    if float(score) > 0.70:
                                        valid_texts.append(t)

                        block["text"] = " ".join(valid_texts)
                    else:
                        block["text"] = ""

        return {"page": page_num, "blocks": mapped_blocks}

    def unload_models(self):
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        if self.ocr:
            del self.ocr
            self.ocr = None

        gc.collect()
        try:
            import paddle

            paddle.device.cuda.empty_cache()
        except Exception:
            pass
