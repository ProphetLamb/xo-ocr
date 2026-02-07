#!/usr/bin/env python3
"""
xo-parts-scanner.py

Press F7 to take a screenshot, parse Crossout part info if visible, and save it to parts.db
"""

import time
import multiprocessing
import threading
import queue
import keyboard

from db_worker import DBWorker
from ocr_worker import OcrWorker
from ocr import take_screenshot

def start_listening():
    ocr_queue = queue.Queue()
    db_queue = queue.Queue()
    stop_event = threading.Event()
    db_worker = DBWorker("parts.db", db_queue, stop_event)
    db_worker.start()
    ocr_workers = [OcrWorker(ocr_queue, db_queue, stop_event) for _ in range(multiprocessing.cpu_count())]
    for ocr_worker in ocr_workers:
        ocr_worker.start()

    print("[*] OCR listener started. Press F7 to capture. Press CTRL+C to quit.")

    def process_and_enqueue():
        try:
            print("[*] Taking screenshot...")
            img = take_screenshot()
            ocr_queue.put(img)
        except Exception as e:
            print("[!] Error during capture:", e)
    keyboard.add_hotkey("f7", process_and_enqueue)
    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("[*] Shutting down...")
        stop_event.set()
        for _ in ocr_workers:
            ocr_queue.put(None) # sentinel
        db_queue.put(None) # sentinel
        for ocr_worker in ocr_workers:
            ocr_worker.join(timeout=5)
        db_worker.join(timeout=5)
        print("[*] Exited.")

if __name__ == "__main__":
    start_listening()
