# Controlling Drone with Body Postures
A makerfaire 2018 project. 

## Overview
![alt text](./imgs/architecture.png)

**Prerequisites**
- Docker
- AWS EC2 GPU (G2/P2/P3)
- Additional wireless network adaptor to connec to tello
- Camera ( pc webcam will do just fine )

I initially developed this with a cpu as a target server  to process the images, but it \
unsurprisingly turned out to be very slow. Also, midway developement I was thinking about \
using AWS Kinesis Streams to stream my video frames to the server, instead of using low level \
sockets. However, it turned out to be quite of a hassle, as I had to think about how to reorder \
the frames as they arrive after being processed in the server. As such, you will see many different configuration \
and environment files lying around in this repo, you don't have to pay attention to them. Just \
follow the steps below and you should be on your way to moving the drones with your hands! :)

## 1) Setup the application


## 2) Setup the AWS GPU EC2

## 3) Setup the tello connection

## 4) Run the application

## 5) Libraries Use
tf-openpose
opencv