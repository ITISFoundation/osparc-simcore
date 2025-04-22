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

  construct(projectUuid) {
    this.base(arguments);

    const subJobsCols = osparc.jobs.SubRunsTable.COLS;
    const colLabels = Object.values(subJobsCols).map(col => col.label);
    const colIDs = Object.values(subJobsCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    this.setSortColumnIndexWithoutSortingData(subJobsCols.START.column);
    this.setSortAscendingWithoutSortingData(false);
    Object.values(subJobsCols).forEach(col => {
      this.setColumnSortable(col.column, false);
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
  },

  members: {
    // overridden
    _loadRowCount() {
      osparc.store.Jobs.getInstance().fetchSubJobs(this.getProjectUuid())
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
        return osparc.store.Jobs.getInstance().fetchSubJobs(this.getProjectUuid())
          .then(subJobs => {
            const data = [];
            const subJobsCols = osparc.jobs.SubRunsTable.COLS;
            subJobs.forEach(subJob => {
              data.push({
                [subJobsCols.PROJECT_UUID.id]: subJob.getProjectUuid(),
                [subJobsCols.NODE_ID.id]: subJob.getNodeId(),
                [subJobsCols.NODE_NAME.id]: subJob.getNodeName(),
                [subJobsCols.SOLVER.id]: subJob.getImage()["name"] + ":" + subJob.getImage()["tag"],
                [subJobsCols.STATE.id]: subJob.getState(),
                [subJobsCols.PROGRESS.id]: subJob.getProgress() * 100 + "%",
                [subJobsCols.START.id]: subJob.getStartedAt() ? osparc.utils.Utils.formatDateAndTime(subJob.getStartedAt()) : "-",
                [subJobsCols.END.id]: subJob.getEndedAt() ? osparc.utils.Utils.formatDateAndTime(subJob.getEndedAt()) : "-",
                [subJobsCols.IMAGE.id]: subJob.getImage() ? osparc.utils.Utils.formatDateAndTime(subJob.getEndedAt()) : "-",
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
