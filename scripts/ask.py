"""Ask the running service a question and read what comes back.

    PYTHONPATH=src python scripts/ask.py "what is a quadratic equation?"
    PYTHONPATH=src python scripts/ask.py --subject science "what is a redox reaction?"
    PYTHONPATH=src python scripts/ask.py --full "nature of roots"

For trying the pilot by hand. The service answers with an evidence pack, not
prose: this prints the gate's decision, the passages it authorised, and where
each came from. When it refuses it prints which condition failed, because "no
answer" and "no answer, and here is why" are different things to anyone deciding
whether the refusal was right.

Needs the service running -- see scripts/serve.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("AGTS_URL", "http://localhost:8000")
DEFAULT_TOKEN = os.environ.get("AGTS_TOKEN", "dev-token")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="+")
    parser.add_argument("--subject", default="mathematics",
                        choices=("mathematics", "science"))
    parser.add_argument("--grade", default="10")
    parser.add_argument("--curriculum", default="2026-27")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--full", action="store_true",
                        help="print every passage in full rather than the first lines")
    args = parser.parse_args()

    payload = {
        "query": " ".join(args.question),
        "grade": args.grade,
        "subject": args.subject,
        "curriculum_version": args.curriculum,
    }
    request = urllib.request.Request(
        f"{args.url}/v1/evidence",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {args.token}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"HTTP {error.code}: {error.read()[:300].decode('utf-8', 'replace')}")
    except urllib.error.URLError as error:
        raise SystemExit(
            f"cannot reach {args.url}: {error.reason}. Is scripts/serve.py running?"
        )

    print(f"\nQ: {payload['query']}   [{args.subject}, grade {args.grade}]")
    print(f"   {body['status']}   {body.get('latency_ms', '?')} ms   "
          f"pack {body['pack_id'][:18]}")

    if body["status"] != "SUFFICIENT":
        print("\n   refused because:")
        for reason in body.get("reasons") or ["no reason recorded"]:
            print(f"     - {reason}")
        print("\n   No passage is shown on purpose. The corpus not answering is an "
              "answer, and\n   showing the nearest thing anyway is how that becomes a "
              "wrong one.")
        return

    if body.get("unapproved_content"):
        print("   NOTE: this corpus is unapproved. Evaluation only, not for a learner.")

    for index, item in enumerate(body["evidence"], start=1):
        text = item["text"].strip()
        if not args.full:
            lines = [line for line in text.splitlines() if line.strip()][:3]
            text = "\n      ".join(line[:110] for line in lines)
            if len(item["text"].splitlines()) > 3:
                text += "\n      ..."
        else:
            text = "\n      ".join(item["text"].splitlines())
        print(f"\n  [{index}] {item['heading_path']}   ({item.get('role', '?')})")
        print(f"      {text}")
        citation = item.get("citation") or {}
        blocks = citation.get("block_ids") or []
        page = citation.get("page")
        # The count, not the list. A span here routinely carries forty-plus
        # block ids, and printing them buries the passage they belong to --
        # which is also the point: a citation naming forty blocks is not
        # pointing at anything (evidence precision is 3.5% on the holdout).
        print(f"      -- page {page}, {len(blocks)} blocks cited, "
              f"first {blocks[0].split(':')[-1] if blocks else '?'}")

    print(f"\n  {len(body['evidence'])} passages. Citations resolve to block ids in the "
          "release manifest.")


if __name__ == "__main__":
    main()
