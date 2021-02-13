import argparse
import csv
import sys
from pathlib import Path

import xmlschema

from .checkers import Checker


def check_file(file: Path, schema: xmlschema.XMLSchema, out_dir: Path) -> None:
    if file.suffix != ".xml":
        print(f"{file} is not an XML file", file=sys.stderr)
        sys.exit(1)
    out_file = file.stem + ".csv"
    out_path = out_dir / out_file

    try:
        problems = Checker.all_checks(str(file), schema)
    except Exception as e:
        print(f"Failed to check {file}.\n{e}")
        return

    with open(out_path, "w", encoding="utf_8_sig", newline="") as f:
        writer = csv.writer(f, dialect="excel")
        writer.writerow(("נתיב בקובץ", "מספר סידורי", "בעיה"))
        writer.writerows(problems)


def main():
    schema = xmlschema.XMLSchema(
        str(
            Path(__file__).parent.parent
            / "MivneAchid_Holdings_KarnotPensiaHadashot_XSD_Schema_008.xsd"
        )
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, nargs="+", help="input file or dir")
    parser.add_argument("--out", default=".", help="output directory")

    args = parser.parse_args()
    out_dir = Path(args.out)
    if not out_dir.is_dir():
        print(f"{out_dir} is not a directory")
        sys.exit(1)

    for file_or_dir in map(Path, args.input):
        if file_or_dir.is_dir():
            for file in file_or_dir.iterdir():
                if file.suffix == ".xml":
                    check_file(file, schema, out_dir)
        else:
            check_file(file_or_dir, schema, out_dir)


if __name__ == "__main__":
    main()
