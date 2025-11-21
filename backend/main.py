from __future__ import annotations

import argparse

import uvicorn


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Run the Checkers FastAPI backend.")
	parser.add_argument("--host", default="0.0.0.0", help="Bind host for the API server.")
	parser.add_argument("--port", type=int, default=8000, help="Port for the API server.")
	parser.add_argument("--reload", action="store_true", help="Enable autoreload (development only).")
	parser.add_argument("--log-level", default="info", help="Uvicorn log level.")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	uvicorn.run(
		"server.app:app",
		host=args.host,
		port=args.port,
		reload=args.reload,
		log_level=args.log_level,
	)


if __name__ == "__main__":
	main()
