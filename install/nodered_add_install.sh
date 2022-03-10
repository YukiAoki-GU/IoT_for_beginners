#!/usr/bin/bash
# USBカメラを使うため
sudo apt -y install fswebcam
#追加のNodeのインストール
cd ~/.node-red
npm install node-red-dashboard #ダッシュボード
npm install node-red-node-pi-gpio #GPIO
npm install node-red-contrib-teachable-machine #teachable machine
npm install node-red-contrib-image-output #イメージ出力
npm install node-red-contrib-python3-function #Python用
npm install node-red-contrib-usbcamera #USBカメラ
npm install node-red-node-base64 #Base64
npm audit fix
# Node-REDが自動起動されるように設定して起動
sudo systemctl enable nodered.service
sudo systemctl start nodered.service
