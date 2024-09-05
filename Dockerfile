FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY claudepicker.py .
COPY k4_voice_dictionary.py .
COPY sadtalker.json .
COPY .env .

#RUN apt-get update && apt-get install -y ffmpeg

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
