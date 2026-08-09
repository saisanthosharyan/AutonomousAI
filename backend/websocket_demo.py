import asyncio
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8000/ws/demo") as ws:
        print("Connected")
        await ws.send("hello")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())