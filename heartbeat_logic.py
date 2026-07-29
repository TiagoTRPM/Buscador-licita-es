import os
import signal
import time
import threading
import requests
from fastapi import FastAPI
from starlette.background import BackgroundTasks

# ... (resto do seu main.py, adicione isso ao topo)

# Variável para controlar o heartbeat
last_heartbeat = time.time()
HEARTBEAT_TIMEOUT = 30  # segundos

@app.post("/api/heartbeat")
async def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()
    return {"status": "ok"}

def monitor_heartbeat():
    global last_heartbeat
    while True:
        if time.time() - last_heartbeat > HEARTBEAT_TIMEOUT:
            print("Heartbeat perdido! Encerrando servidor...")
            os.kill(os.getpid(), signal.SIGTERM)
            break
        time.sleep(5)

# Iniciar o monitor em uma thread separada
threading.Thread(target=monitor_heartbeat, daemon=True).start()
