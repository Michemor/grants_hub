from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/api")
async def root():
    return {"message": "Daystar Grant hub"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
