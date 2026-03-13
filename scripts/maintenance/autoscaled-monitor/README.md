# summary of autoscaled nodes on a deployment

```bash
./osparc_clusters.py --help # to print the help
```


# example usage

```bash
./osparc_clusters.py --repo-config=PATH/TO/DEPLOYX/REPO.CONFIG summary # this will show the current auto-scaled machines in DEPLOYX
```

```bash
./osparc_clusters.py --repo-config=PATH/TO/DEPLOYX/REPO.CONFIG --ssh-key-path=PATH/TO/DEPLOYX/SSH_KEY summary # this will show the current auto-scaled machines in DEPLOYX AND also what is running on them
```

```bash
./osparc_clusters.py --repo-config=PATH/TO/DEPLOYX/REPO.CONFIG --ssh-key-path=PATH/TO/DEPLOYX/SSH_KEY summary --user-id=XX # this will show the current auto-scaled machines in DEPLOYX AND also what is running on them for user-id XX
```
