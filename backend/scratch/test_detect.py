import cv2
import numpy as np
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.video_processor import RoadSensePipeline
from config import VIDEOS_DIR

def main():
    video_path = os.path.join(VIDEOS_DIR, "video_08.mp4")
    if not os.path.exists(video_path):
        print(f"Video {video_path} not found! Trying video_15.mp4...")
        video_path = os.path.join(VIDEOS_DIR, "video_15.mp4")
        
    cap = cv2.VideoCapture(video_path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    VIDEO_MAX_W = 416
    if W > VIDEO_MAX_W:
        scale = VIDEO_MAX_W / W
        out_w, out_h = VIDEO_MAX_W, int(H * scale)
    else:
        out_w, out_h = W, H
        
    pipeline = RoadSensePipeline(frame_width=out_w, frame_height=out_h)
    
    total_time = 0
    print(f"\nProcessing 30 frames (imgsz=320, 1-in-3 skip, instant-confirm fix)")
    print(f"{'Frame':>6} | {'Skip':>5} | {'Tracked':>8} | {'Alerts':>7} | {'Time':>7}")
    print("-" * 46)
    
    for frame_idx in range(1, 31):
        ret, frame = cap.read()
        if not ret:
            break
            
        if W > VIDEO_MAX_W:
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
            
        skip_detection = (frame_idx > 1) and (frame_idx % 3 != 1)
        
        t0 = time.time()
        result = pipeline.process_frame(frame, skip_detection)
        elapsed = time.time() - t0
        total_time += elapsed
        
        tracked = result["tracked"]
        alerts = result["alerts"]
        
        print(f"{frame_idx:>6} | {str(skip_detection):>5} | {len(tracked):>8} | {len(alerts):>7} | {elapsed:.3f}s")
        
    cap.release()
    avg = total_time / 30
    print(f"\nAverage time per frame: {avg:.3f}s → effective FPS: {1/avg:.1f}")

if __name__ == "__main__":
    main()
