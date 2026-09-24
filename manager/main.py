import os
import boto3
import pika
import json
import uuid
import asyncio
import threading
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import uvicorn
import sqlite3
from contextlib import asynccontextmanager
from languages import TargetLanguage

s3_client = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id=os.environ.get("S3_USER", "admin"),
    aws_secret_access_key=os.environ.get("S3_PASS", "admin123password"),
    region_name="us-east-1",
)
BUCKET_NAME = "translation-jobs"

# --- SSE State Variables ---
subscribers = {}
loop = None


def init_db():
    conn = sqlite3.connect("jobs.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, 
            filename TEXT,
            language TEXT,
            status TEXT, 
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop
    loop = asyncio.get_running_loop()
    threading.Thread(target=rabbitmq_consumer, daemon=True).start()
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- RabbitMQ Publishers ---
def publish_job_event(job_id: str, status: str):
    """Publishes a state change payload to the RabbitMQ job_events exchange."""
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


# --- RabbitMQ Consumer (Background Thread) ---
def rabbitmq_consumer():
    """Consumes state events and pushes them to active SSE subscribers."""
    credentials = pika.PlainCredentials(
        os.environ.get("RMQ_USER", "admin"), os.environ.get("RMQ_PASS", "admin123")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq", credentials=credentials)
    )
    channel = connection.channel()
    channel.exchange_declare(exchange="job_events", exchange_type="fanout")

    result = channel.queue_declare(queue="", exclusive=True)
    queue_name = result.method.queue
    channel.queue_bind(exchange="job_events", queue=queue_name)

    def callback(ch, method, properties, body):
        event_data = json.loads(body)
        job_id = event_data.get("job_id")
        status = event_data.get("status")
        timestamp = event_data.get("timestamp")

        conn = sqlite3.connect("jobs.db")
        conn.execute(
            """
            INSERT INTO jobs (job_id, status, timestamp) 
            VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET 
            status=excluded.status, 
            timestamp=excluded.timestamp
        """,
            (job_id, status, timestamp),
        )
        conn.commit()
        conn.close()

        if job_id in subscribers and loop:
            for queue in subscribers[job_id]:
                asyncio.run_coroutine_threadsafe(queue.put(event_data), loop)

    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()


@app.post("/process-pdf")
async def process_pdf(
    file: UploadFile = File(...), language: TargetLanguage = Form(TargetLanguage.polish)
):
    job_id = str(uuid.uuid4())

    conn = sqlite3.connect("jobs.db")
    conn.execute(
        "INSERT INTO jobs (job_id, filename, language, status, timestamp) VALUES (?, ?, ?, ?, ?)",
        (
            job_id,
            file.filename,
            language.value,
            "PENDING",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()

    publish_job_event(job_id, "PENDING")

    try:
        pdf_bytes = await file.read()
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_id}/source.pdf",
            Body=pdf_bytes,
            ContentType="application/pdf",
        )

        job_payload = {
            "job_id": job_id,
            "target_lang": language.value,
            "filename": file.filename,
        }
        publish_to_queue("ocr_queue", job_payload)

        return {"job_id": job_id, "status": "PENDING"}

    except Exception as e:
        publish_job_event(job_id, "FAILED")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def list_jobs():
    """Returns all jobs from the SQLite database."""
    conn = sqlite3.connect("jobs.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM jobs ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
