import uvicorn
from markitdown_service.config import settings


def main():
    """Run MarkItDown HTTP Service using Uvicorn."""
    uvicorn.run(
        "markitdown_service.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()

