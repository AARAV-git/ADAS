import cv2
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.video_processor import RoadSensePipeline
from config import VIDEOS_DIR

def main():
    video_path = os.path.join(VIDEOS_DIR, "video_11.mp4")
    if not os.path.exists(video_path):
        print(f"Video {video_path} not found!")
        return
        
    cap = cv2.VideoCapture(video_path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    VIDEO_MAX_W = 1024
    if W > VIDEO_MAX_W:
        scale = VIDEO_MAX_W / W
        out_w, out_h = VIDEO_MAX_W, int(H * scale)
    else:
        out_w, out_h = W, H
        
    pipeline = RoadSensePipeline(frame_width=out_w, frame_height=out_h)
    
    print(f"\nProfiling 30 frames of 2.5K video_11.mp4 ({W}x{H})")
    print(f"{'Frame':>6} | {'Read (s)':>8} | {'Resize (s)':>10} | {'Process (s)':>11} | {'Total (s)':>9}")
    print("-" * 55)
    
    total_read = 0
    total_resize = 0
    total_process = 0
    total_time = 0
    
    for frame_idx in range(1, 31):
        t0 = time.time()
        
        # 1. Read
        t_r0 = time.time()
        ret, frame = cap.read()
        t_r1 = time.time()
        read_time = t_r1 - t_r0
        total_read += read_time
        
        if not ret:
            break
            
        # 2. Resize
        t_s0 = time.time()
        if W > VIDEO_MAX_W:
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        t_s1 = time.time()
        resize_time = t_s1 - t_s0
        total_resize += resize_time
            
        # 3. Process
        skip_detection = (frame_idx > 1) and (frame_idx % 3 != 1)
        t_p0 = time.time()
        result = pipeline.process_frame(frame, skip_detection)
        t_p1 = time.time()
        process_time = t_p1 - t_p0
        total_process += process_time
        
        elapsed = time.time() - t0
        total_time += elapsed
        
        print(f"{frame_idx:>6} | {read_time:>8.4f} | {resize_time:>10.4f} | {process_time:>11.4f} | {elapsed:>9.4f}")
        
    cap.release()
    print("-" * 55)
    print(f"Average Read:    {total_read/30:.4f}s")
    print(f"Average Resize:  {total_resize/30:.4f}s")
    print(f"Average Process: {total_process/30:.4f}s")
    print(f"Average Total:   {total_time/30:.4f}s → FPS: {30/total_time:.1f}")

if __name__ == "__main__":
    main()
