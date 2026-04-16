"""Thin Python wrapper around the OmniGraph CLI.

All graph operations go through this class so the rest of the codebase
never shells out directly.  If we later switch to the HTTP API
(omnigraph-server), only this file needs to change.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


class OmniGraphClient:
    """Wraps the ``omnigraph`` CLI for a single repository."""

    def __init__(
        self,
        repo_path: str | Path,
        schema_path: str | Path | None = None,
        queries_dir: str | Path | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.queries_dir = Path(queries_dir) if queries_dir else None

    # ------------------------------------------------------------------ init

    def init(self, schema_path: str | Path | None = None) -> None:
        """``omnigraph init --schema <pg> <repo>``"""
        schema = Path(schema_path) if schema_path else self.schema_path
        if schema is None:
            raise ValueError("schema_path required for init")
        self._run(["init", "--schema", str(schema), str(self.repo_path)])

    # ------------------------------------------------------------------ load

    def load(
        self,
        data_path: str | Path,
        *,
        branch: str = "main",
        mode: str = "append",
    ) -> None:
        """``omnigraph load --data <jsonl> --branch <b> --mode <m> <repo>``"""
        self._run([
            "load",
            str(self.repo_path),
            "--data", str(data_path),
            "--branch", branch,
            "--mode", mode,
        ])

    def load_jsonl(
        self,
        lines: list[dict],
        *,
        branch: str = "main",
        mode: str = "append",
    ) -> None:
        """Write *lines* to a temp file, then ``omnigraph load``."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
            tmp = f.name
        try:
            self.load(tmp, branch=branch, mode=mode)
        finally:
            Path(tmp).unlink(missing_ok=True)

    # ------------------------------------------------------------------ read

    def read(
        self,
        query_file: str | Path,
        query_name: str,
        params: dict | None = None,
        *,
        branch: str | None = None,
    ) -> list[dict]:
        """Run a named read query and return the result rows."""
        cmd = [
            "read",
            str(self.repo_path),
            "--query", str(query_file),
            "--name", query_name,
            "--json",
        ]
        if params:
            cmd += ["--params", json.dumps(params)]
        if branch:
            cmd += ["--branch", branch]

        raw = self._run(cmd, capture=True)
        result = json.loads(raw)
        return result.get("rows", [])

    def query(
        self,
        query_name: str,
        params: dict | None = None,
        *,
        query_file: str | None = None,
        branch: str | None = None,
    ) -> list[dict]:
        """Convenience: resolve *query_file* from ``queries_dir`` if not given."""
        if query_file is None and self.queries_dir is None:
            raise ValueError("query_file or queries_dir required")
        if query_file is None:
            # Search all .gq files in queries_dir for the named query
            for gq in self.queries_dir.glob("*.gq"):
                if gq.read_text().find(f"query {query_name}(") != -1 or \
                   gq.read_text().find(f"query {query_name}()") != -1:
                    query_file = str(gq)
                    break
            if query_file is None:
                raise ValueError(f"query {query_name!r} not found in {self.queries_dir}")
        return self.read(query_file, query_name, params, branch=branch)

    # ----------------------------------------------------------------- change

    def change(
        self,
        query_file: str | Path,
        query_name: str,
        params: dict | None = None,
        *,
        branch: str | None = None,
    ) -> dict:
        """Run a named mutation and return the result summary."""
        cmd = [
            "change",
            str(self.repo_path),
            "--query", str(query_file),
            "--name", query_name,
            "--json",
        ]
        if params:
            cmd += ["--params", json.dumps(params)]
        if branch:
            cmd += ["--branch", branch]

        raw = self._run(cmd, capture=True)
        return json.loads(raw)

    def mutate(
        self,
        query_name: str,
        params: dict | None = None,
        *,
        query_file: str | None = None,
        branch: str | None = None,
    ) -> dict:
        """Convenience: resolve *query_file* from ``queries_dir``."""
        if query_file is None and self.queries_dir is None:
            raise ValueError("query_file or queries_dir required")
        if query_file is None:
            for gq in self.queries_dir.glob("*.gq"):
                if gq.read_text().find(f"query {query_name}(") != -1 or \
                   gq.read_text().find(f"query {query_name}()") != -1:
                    query_file = str(gq)
                    break
            if query_file is None:
                raise ValueError(f"query {query_name!r} not found in {self.queries_dir}")
        return self.change(query_file, query_name, params, branch=branch)

    # ---------------------------------------------------------------- export

    def export(self, *, branch: str | None = None) -> list[dict]:
        """``omnigraph export`` → list of JSONL dicts."""
        cmd = ["export", str(self.repo_path)]
        if branch:
            cmd += ["--branch", branch]
        raw = self._run(cmd, capture=True)
        return [json.loads(line) for line in raw.strip().splitlines() if line.strip()]

    # ------------------------------------------------------------ snapshot

    def snapshot(self) -> str:
        """``omnigraph snapshot`` → raw text."""
        return self._run(["snapshot", str(self.repo_path)], capture=True)

    # ------------------------------------------------------------ internal

    def _run(
        self,
        args: list[str],
        *,
        capture: bool = False,
    ) -> str:
        result = subprocess.run(
            ["omnigraph", *args],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"omnigraph {' '.join(args[:2])} failed "
                f"(exit {result.returncode}):\n{result.stderr.strip()}"
            )
        return result.stdout if capture else ""
