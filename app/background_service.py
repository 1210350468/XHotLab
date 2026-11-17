from contextlib import redirect_stderr, redirect_stdout

import uvicorn

from .config import ROOT


def main() -> None:
    logs = ROOT / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / 'server.stdout.log').open('a', encoding='utf-8') as output:
        with (logs / 'server.stderr.log').open('a', encoding='utf-8') as errors:
            with redirect_stdout(output), redirect_stderr(errors):
                uvicorn.run(
                    'app.main:app',
                    host='127.0.0.1',
                    port=8766,
                    log_level='info',
                    access_log=False,
                )


if __name__ == '__main__':
    main()
