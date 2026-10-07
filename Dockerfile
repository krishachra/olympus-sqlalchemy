FROM public.ecr.aws/d3j8x8q7/olympus-base-python:latest

WORKDIR /app

COPY . /app

RUN pip install "typing-extensions>=4.6.0" "pytest==8.4.2" --no-cache-dir -q

CMD ["/bin/bash"]
