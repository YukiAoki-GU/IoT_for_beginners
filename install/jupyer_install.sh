#!/usr/bin/bash

#aptの更新
sudo apt -y update

#git cloneのインストール
sudo apt -y install git 
#ロケールを日本へ
echo 'LANG=ja_JP.UTF-8' | sudo tee /etc/default/locale > /dev/null

#JupyterLabのインストール
sudo apt -y install python3-pip
sudo pip3 install jupyterlab
#jupyter_configを~/.jupyter/に作る
jupyter-lab --generate-config

#jupyter_configに追記
{
echo "c = get_config()"
echo "c.NotebookApp.ip = '*'"
echo "c.NotebookApp.open_browser = False"
echo "c.NotebookApp.port = 8080"
echo "c.NotebookApp.token = 'jupyter'"
echo "c.NotebookApp.password = 'sha1:6c5ae55baca5:5d9bde50836b504ef4241afb82c1c599475276f5'"
} >> jupyter_lab_config.py

mv jupyter_lab_config.py ~/.jupyter/

# Jupyterlab.serviceをsystemdに追加し，自動起動されるよう設定し，起動
{
echo "[Unit]"
echo "Description=Jupyter lab"
echo ""
echo "[Service]"
echo "Type=simple"
echo "User="$USER
echo "ExecStart=/usr/local/bin/jupyter-lab --config=/home/"$USER"/.jupyter/jupyter_lab_config.py"
echo "WorkingDirectory=/home/"$USER""
echo ""
echo "[Install]"
echo "WantedBy=multi-user.target"
} >> Jupyterlab.service

sudo mv Jupyterlab.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable Jupyterlab.service
sudo systemctl start Jupyterlab.service
