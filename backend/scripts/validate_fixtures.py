"""Backward-compatible entrypoint for the two-container component checks."""
import asyncio
from validate_browser_isolation import main


if __name__ == '__main__':
    asyncio.run(main())
