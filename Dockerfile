FROM registry.cn-hangzhou.aliyuncs.com/numen/base

RUN mkdir /app
RUN mkdir /app/logs
#开始复制程序
WORKDIR /app
COPY requirements.txt /app


RUN pip3 install --no-cache-dir -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com


RUN chmod -R 777 /app

COPY settings.xml /app
COPY Log.py /app
COPY start.py /app

RUN chmod -R 777 /app

ENTRYPOINT ["python3", "./start.py" ]
