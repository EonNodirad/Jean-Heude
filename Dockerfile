FROM python3.11

WORKDIR /backend_python
COPY . .
RUN pip install -r requirements.txt
CMD [ "python", "main.py" ]