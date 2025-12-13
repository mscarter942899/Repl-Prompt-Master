from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Roblox Trading Bot is alive!"

@app.route('/health')
def health():
    return {"status": "healthy", "service": "roblox-trading-bot"}

def run():
    app.run(host='0.0.0.0', port=5000)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
