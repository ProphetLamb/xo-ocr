import json
import queue
import threading


from ocr import box_extraction, pil2openCv
from specs import extract_specifications

class OcrWorker(threading.Thread):
    def __init__(self, ocr_queue: queue.Queue, db_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.ocr_queue = ocr_queue
        self.db_queue = db_queue
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            try:
                task = self.ocr_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if task is None:
                # sentinel to stop
                break
            img = task
            self.process_img(img)
            self.ocr_queue.task_done()

    def process_img(self, img):
        try:
            print("[*] Finding largest rectangle...")
            bbox = box_extraction(img)
            if bbox is None:
                print("[!] No box found")
                return
            x, y, w, h = bbox
            print(f"[*] Using bbox: x={x}, y={y}, w={w}, h={h}")
            bbox = img.crop((x, y, x + w, y + h))
            bbox = pil2openCv(bbox)
            print("[*] Running OCR...")
            info = extract_specifications(bbox)
            print("[*] OCR result:", json.dumps(info))
            self.db_queue.put(info)
            print("[+] Enqueued OCR result for saving.")
        except Exception as e:
            print(f"[!] Error during OCR:", e)