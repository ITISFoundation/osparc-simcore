# service integration library


This is the o2sparc's service integration library or ``ooil`` in short


SEE how is it used in Makefiles in https://github.com/ITISFoundation/cookiecutter-osparc-service


#### What is the .osparc folder and its content?
'osparc config' is a set of stardard file forms (yaml) that the user fills provides in order to describe how her service works and integrates with osparc. It may contain:
  - config files are stored under '.osparc/' folder in the root repo folder (analogous to other configs like .github, .vscode, etc)
  - configs are parsed and validated into pydantic models
  - models can be serialized/deserialized into label annotations on images. This way, the config is attached to the service during it's entire lifetime.
  - config should provide enough information about that context to allow building an image and running a container on a single command call.
