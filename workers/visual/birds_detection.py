"""YOLO + supervision helpers that turn an image or video into a list of species labels."""

from ultralytics import YOLO
import supervision as sv
import cv2 as cv

def image_prediction(image_path, result_filename=None, save_dir = "./image_prediction_results", confidence=0.5, model="./model.pt"):
    """
    Function to display predictions of a pre-trained YOLO model on a given image.

    Parameters:
        image_path (str): Path to the image file. Can be a local path or a URL.
        result_path (str): If not None, this is the output filename.
        confidence (float): 0-1, only results over this value are saved.
        model (str): path to the model.
    """

    # Load YOLO model
    model = YOLO(model)
    class_dict = model.names

    # Load image from local path
    img = cv.imread(image_path)

    # Check if image was loaded successfully
    if img is None:
        print("Couldn't load the image! Please check the image path.")
        return

    # Run the model on the image
    result = model(img)[0]

    # Convert YOLO result to Detections format
    detections = sv.Detections.from_ultralytics(result)

    labels = []

    # Filter detections based on confidence threshold and check if any exist
    if detections.class_id is not None:
        detections = detections[(detections.confidence > confidence)]

        # Create labels for the detected objects
        labels = [f"{class_dict[cls_id]}" for cls_id in 
                  detections.class_id]
        
    return labels


# ## Video Detection
def video_prediction(video_path, result_filename=None, save_dir = "./video_prediction_results", confidence=0.5, model="./model.pt", inference_per_sec = 5):
    """
    Function to make predictions on video frames using a trained YOLO model and display the video with annotations.

    Parameters:
        video_path (str): Path to the video file.
        save_video (bool): If True, saves the video with annotations. Default is False.
        filename (str): The name of the output file where the video will be saved if save_video is True.
    """
    try:
        # Load video info and extract width, height, and frames per second (fps)
        video_info = sv.VideoInfo.from_video_path(video_path=video_path)
        w, h, fps = int(video_info.width), int(video_info.height), int(video_info.fps)

        frame_interval = fps // inference_per_sec

        model = YOLO(model)  # Load your custom-trained YOLO model
        tracker = sv.ByteTrack(frame_rate=fps)  # Initialize the tracker with the video's frame rate
        class_dict = model.names  # Get the class labels from the model
        
        # Capture the video from the given path
        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Error: couldn't open the video!")
        
        label = []

        frame_count  = 0

        # Process the video frame by frame
        while cap.isOpened():
            
            ret, frame = cap.read()
            if not ret:  # End of the video
                break

            frame_count += 1
            if frame_count % frame_interval != 0:
                continue
            # Make predictions on the current frame using the YOLO model
            result = model(frame)[0]
            detections = sv.Detections.from_ultralytics(result)  # Convert model output to Detections format
            detections = tracker.update_with_detections(detections=detections)  # Track detected objects


            # Filter detections based on confidence
            if detections.tracker_id is not None:
                detections = detections[(detections.confidence > confidence)]  # Keep detections with confidence greater than a threashold

                labels_1 = [f"{class_dict[cls_id]}" for cls_id in detections.class_id]
                
                label = labels_1 if len(labels_1) > len(label) else label

        
        return label


    except Exception as e:
        print(f"An error occurred: {e}")



if __name__ == '__main__':
    # Usage: python birds_detection.py <image-or-video> [model.pt]
    import sys
    path, model = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "./model.pt")
    predict = video_prediction if path.lower().endswith(('.mp4', '.avi', '.mov')) else image_prediction
    print(predict(path, model=model))
