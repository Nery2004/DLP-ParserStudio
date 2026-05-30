"""Command line interface for DLP-ParserStudio."""

from __future__ import annotations

import argparse

from dlp_parserstudio import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dlp",
        description="DLP-ParserStudio: ecosistema educativo de analisis lexico y sintactico.",
    )

    subparsers = parser.add_subparsers(dest="command")

    version_parser = subparsers.add_parser(
        "version",
        help="Muestra la version instalada de DLP-ParserStudio.",
    )
    version_parser.set_defaults(func=show_version)

    ide_parser = subparsers.add_parser(
        "ide",
        help="Inicia el IDE web local de DLP-ParserStudio.",
    )
    ide_parser.add_argument("--host", default="127.0.0.1", help="Host del servidor.")
    ide_parser.add_argument("--port", default=8000, type=int, help="Puerto del servidor.")
    ide_parser.add_argument(
        "--reload",
        action="store_true",
        help="Reinicia el servidor automaticamente al cambiar archivos.",
    )
    ide_parser.set_defaults(func=run_ide)

    return parser


def show_version(_args: argparse.Namespace) -> int:
    print(f"DLP-ParserStudio {__version__}")
    return 0


def run_ide(args: argparse.Namespace) -> int:
    from dlp_parserstudio.ide.app import run_server

    run_server(host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
