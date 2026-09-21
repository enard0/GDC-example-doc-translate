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

from extractor import PDFExtractor

app = FastAPI(title="OCR Service Worker")
extractor = PDFExtractor()

s3_client = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id=os.environ.get("S3_USER", "admin"),
    aws_secret_access_key=os.environ.get("S3_PASS", "admin123password"),
    region_name="us-east-1",
)
BUCKET_NAME = "translation-jobs"


def publish_job_event(job_id: str, status: str):
    try:
        credentials = pika.PlainCredentials(
            os.environ.get("RMQ_USER", "admin"), os.environ.get("RMQ_PASS", "admin123")
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


def publish_to_queue(queue_name: str, payload: dict):
    credentials = pika.PlainCredentials(
        os.environ.get("RMQ_USER", "admin"), os.environ.get("RMQ_PASS", "admin123")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq", credentials=credentials)
    )
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(payload),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


def process_message(ch, method, properties, body):
    data = json.loads(body)
    job_id = data["job_id"]
    target_lang = data["target_lang"]

    publish_job_event(job_id, "OCR_PROCESSING")

    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=f"{job_id}/source.pdf")
        file_bytes = response["Body"].read()

        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        predictions = []

        for page_num in range(1, page_count + 1):
            result_dict = extractor.extract_page(file_bytes, page_num)
            predictions.append(result_dict)

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_id}/ocr_output.json",
            Body=json.dumps(predictions).encode("utf-8"),
            ContentType="application/json",
        )

        extractor.unload_models()

        publish_job_event(job_id, "OCR_COMPLETED")
        publish_to_queue(
            "translation_queue", {"job_id": job_id, "target_lang": target_lang}
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        traceback.print_exc()
        publish_job_event(job_id, "FAILED")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consuming():
    credentials = pika.PlainCredentials(
        os.environ.get("RMQ_USER", "admin"), os.environ.get("RMQ_PASS", "admin123")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq", credentials=credentials, heartbeat=0)
    )
    channel = connection.channel()
    channel.queue_declare(queue="ocr_queue", durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="ocr_queue", on_message_callback=process_message)
    channel.start_consuming()


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    threading.Thread(target=start_consuming, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8001)
