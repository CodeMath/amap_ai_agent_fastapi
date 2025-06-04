#!/bin/bash

# 현재 디렉토리를 빌드해서 ECR 배포 하기

aws ecr get-login-password --region ap-northeast-2 --profile v3ecr | docker login --username AWS --password-stdin 861276089671.dkr.ecr.ap-northeast-2.amazonaws.com

# 빌드
docker build --platform linux/amd64 -t 861276089671.dkr.ecr.ap-northeast-2.amazonaws.com/amap:latest .

# 푸시
docker push 861276089671.dkr.ecr.ap-northeast-2.amazonaws.com/amap:latest