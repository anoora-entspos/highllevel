#to run: python3 -m uvicorn new:app --reload 
from fastapi import FastAPI, BackgroundTasks
import requests
from pydub import AudioSegment
import boto3
import base64
from io import BytesIO
import uuid
from pydantic import BaseModel  
import time
import tempfile
from claudepicker import pick_voice
from elevenlabs.client import ElevenLabs
import firebase_admin
from firebase_admin import credentials, storage, firestore
from google.cloud import firestore
import os
import uuid
import time
from dotenv import load_dotenv


load_dotenv()

app = FastAPI()


# Define your AWS credentials (Use environment variables or IAM roles in production)
aws_access_key_id = os.getenv("aws_access_key_id")
aws_secret_access_key = os.getenv("aws_secret_access_key")

# Define the name of the S3 bucket
S3_BUCKET_NAME = "intermediate-result"

# Create a Boto3 S3 client
s3 = boto3.client('s3',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key)

# Eleven Labs API Configuration
XI_API_KEY = os.getenv("XI_API_KEY")
client = ElevenLabs(
api_key=XI_API_KEY,
)

# Other model URLs
RUNPOD_FLUX_URL = "https://api.runpod.ai/v2/xkdpxqooff5zu7/run"
RUNPOD_VIDEO_RETALKING_URL = "https://api.runpod.ai/v2/5i72iyq2gojepq/run"
RUNPOD_LIVE_PORTRAIT_URL = "https://api.runpod.ai/v2/ids13oa96hdn6a/run"
RUNPOD_STATUS_FLUX_URL = "https://api.runpod.ai/v2/xkdpxqooff5zu7/status/{request_id}"
RUNPOD_STATUS_VIDEO_RETALKING_URL = "https://api.runpod.ai/v2/5i72iyq2gojepq/status/{request_id}"
RUNPOD_STATUS_LIVE_PORTRAIT_URL = "https://api.runpod.ai/v2/ids13oa96hdn6a/status/{request_id}"

# Set Google Application Credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'sadtalker.json'

# Initialize Firebase Admin SDK with your service account
cred = credentials.Certificate('sadtalker.json')
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Specify the bucket name
bucket_name = 'sadtalker-d67ba.appspot.com'

#runpod token
runpod_auth=os.environ.get("runpod_auth")

#runpod apis headers
api_headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer NQWCNZIZ01WIU9OXPBUL39TS06EM1O4NE28HZDT9"
        }

def upload_to_s3(file_data, filename, content_type):
    # Create a BytesIO object from the binary file data
    buffer = BytesIO(file_data)
    buffer.seek(0)  # Ensure the buffer's position is at the start
    
    # Upload the file-like object to S3
    s3.upload_fileobj(buffer, S3_BUCKET_NAME, filename, ExtraArgs={"ContentType": content_type})
    
    # Return the URL of the uploaded file
    return f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{filename}"


def calculate_audio_duration(audio_url: str) -> float:
    try:
        # Fetch the audio file from the URL
        response = requests.get(audio_url)
        response.raise_for_status()
        
        # Load the audio file into pydub's AudioSegment
        audio = AudioSegment.from_file(BytesIO(response.content))
        
        # Calculate the duration in seconds
        duration = len(audio) / 1000.0
        
        return duration
    except Exception as e:
        print(f"Error occurred: {e}")
        return None


def check_status(status_url, polling_interval):
    while True:
        response = requests.get(status_url, headers=api_headers)
        print(f"Status URL: {status_url}")
        print(f"Status Code: {response.status_code}")
        try:
            status_data = response.json()
            status = status_data.get("status")

            if status == "COMPLETED":
                output = status_data.get("output")
                # If output is a list, take the first item
                if isinstance(output, list) and len(output) > 0:
                    return output[0].split(',')[1]  # Remove the "data:image/png;base64," prefix
                return output
            elif status in ["FAILED", "CANCELLED"]:
                raise Exception(f"Model processing {status}.")
        except ValueError as e:
            print(f"Response content: {response.text}")
            raise Exception(f"Failed to parse JSON response: {e}")
        
        time.sleep(polling_interval)
        
