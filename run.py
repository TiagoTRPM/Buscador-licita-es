# run.py
import uvicorn
import multiprocessing
import webbrowser
from threading import Timer
from main import app

def abrir_navegador():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    Timer(1.5, abrir_navegador).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
