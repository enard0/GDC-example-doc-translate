import os
import boto3
import pika
import json
import traceback
import threading
from datetime import datetime
import uvicorn
from fastapi import FastAPI
import pymupdf
import re
import nh3
from translate import TranslationEngine

engine = TranslationEngine()
app = FastAPI(title="Translation Service Worker")

s3_client = boto3.client(
    "s3",
    endpoint_url="http://s3:8333",
    aws_access_key_id=os.environ.get("S3_USER"),
    aws_secret_access_key=os.environ.get("S3_PASS"),
    region_name="us-east-1",
)
BUCKET_NAME = "translation-jobs"
FONT_PATH = "./arial.ttf"


def publish_job_event(job_id: str, status: str):
    try:
        credentials = pika.PlainCredentials(
            os.environ.get("RMQ_USER"), os.environ.get("RMQ_PASS")
        )
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host="rabbitmq", credentials=credentials)
        )
        channel = connection.channel()
        channel.exchange_declare(exchange="job_events", exchange_type="fanout")
        payload = {
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        channel.basic_publish(
            exchange="job_events", routing_key="", body=json.dumps(payload)
        )
        connection.close()
    except Exception as e:
        print(f"RabbitMQ Publish Error ({status}): {e}")


def process_latex_to_html(text: str) -> str:
    allowed_tags = {"b", "u", "sup", "sub"}
    text = nh3.clean(text, tags=allowed_tags, attributes={})
    text = text.replace("$", "").replace("\\$", "")
    text = re.sub(r"\\underline\{\\text\{([^}]+)\}\}", r"<u>\1</u>", text)
    text = re.sub(r"\\underline\{([^}]+)\}", r"<u>\1</u>", text)
    text = re.sub(r"\\textbf\{([^}]+)\}", r"<b>\1</b>", text)
    text = re.sub(r"\^\{([^}]+)\}", r"<sup>\1</sup>", text)
    text = text.replace("\\geq", "≥").replace("\\leq", "≤")
    text = re.sub(r"\\mathbb\{([^}]+)\}", r"\1", text)
    return text


def process_message(ch, method, properties, body):
    data = json.loads(body)
    job_id = data["job_id"]
    target_lang = data["target_lang"]
    filename = data.get("filename", "document.pdf")

    publish_job_event(job_id, "TRANSLATING")

    try:
        ocr_response = s3_client.get_object(
            Bucket=BUCKET_NAME, Key=f"{job_id}/ocr_output.json"
        )
        extracted_pages = json.loads(ocr_response["Body"].read().decode("utf-8"))

        pdf_response = s3_client.get_object(
            Bucket=BUCKET_NAME, Key=f"{job_id}/source.pdf"
        )
        pdf_bytes = pdf_response["Body"].read()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

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

        for page_num, extracted_json in enumerate(extracted_pages, start=1):
            blocks = extracted_json.get("blocks", [])
            blocks_to_translate = [
                b for b in blocks if b.get("type") in text_labels and b.get("text")
            ]

            if blocks_to_translate:
                # Call the model logic separated into model.py
                translated_texts = engine.translate_blocks(
                    blocks_to_translate, target_lang
                )

                for block, translated_text in zip(
                    blocks_to_translate, translated_texts
                ):
                    block["text"] = translated_text

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

                    limit_x1 = min(chain_max_x1, max_x) if len(my_chain) > 1 else max_x
                    box_height = y1 - y0

                    font_size = (
                        max(8.0, box_height * 0.75)
                        if block["type"] in ["header", "doc_title", "paragraph_title"]
                        else 11.0
                    )
                    current_x1 = x1

                    while True:
                        expanded_rect = pymupdf.Rect(
                            x0 - 1, y0 - 2, current_x1 + 2, y1 + 2
                        )
                        page.draw_rect(
                            expanded_rect, color=(0, 0, 0), fill=(1, 1, 1), width=0
                        )

                        original_text = block.get("text", "")

                        if block.get("type") == "table":
                            allowed_tags = {
                                "table",
                                "tr",
                                "td",
                                "th",
                                "tbody",
                                "thead",
                                "br",
                            }
                            safe_text = nh3.clean(
                                original_text, tags=allowed_tags, attributes={}
                            )
                            html_table = safe_text.replace("\\n", "<br>").replace(
                                "\n", ""
                            )
                            css = f"table {{ border-collapse: collapse; width: 100%; }} td {{ border: 1px solid black; padding: 2px; font-size: {font_size}px; font-family: sans-serif; }}"
                            page.insert_htmlbox(expanded_rect, html_table, css=css)
                            break

                        processed_text = process_latex_to_html(original_text)

                        if "<" in processed_text and ">" in processed_text:
                            css = f"p {{ font-size: {font_size}px; font-family: sans-serif; margin: 0; color: black; }}"
                            html_content = f"<p>{processed_text}</p>"
                            page.insert_htmlbox(expanded_rect, html_content, css=css)
                            break
                        else:
                            rc = page.insert_textbox(
                                expanded_rect,
                                processed_text,
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

        output_pdf_bytes = doc.write()

        base_name = filename.rsplit(".", 1)[0]
        download_name = f"{base_name}-{target_lang}.pdf"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_id}/final_translated.pdf",
            Body=output_pdf_bytes,
            ContentType="application/pdf",
            ContentDisposition=f'attachment; filename="{download_name}"',
        )

        publish_job_event(job_id, "COMPLETED")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        traceback.print_exc()
        publish_job_event(job_id, "FAILED")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consuming():
    credentials = pika.PlainCredentials(
        os.environ.get("RMQ_USER"), os.environ.get("RMQ_PASS")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq", credentials=credentials, heartbeat=0)
    )
    channel = connection.channel()
    channel.queue_declare(queue="translation_queue", durable=True)
    channel.basic_qos(prefetch_count=1)

    for method_frame, properties, body in channel.consume(
        queue="translation_queue", inactivity_timeout=60
    ):
        if method_frame is None:
            if engine.model is not None or engine.tokenizer is not None:
                engine.unload_models()
            continue

        process_message(channel, method_frame, properties, body)


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    threading.Thread(target=start_consuming, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8002)
