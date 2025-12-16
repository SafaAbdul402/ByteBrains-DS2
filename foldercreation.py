import os

# Full path to your project root
project_root = r"C:\Users\safar\PycharmProjects\DataScienceProject\VoiceRecognitionProject"

# Walk through all folders in the project
for dirpath, dirnames, filenames in os.walk(project_root):
    # Only add .gitkeep if folder has no files except .gitkeep
    if not any(f for f in filenames if f != ".gitkeep"):
        gitkeep_path = os.path.join(dirpath, ".gitkeep")
        if not os.path.exists(gitkeep_path):
            with open(gitkeep_path, "w") as f:
                f.write("")  # create empty .gitkeep file
            print(f"Created {gitkeep_path}")
