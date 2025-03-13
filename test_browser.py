import asyncio
import logging
from app.tools.browser.browser_manager import BrowserManager

logging.basicConfig(level=logging.INFO)

async def test_browser():
    try:
        manager = BrowserManager(headless=True)
        await manager.initialize()
        print("Browser initialized successfully")

        # Test health check
        is_healthy = await manager.health_check()
        print(f"Browser health check: {'passed' if is_healthy else 'failed'}")

        # Clean up
        if manager.browser:
            await manager.browser.close()
    except Exception as e:
        print(f"Error during browser test: {e}")

if __name__ == "__main__":
    asyncio.run(test_browser())
