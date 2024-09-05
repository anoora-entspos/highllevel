
FROM public.ecr.aws/lambda/python:3.10

COPY requirements.txt .
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY main.py ${LAMBDA_TASK_ROOT}
COPY claudepicker.py ${LAMBDA_TASK_ROOT}
COPY k4_voice_dictionary.py ${LAMBDA_TASK_ROOT}
COPY sadtalker.json ${LAMBDA_TASK_ROOT}


CMD [ "main.handler" ]