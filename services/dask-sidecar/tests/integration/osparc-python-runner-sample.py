import os
from pathlib import Path

OUTPUT_FOLDER = os.environ["OUTPUT_FOLDER"]


if __name__ == "__main__":
    print("creating a 10MB file...")
    output_file = Path(OUTPUT_FOLDER) / "my_output_data.zip"
    print(output_file, "...")
    FILE_SIZE = 10 * 1024 * 1024
    with output_file.open("wb") as fp:
        fp.write(f"I am a {FILE_SIZE}B file".encode())
        fp.truncate(FILE_SIZE)
    print("...DONE!!!")
