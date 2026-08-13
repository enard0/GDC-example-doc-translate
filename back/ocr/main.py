from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from extractor import PDFExtractor
from schemas import PageResponse
import uvicorn

# Inicjalizacja instancji serwisu
app = FastAPI(title="Local PDF Extractor Service")
extractor = PDFExtractor()


@app.post("/extract-layout", response_model=PageResponse)
async def extract_layout(file: UploadFile = File(...), page: int = Form(1)):
    try:
        # Wczytujemy plik do pamięci
        content = await file.read()

        # Wywołujemy naszą klasę ekstrakcyjną
        result = extractor.extract_page(content, page)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=500, detail="Wystąpił błąd podczas przetwarzania pliku."
        )


if __name__ == "__main__":
    # Uruchomienie serwera lokalnie na porcie 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="debug")
