"""Export official Q&A; no invented subsidy or eligibility examples are emitted."""

from resources.database.seed_data.policy_qa_seed import export_qa_to_json
from pathlib import Path


def main(output_file: str | Path | None = None) -> None:
    """Write the revalidated question/answer dataset to its resource directory."""
    print(export_qa_to_json(output_file))


if __name__ == "__main__":
    main()
