import asyncio
import websockets
import time

async def main():
    uri = "ws://localhost:8000/ws/stream/video_11.mp4"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Measuring frame intervals for 50 frames...")
            last_time = time.time()
            frame_count = 0
            
            while frame_count < 50:
                # 1. Receive JSON telemetry
                msg = await websocket.recv()
                # 2. Receive binary JPEG
                jpeg = await websocket.recv()
                
                now = time.time()
                elapsed = now - last_time
                last_time = now
                frame_count += 1
                
                print(f"Received frame {frame_count:02d} | Interval: {elapsed:.4f}s ({1/elapsed:.1f} FPS)")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
