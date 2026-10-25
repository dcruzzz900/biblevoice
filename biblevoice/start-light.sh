#!/bin/sh
# Light server: no speech model. Phones recognise speech and send text. Plain HTTP; put a tunnel/host in front for HTTPS.
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements-light.txt
export LIGHT=1
echo "Serving on http://localhost:8000 (expose it with a tunnel, see README)"
exec uvicorn main:app --host 0.0.0.0 --port 8000
