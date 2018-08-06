
docker-machine start makerfaire-gpu
docker-machine env makerfaire-gpu | Invoke-Expression
docker run --runtime=nvidia -it --rm -p 8089:8089 houdinisparks/pose_recogniser:mf-gpu-2