docker-machine env makerfaire-gpu-2 | Invoke-Expression
docker stop $(docker ps -aq)
docker run --runtime=nvidia -it --rm -p 8089:8089  houdinisparks/pose_recogniser:mf-gpu-30stimeout bash