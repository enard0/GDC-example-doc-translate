from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from extractor import PDFExtractor
from schemas import PageResponse
import traceback
import uvicorn

app = FastAPI(title="Local PDF Extractor Service")
extractor = PDFExtractor()


@app.post("/extract-layout", response_model=PageResponse)
async def extract_layout(file: UploadFile = File(...), page: int = Form(1)):
    try:
        content = await file.read()
        result = extractor.extract_page(content, page)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="debug")
