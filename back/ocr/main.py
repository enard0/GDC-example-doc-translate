import os
import base64
import traceback
import uvicorn
from fastapi import FastAPI, HTTPException
from extractor import PDFExtractor
from schemas import VertexPredictRequest, VertexPredictResponse, PageResponse

app = FastAPI(title="Vertex AI OCR Service")
extractor = PDFExtractor()


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/predict", response_model=VertexPredictResponse)
async def predict(request: VertexPredictRequest):
    predictions = []
    try:
        for instance in request.instances:
            file_bytes = base64.b64decode(instance.file_base64)
            page_num = instance.page

            result_dict = extractor.extract_page(file_bytes, page_num)

            predictions.append(PageResponse(**result_dict))

        return VertexPredictResponse(predictions=predictions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/shutdown-models")
async def shutdown_models():
    try:
        extractor.unload_models()
        return {"detail": "OCR models unloaded successfully, VRAM cleared."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    port = int(os.environ.get("AIP_HTTP_PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
