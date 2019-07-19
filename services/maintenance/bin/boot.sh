exec start-notebook.sh --NotebookApp.password=$(python -c "from notebook.auth import passwd; print(passwd('${MAINTENANCE_PASSWORD}'))")
