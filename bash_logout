if [ -z "${SSH_CONNECTION}" ]; then
  echo "`date` killing SSH agent PID $SSH_AGENT_PID for user `whoami`" >> /tmp/bash_logout
  kill $SSH_AGENT_PID
fi
echo "`date` last ~/.bash_logout for user `whoami`" >> /tmp/bash_logout
