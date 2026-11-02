import pytest
from pathlib import Path
import nbformat
from nbclient import NotebookClient

NOTEBOOKS = [
    "Crawl/notebooks/01_Crawl_Text.ipynb",
    "OCR/notebooks/01_OCR_Han.ipynb",
    "OCR/notebooks/02_OCR_Viet.ipynb",
    "Web/notebooks/01_Semantic_Alignment.ipynb"
]

@pytest.mark.parametrize("nb_rel_path", NOTEBOOKS)
def test_notebooks_valid_nbformat(nb_rel_path):
    nb_path = Path(nb_rel_path)
    assert nb_path.exists(), f"Notebook file missing: {nb_path}"

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    assert len(nb.cells) >= 3
    # Check that at least one code cell exists
    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    assert len(code_cells) >= 2

@pytest.mark.parametrize("nb_rel_path", NOTEBOOKS)
def test_notebooks_smoke_execute(nb_rel_path):
    """Executes notebook in smoke mode to verify all code cells run cleanly without exception."""
    nb_path = Path(nb_rel_path)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    client = NotebookClient(nb, timeout=60, kernel_name="python3")
    client.execute()
    # If no exception raised, execution succeeded!
