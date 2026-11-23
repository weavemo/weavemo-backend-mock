"""Evaluate the reviewed puzzle rules in a server-only Node process."""

import json
import os
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
from threading import BoundedSemaphore

RUNNER = Path(__file__).with_name("adventure_puzzles") / "run.cjs"
RUNNERS = BoundedSemaphore(4)
TAGS = {"div", "p", "span", "strong", "b", "small", "h2", "h3", "button", "input"}
STYLE = {
    "grid-template-columns": r"repeat\(\d+,\s*(?:1fr|minmax\(0,\s*1fr\))\)",
    "width": r"[\d.]+%",
    "height": r"[\d.]+%",
    "max-width": r"\d+px",
    "min-height": r"\d+px",
    "border": r"2px dashed #[a-fA-F\d]{6}",
    "font-size": r"\d+px",
    "letter-spacing": r"\d+px",
    "text-align": r"center",
    "justify-content": r"center",
    "color": r"#[a-fA-F\d]{6}",
    "opacity": r"[\d.]+",
}


class BoardParser(HTMLParser):
    """Convert the private renderer's markup to inert React data."""

    def __init__(self):
        super().__init__()
        self.nodes = []
        self.stack = []

    def append(self, node):
        children = self.stack[-1]["children"] if self.stack else self.nodes
        children.append(node)

    def handle_data(self, data):
        if data:
            self.append(data)

    def handle_starttag(self, tag, attrs):
        if tag not in TAGS:
            raise ValueError(f"Unsupported puzzle board element {tag}")
        attrs = dict(attrs)
        node = {"tag": tag, "children": []}
        if attrs.get("class"):
            node["className"] = attrs["class"]
        if tag == "button":
            match = re.fullmatch(r"move\('([\w-]+)'\)", attrs.get("onclick") or "")
            if match and "disabled" not in attrs:
                node["action"] = match[1]
        if tag == "input":
            node["numeric"] = attrs.get("inputmode") == "numeric"
        style = {}
        for declaration in (attrs.get("style") or "").split(";"):
            key, _, value = declaration.partition(":")
            key, value = key.strip(), value.strip()
            if key in STYLE and re.fullmatch(STYLE[key], value):
                tokens = key.split("-")
                style[tokens[0] + "".join(word.title() for word in tokens[1:])] = value
        if style:
            node["style"] = style
        self.append(node)
        if tag != "input":
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != "input":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]["tag"] != tag:
            raise ValueError(f"Unbalanced puzzle board element {tag}")
        self.stack.pop()


def run_puzzle(row, operation, lang, *, move=None, answer=""):
    payload = {
        "region": row["region"],
        "gate": row["gate"],
        "variant": (row["attempt_count"] - 1) % 3,
        "moves": row["moves"],
        "operation": operation,
        "lang": lang,
        "move": move,
        "answer": answer,
    }
    if not RUNNERS.acquire(timeout=2):
        raise RuntimeError("Puzzle engine is busy")
    try:
        result = subprocess.run(
            [os.getenv("WEAVEMO_NODE_BINARY", "node"), str(RUNNER)],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=3,
            check=True,
        )
    finally:
        RUNNERS.release()
    output = json.loads(result.stdout)
    if "board" in output:
        parser = BoardParser()
        parser.feed(output.pop("board"))
        parser.close()
        if parser.stack:
            raise ValueError("Incomplete puzzle board")
        output["board"] = parser.nodes
    return output
