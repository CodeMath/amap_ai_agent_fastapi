# AWS Lambda 컨테이너 이미지용 베이스
FROM public.ecr.aws/lambda/python:3.12

# 의존성 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Lambda 핸들러 지정
CMD ["main.handler"]