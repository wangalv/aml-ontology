"""Paths, pinned versions and runtime settings for the demo.

Anything specific to one machine comes from environment variables, never from the repository.
"""
import os
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DEMO_DIR.parent

# Pinned: the files in ontology/ and data/ were built from this AMLTRIX release.
AMLTRIX_VERSION = "1.0-beta.4"
AMLO_TTL = REPO_DIR / "ontology" / "amlo.ttl"
AMLTRIX_TTL = REPO_DIR / "data" / "amltrix.ttl"

# The Investigation Ontology (Demo): an extension that lives inside demo/, never in ontology/.
INVESTIGATION_TTL = DEMO_DIR / "vocab" / "investigation.ttl"
INVESTIGATION_SHAPES = DEMO_DIR / "shapes" / "investigation-shapes.ttl"
MAPPING_DIR = DEMO_DIR / "mapping"
SAMPLES_DIR = DEMO_DIR / "samples"
GENERATED_DIR = DEMO_DIR / "generated"

# Read-only transaction database. It lives outside this repository (set AML_DB to its path);
# when unset or missing, the demo falls back to the small bundled sample.
AML_DB = Path(os.environ["AML_DB"]) if os.environ.get("AML_DB") else None
SAMPLE_DB = DEMO_DIR / "samples" / "mini.duckdb"
# The Python that opens AML_DB. The file may have been written by a newer DuckDB than this project's own environment has;
# then point this at a Python whose duckdb can read it. Empty: the Python running this code.
AML_DB_PYTHON = os.environ.get("AML_DB_PYTHON", "")

def _load_env_file(path):
    """Read KEY=VALUE lines from demo/.env into os.environ. Real environment variables win. The file is git-ignored."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file(DEMO_DIR / ".env")

# LLM settings. "mock" replays canned responses and needs nothing. "ollama" uses a model on this machine.
# "zai" uses the Z.ai / Zhipu GLM API and needs Z_AI_API_KEY in demo/.env (never in the repository).
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")
LLM_MODEL = os.environ.get("LLM_MODEL", "")  # empty: each provider uses its own default
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = "qwen3.5:9b"
Z_AI_BASE_URL = os.environ.get("Z_AI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
Z_AI_API_KEY = os.environ.get("Z_AI_API_KEY", "")
Z_AI_CHAT_MODEL = os.environ.get("Z_AI_CHAT_MODEL", "")
MOCK_DIR = SAMPLES_DIR / "mock"
