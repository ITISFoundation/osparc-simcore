/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.jobs.SubRunsTableModel", {
  extend: qx.ui.table.model.Remote,

  construct: function(projectUuid) {
    this.base(arguments);

    const subJobsCols = osparc.jobs.SubRunsTable.COLS;
    const colLabels = Object.values(subJobsCols).map(col => col.label);
    const colIDs = Object.values(subJobsCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    this.setSortColumnIndexWithoutSortingData(subJobsCols.START.column);
    this.setSortAscendingWithoutSortingData(false);
    Object.values(subJobsCols).forEach(col => {
      this.setColumnSortable(col.column, Boolean(col.sortableMap));
    });

    this.setProjectUuid(projectUuid);
  },

  properties: {
    projectUuid: {
      check: "String",
      nullable: true,
    },

    isFetching: {
      check: "Boolean",
      init: false,
      event: "changeFetching"
    },

    orderBy: {
      check: "Object",
      init: {
        field: "started_at", // started_at
        direction: "desc"
      }
    },
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
  },

  members: {
    // overridden
    sortByColumn(columnIndex, ascending) {
      const subJobsCols = osparc.jobs.SubRunsTable.COLS;
      const colInfo = Object.values(subJobsCols).find(col => col.column === columnIndex);
      this.setOrderBy({
        field: colInfo.sortableMap,
        direction: ascending ? "asc" : "desc"
      })
      this.base(arguments, columnIndex, ascending)
    },

    // overridden
    _loadRowCount() {
      osparc.store.Jobs.getInstance().fetchSubJobs(this.getProjectUuid(), this.getOrderBy())
        .then(subJobs => {
          this._onRowCountLoaded(subJobs.length)
        })
        .catch(() => {
          this._onRowCountLoaded(null)
        })
    },

    // overridden
    _loadRowData(firstRow, qxLastRow) {
      this.setIsFetching(true);

      const lastRow = Math.min(qxLastRow, this._rowCount - 1);
      // Returns a request promise with given offset and limit
      const getFetchPromise = () => {
        return osparc.store.Jobs.getInstance().fetchSubJobs(this.getProjectUuid(), this.getOrderBy())
          .then(subJobs => {
            const data = [];
            const subJobsCols = osparc.jobs.SubRunsTable.COLS;
            subJobs.forEach(subJob => {
              const serviceKey = subJob.getImage()["name"];
              const serviceVersion = subJob.getImage()["tag"];
              const serviceMetadata = osparc.store.Services.getLatest(serviceKey);
              let appName = serviceKey.split("/").pop();
              if (serviceMetadata) {
                appName = serviceMetadata["name"];
              }
              const displayVersion = osparc.store.Services.getVersionDisplay(serviceKey, serviceVersion) || serviceVersion;
              const startedAt = subJob.getStartedAt();
              const endedAt = subJob.getEndedAt();
              let duration = "-";
              if (startedAt && endedAt && endedAt > startedAt) {
                const diffMs = endedAt - startedAt; // Difference in milliseconds
                const diffSeconds = Math.floor(diffMs / 1000) % 60;
                const diffMinutes = Math.floor(diffMs / (1000 * 60)) % 60;
                const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                duration = `${String(diffHours).padStart(2, "0")}:${String(diffMinutes).padStart(2, "0")}:${String(diffSeconds).padStart(2, "0")}`;
              }
              data.push({
                [subJobsCols.PROJECT_UUID.id]: subJob.getProjectUuid(),
                [subJobsCols.NODE_ID.id]: subJob.getNodeId(),
                [subJobsCols.NODE_NAME.id]: subJob.getNodeName(),
                [subJobsCols.APP.id]: appName + ":" + displayVersion,
                [subJobsCols.STATE.id]: osparc.data.Job.STATUS_LABELS[subJob.getState()] || subJob.getState(),
                [subJobsCols.PROGRESS.id]: subJob.getProgress() * 100 + "%",
                [subJobsCols.START.id]: startedAt ? osparc.utils.Utils.formatDateAndTime(startedAt) : "-",
                [subJobsCols.END.id]: endedAt ? osparc.utils.Utils.formatDateAndTime(endedAt) : "-",
                [subJobsCols.DURATION.id]: duration,
                [subJobsCols.CREDITS.id]: subJob.getOsparcCredits() === null ? "-" : subJob.getOsparcCredits(),
              });
            });
            return data;
          });
      };

      // Divides the model row request into several server requests to comply with the number of rows server limit
      const reqLimit = lastRow - firstRow + 1; // Number of requested rows
      const nRequests = Math.ceil(reqLimit / this.self().SERVER_MAX_LIMIT);
      if (nRequests > 1) {
        const requests = [];
        for (let i=firstRow; i <= lastRow; i += this.self().SERVER_MAX_LIMIT) {
          requests.push(getFetchPromise(i, i > lastRow - this.self().SERVER_MAX_LIMIT + 1 ? reqLimit % this.self().SERVER_MAX_LIMIT : this.self().SERVER_MAX_LIMIT))
        }
        Promise.all(requests)
          .then(responses => this._onRowDataLoaded(responses.flat()))
          .catch(err => {
            console.error(err);
            this._onRowDataLoaded(null);
          })
          .finally(() => this.setIsFetching(false));
      } else {
        getFetchPromise(firstRow, reqLimit)
          .then(data => {
            this._onRowDataLoaded(data);
          })
          .catch(err => {
            console.error(err)
            this._onRowDataLoaded(null);
          })
          .finally(() => this.setIsFetching(false));
      }
    }
  }
})
