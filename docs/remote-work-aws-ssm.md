# How to use VSCode on a remote private EC2
[reference](https://medium.com/@dbpprt/transparently-develop-on-an-ec2-instance-with-vscode-remote-ssh-through-ssm-6e5c5e599ee1)

## to use from the terminal

```bash
host i-* mi-*
User ec2-user
ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
```

## to use from VSCode

```bash
host i-*.*.*
User ec2-user
ProxyCommand bash -c "aws ssm start-session --target $(echo %h|cut -d'.' -f1) --profile $(echo %h|/usr/bin/cut -d'.' -f2) --region $(echo %h|/usr/bin/cut -d'.' -f3) --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
```