def generate_speech_with_eleven_labs(text, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            VOICE_ID = pick_voice(prompt)
            
            # Generate speech using the client
            audio = client.generate(
                text=text,
                voice=VOICE_ID,
                model="eleven_multilingual_v2"
            )
            
            # Combine the audio chunks into a single byte string
            audio_bytes = b"".join(audio)
            
            return audio_bytes
        
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception(f"Failed to generate speech after {max_retries} attempts: {str(e)}")
    
    # This line should never be reached due to the exception in the loop,
    # but it's here to satisfy the function's return expectation
    return None

def upload_image_to_firebase(image_data):
    # Generate a unique filename for the image
    unique_filename = f"{uuid.uuid4()}.png"
    remote_file_path = f'runpodimages/{unique_filename}'
    
    bucket = storage.bucket(bucket_name)

    # Create a blob (object) in the bucket and upload the file
    blob = bucket.blob(remote_file_path)
    blob.upload_from_file(image_data, content_type='image/png')

    # Generate a signed URL with a download token
    expiration_time_seconds = 36576576500  # Set expiration time as needed (in seconds)
    image_signed_url = blob.generate_signed_url(expiration=expiration_time_seconds)

    print(f'Image uploaded successfully! Public URL with token: {image_signed_url}')
    
    return image_signed_url

# Modify the upload_video_to_firebase function
def upload_video_to_firebase(video_path, image_data, prompt, userid):
    thumbnailUrl = upload_image_to_firebase(image_data)

    # Generate a unique filename for the video
    unique_filename = f"{uuid.uuid4()}.mp4"
    remote_file_path = f'runpodvideos/{unique_filename}'
    
    bucket = storage.bucket(bucket_name)

    # Create a blob (object) in the bucket and upload the file
    blob = bucket.blob(remote_file_path)
    blob.upload_from_filename(video_path)

    # Generate a signed URL with a download token
    expiration_time_seconds = 36576576500  # Set expiration time as needed (in seconds)
    signed_url = blob.generate_signed_url(expiration=expiration_time_seconds)

    print(f'Video uploaded successfully! Public URL with token: {signed_url}')

    # Firestore document data
    document_data = {
        'addToFeed': False,
        'commentsCount': 0,
        'likes': [],
        'shares': [],
        'thumbnail': thumbnailUrl,
        'uploaderId': userid,
        'videoCaption': prompt,
        'timestamp': firestore.SERVER_TIMESTAMP,
        'videoUrl': signed_url
    }

    # Initialize Firestore
    db = firestore.Client()

    # Add a document to Firestore
    collection_name = 'videosList'
    db.collection(collection_name).add(document_data)

    print(f'Document added to Firestore collection: {collection_name}')

# Dictionary to store job status
jobs = {}

def run_animation_job(job_id, prompt, text, userid):
    # Simulate processing
    jobs[job_id] = 'IN_PROGRESS'
    try:

            try:
                print(f"api headerssss ${api_headers}")
                sd3_headers = api_headers
                flux_response = requests.post(RUNPOD_FLUX_URL, headers=sd3_headers, json={"input":{
                    
                    "prompt": prompt + str(",upper body, portrait, looking at the viewer, fully clothed"),
                    "num_outputs": 1,
                    "aspect_ratio": "9:16",
                    "output_format": "png",
                    "output_quality": 90
            
                }})

                # Ensure the request was successful
                if flux_response.status_code != 200:
                    print(f"SD3 Request failed with status code: {flux_response.status_code}")
                    print(f"Response body: {flux_response.text}")
                    return {"error": "Failed to request image generation"}, 500
                
                flux_job_id = flux_response.json().get("id")
                if not flux_job_id:
                    print("Failed to retrieve job_id from SD3 response.")
                    return {"error": "No job_id returned from SD3"}, 500
                
                flux_status_url = RUNPOD_STATUS_FLUX_URL.format(request_id=flux_job_id)

                # Step 2: Check SD3 model status (poll every 5 seconds)
                base64_image = check_status(flux_status_url, polling_interval=5)
                
                # Step 3: Upload the image to S3 and get the URL
                image_filename = f"{uuid.uuid4()}.png"
                s3_image_url = upload_to_s3(base64.b64decode(base64_image), image_filename, "image/png")
            except Exception as e:
                raise Exception(f"Image generation failed: {str(e)}")

        # Animation generation
            try:
                live_portrait_headers = api_headers
                live_portrait_response = requests.post(RUNPOD_LIVE_PORTRAIT_URL, headers=live_portrait_headers, json={
                    "input":{
                "face_image": s3_image_url,
                "driving_video":"https://firebasestorage.googleapis.com/v0/b/sadtalker-d67ba.appspot.com/o/edit.mp4?alt=media&token=2ee35c02-a96c-4b93-a1ec-50a96d3801ac",
                "live_portrait_dsize": 768,
                "live_portrait_scale": 2.3,
                "video_frame_load_cap": 0,
                "live_portrait_lip_zero": True,
                "live_portrait_relative": True,
                "live_portrait_vx_ratio": 0,
                "live_portrait_vy_ratio": -0.12,
                "live_portrait_stitching": True,
                "video_select_every_n_frames": 1,
                "live_portrait_eye_retargeting": False,
                "live_portrait_lip_retargeting": False,
                "live_portrait_lip_retargeting_multiplier": 1,
                "live_portrait_eyes_retargeting_multiplier": 1
            } 
                })

                if live_portrait_response.status_code != 200:
                    print(f"Live Portrait Request failed with status code: {live_portrait_response.status_code}")
                    print(f"Response body: {live_portrait_response.text}")
                    return {"error": "Failed to request Live Portrait"}, 500

                live_portrait_job_id = live_portrait_response.json().get("id")
                if not live_portrait_job_id:
                    print("Failed to retrieve job_id from Live Portrait response.")
                    return {"error": "No job_id returned from Live Portrait"}, 500

                live_portrait_status_url = RUNPOD_STATUS_LIVE_PORTRAIT_URL.format(request_id=live_portrait_job_id)

                # Step 5: Check Live Portrait model status (poll every 10 seconds)
                base64_video = check_status(live_portrait_status_url, polling_interval=10)

                # Step 6: Upload the Live Portrait video to S3 and get the URL
                live_portrait_video_filename = f"{uuid.uuid4()}.mp4"
                s3_live_portrait_video_url = upload_to_s3(base64.b64decode(base64_video), live_portrait_video_filename, "video/mp4")
            except Exception as e:
                raise Exception(f"Animation generation failed: {str(e)}")


            try:
                audio_data = generate_speech_with_eleven_labs(text, prompt)

                # Step 8: Upload the audio to S3 and get the URL
                audio_filename = f"{uuid.uuid4()}.mp3"
                s3_audio_url = upload_to_s3(audio_data, audio_filename, "audio/mpeg")
            except Exception as e:
                raise Exception(f"Speech generation failed: {str(e)}")

  
            try:
                duration = calculate_audio_duration(s3_audio_url)
                if duration is None:
                    duration = 15

                
                video_headers = api_headers
                video_response = requests.post(RUNPOD_VIDEO_RETALKING_URL, headers=video_headers, json={
                    "input": {
                        "face": s3_live_portrait_video_url,  # URL of the Live Portrait video
                        "input_audio": s3_audio_url,  # S3 audio URL
                        "audio_duration": int(duration)  # Example duration, adjust accordingly
                    }
                })

                # Ensure the request was successful
                if video_response.status_code != 200:
                    print(f"Video retalking request failed with status code: {video_response.status_code}")
                    print(f"Response body: {video_response.text}")
                    return {"error": "Failed to request video retalking"}, 500

                video_job_id = video_response.json().get("id")
                if not video_job_id:
                    print("Failed to retrieve job_id from video retalking response.")
                    return {"error": "No job_id returned from video retalking service"}, 500

                video_status_url = RUNPOD_STATUS_VIDEO_RETALKING_URL.format(request_id=video_job_id)
                try:
                    final_video = check_status(video_status_url, polling_interval=15)
                    print(f"Final video response: {final_video}")

                    base64_data = final_video.replace("data:video/mp4;base64,", "")
                    print(f"Base64 data length: {len(base64_data)}")

                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
                        temp_video.write(base64.b64decode(base64_data))
                        temp_video.flush()
                        temp_video_path = temp_video.name

                    print(f"Temporary video file created at: {temp_video_path}")

                    # Ensure base64_image is correctly formatted
                    if base64_image:
                        image_data = BytesIO(base64.b64decode(base64_image))
                    else:
                        raise ValueError("Base64 image data is missing or invalid")
                    try:
                    # Upload to Firebase
                        upload_video_to_firebase(temp_video_path, image_data, prompt, userid)
                    except Exception as e:
                        print(f"Error during upload: {e}")
                        return {"error": "Failed to upload video to Firebase"}, 500


                    # Clean up temporary file
                    os.unlink(temp_video_path)
                    

                except Exception as e:
                    print(f"Unexpected error: {e}")
                    return {"error": "Internal server error"}, 500    
            except Exception as e:
                raise Exception(f"Video processing or upload failed: {str(e)}")
            jobs[job_id] = 'COMPLETED'
            # Final step: update status and add result URL
            return {"message": "Video processed and uploaded successfully"}
            
    except Exception as e:
            return {"error": str(e)}
    
# Define a Pydantic model for the request body  
class AnimationJob(BaseModel):  
    prompt: str  
    text: str  
    userid: str  
    
@app.post("/create_animation")  
async def create_animation(job: AnimationJob, background_tasks: BackgroundTasks):  
    job_id = str(uuid.uuid4())  
    
    # Store the job in 'queue' state initially  
    jobs[job_id] = 'NOT_FOUND'  
    
    # Add the task to background so it runs after returning response  
    background_tasks.add_task(run_animation_job, job_id, job.prompt, job.text, job.userid)  
    
    return {"message": "Job started", "job_id": job_id}  

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    status = jobs.get(job_id, "NOT_FOUND")
    return {"job_id": job_id, "status": status}






