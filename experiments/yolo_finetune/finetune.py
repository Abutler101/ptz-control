from pathlib import Path
from ultralytics import YOLO


def finetune():
    data_yaml_path = Path(__file__).parent.joinpath("ice_hockey_data.yaml")
    model_path = Path(__file__).parents[1].joinpath("yolo11n.pt")
    epochs = 80
    img_size = 1280
    batch_size = 10

    print(f"Fine tuning Yolo11n for ice hockey")
    model = YOLO(model_path)
    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        imgsz=img_size,
        rect=True,
        batch=batch_size,
        name='ice_hockey_detector',
        verbose=True
    )
    print("Training Complete")
    print(f"Results saved to: {model.trainer.save_dir}")

    metrics = model.val()
    print(f"Validation metrics: {metrics}")


if __name__ == '__main__':
    finetune()
