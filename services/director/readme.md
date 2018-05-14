# director

## dockerfile

- Uses multi-stage dockerfile to extend a common stack of layers into production or development images
- Main difference between development and production stages is whether the code gets copied or not inside of the image
- Development stage is set first to avoid re-building when files are changed
- ``boot.sh`` is necessary to activate the virtual environment inside of the docker

```bash

  # development image
  docker build --target development -t director:dev .

  # production image
  docker build -t director:prod .
  # or
  docker build --target production -t director:prod .

```
