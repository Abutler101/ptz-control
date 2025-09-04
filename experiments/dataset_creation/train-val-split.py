import os
import shutil
import random
from pathlib import Path


def split_dataset(
    images_dir: Path = Path("images"),
    labels_dir: Path= Path("labels"),
    output_dir: Path= Path("dataset"),
    val_ratio=0.2,
    seed=42,
):
    random.seed(seed)

    image_files = [
        f for f in os.listdir(images_dir)
        if images_dir.joinpath(f"{f}").is_file()
    ]

    random.shuffle(image_files)

    val_size = int(len(image_files) * val_ratio)
    val_files = set(image_files[:val_size])
    train_files = set(image_files[val_size:])

    for split in ["train", "val"]:
        output_dir.joinpath(f"images/{split}").mkdir(exist_ok=True)
        output_dir.joinpath(f"labels/{split}").mkdir(exist_ok=True)

    # Copy files
    for split, files in [("train", train_files), ("val", val_files)]:
        for img_file in files:
            base = Path(img_file).stem
            label_file = base + ".txt"

            img_src = images_dir.joinpath(img_file)
            label_src = labels_dir.joinpath(label_file)

            img_dst = output_dir.joinpath(f"images/{split}/{img_file}")
            label_dst = output_dir.joinpath(f"labels/{split}/{label_file}")

            shutil.copy2(img_src, img_dst)

            if label_src.exists():
                shutil.copy2(label_src, label_dst)
            else:
                print(f"Warning: No label found for {img_file}")

    print("Dataset split complete!")


if __name__ == "__main__":
    split_dataset(
        images_dir=Path("/Users/pmai281/Downloads/project-3-at-2025-09-03-08-55-76b6dfe7/images"),
        labels_dir=Path("/Users/pmai281/Downloads/project-3-at-2025-09-03-08-55-76b6dfe7/labels"),
        output_dir=Path("/Users/pmai281/Developer/ptz-control/experiments/yolo_finetune/dataset"),
        val_ratio=0.2,  # 20% validation
    )
