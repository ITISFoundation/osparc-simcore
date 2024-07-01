import json
import os
import pathlib as pl

input_path = pl.Path(os.environ["INPUT_FOLDER"])
output_path = pl.Path(os.environ["OUTPUT_FOLDER"])

input_file_path = input_path / "input.json"
output_file_path = output_path / "output.json"

input_content = json.loads(input_file_path.read_text())

print(input_content)

output_file_path.write_text(json.dumps(input_content))
