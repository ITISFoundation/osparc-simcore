# create an output that produces a script with data
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# passed by runner
input_dir = Path(os.environ["INPUT_FOLDER"])
output_dir = Path(os.environ["OUTPUT_FOLDER"])

current_path = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
data_path = output_dir / "data.json"


data = dict()
data["timestamp"] = str(datetime.utcnow())
data["input_dir_list"] = os.listdir(str(input_dir))
data["output_dir_list"] = os.listdir(str(input_dir))
print(json.dumps(data, indent=2))

data.update(os.environ)

# creates some data in output
with data_path.open("wt") as fh:
    json.dump(data, fh)

# copies this code in output
shutil.copy(current_path, output_dir / "main.py")

# both will be zipped and exposed to the output
