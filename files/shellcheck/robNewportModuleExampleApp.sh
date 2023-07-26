#!/bin/bash -i
export JAVA_HOME=/opt/android-studio-2021.3.1/android-studio/jbr
cd ~/github-thinkspan/rob-newport-module/example/android/ || exit
nvm use

/opt/android-studio-2021.3.1/android-studio/bin/studio.sh .
