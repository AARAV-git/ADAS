import os

# Change this to your video folder path
folder_path = r"C:\Users\sunny\Desktop\ADAS Adoption\vedio"

# Supported video extensions
video_extensions = (".mp4", ".avi", ".mov", ".mkv", ".wmv")

# Get all video files
video_files = [
    f for f in os.listdir(folder_path)
    if f.lower().endswith(video_extensions)
]

# Sort for consistent renaming
video_files.sort()

# Rename files
for i, filename in enumerate(video_files, start=1):
    extension = os.path.splitext(filename)[1]
    new_name = f"video_{i:02d}{extension}"

    old_path = os.path.join(folder_path, filename)
    new_path = os.path.join(folder_path, new_name)

    os.rename(old_path, new_path)
    print(f"{filename}  -->  {new_name}")

print("\nAll videos renamed successfully!")