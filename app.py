from flask import Flask, render_template, Response, request, jsonify, send_from_directory
import os
import time
import random
import string
import cv2

app = Flask(__name__)

# Paths and configurations
CLIPS_FOLDER = './clips'
CAM_RESOLUTIONS = {
    1: (1920, 1080),
    2: (1920, 1080),
    3: (1920, 1080)
}
FPS = {
    1: 30,  # Default FPS for camera 1
    2: 30,  # Default FPS for camera 2
    3: 30   # Default FPS for camera 3
}

# Ensure clips folder exists
os.makedirs(CLIPS_FOLDER, exist_ok=True)

# Camera handlers (cv2.VideoCapture)
cameras = {
    1: cv2.VideoCapture(0),  # Change index based on your system
    2: cv2.VideoCapture(1),
    3: cv2.VideoCapture(2)
}

def generate_random_string(length=5):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Set camera resolution and FPS
for cam_id, camera in cameras.items():
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_RESOLUTIONS[cam_id][0])
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_RESOLUTIONS[cam_id][1])
    camera.set(cv2.CAP_PROP_FPS, FPS[cam_id])

@app.route('/')
def index():
    # Serve the index page
    return render_template('index.html')

@app.route('/live')
def live():
    # Serve the live streaming page
    return render_template('live.html')

@app.route('/stream/<int:cam_id>')
def stream(cam_id):
    # Camera stream generator
    def generate_frames():
        camera = cameras[cam_id]
        while True:
            success, frame = camera.read()
            if not success:
                break
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/record', methods=['POST'])
def record():
    # Get camera ID and duration from the client
    cam_id = int(request.form.get('cam_id'))
    duration = int(request.form.get('duration'))  # duration in seconds

    # Check if the camera is accessible
    camera = cameras.get(cam_id)
    if not camera or not camera.isOpened():
        return jsonify({'error': 'Camera not available'}), 400

    # Get the actual FPS from the camera
    fps = camera.get(cv2.CAP_PROP_FPS)
    if fps <= 0:  # Fallback if the FPS can't be determined
        fps = FPS[cam_id]  # Use predefined FPS if camera doesn't provide it

    # Generate a random filename for the clip
    clip_id = generate_random_string()
    clip_path = os.path.join(CLIPS_FOLDER, f'{clip_id}.mp4')

    # Set video codec and writer
    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # Using 'mp4v' codec
    resolution = CAM_RESOLUTIONS[cam_id]  # Get resolution for the camera

    # Initialize the VideoWriter
    out = cv2.VideoWriter(clip_path, fourcc, fps, resolution)

    if not out.isOpened():
        return jsonify({'error': 'Failed to open video writer'}), 500

    # Calculate the number of frames to record based on FPS and duration
    total_frames = int(fps * duration)
    frames_recorded = 0

    while frames_recorded < total_frames:
        ret, frame = camera.read()
        if ret:
            # Resize frame to match the recording resolution
            frame = cv2.resize(frame, resolution)
            out.write(frame)  # Write frame to the video file
            frames_recorded += 1
        else:
            break

    # Release resources
    out.release()

    return jsonify({'clip_id': clip_id})


@app.route('/clips/<clip_id>.mp4')
def get_clip(clip_id):
    # Serve the saved video clip
    return send_from_directory(CLIPS_FOLDER, f'{clip_id}.mp4')

@app.route('/list_clips')
def list_clips():
    # Return a list of available clips
    clips = [f for f in os.listdir(CLIPS_FOLDER) if f.endswith('.mp4')]
    return jsonify(clips)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
