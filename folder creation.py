from pathlib import Path

# Base folder: the first VoiceRecognition
base_dir = Path(r"C:\Users\safar\PycharmProjects\VoiceRecognition")

# Subfolders to create
folders = ["data", "models", "src", "notebooks"]

# Python files in src
src_files = ["transcriber.py", "mfcc_extractor.py", "embedding_model.py", "speaker_id.py", "realtime.py"]

# Create subfolders
for folder in folders:
    folder_path = base_dir / folder
    folder_path.mkdir(parents=True, exist_ok=True)
    print(f"Created folder: {folder_path}")

# Create Python files in src
for file in src_files:
    file_path = base_dir / "src" / file
    file_path.touch(exist_ok=True)
    print(f"Created file: {file_path}")

# Create README.md in base folder
readme_path = base_dir / "README.md"
readme_path.touch(exist_ok=True)
print(f"Created file: {readme_path}")
