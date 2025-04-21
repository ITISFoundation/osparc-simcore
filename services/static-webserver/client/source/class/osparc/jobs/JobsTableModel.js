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


qx.Class.define("osparc.jobs.JobsTableModel", {
  extend: qx.ui.table.model.Remote,

  construct() {
    this.base(arguments);

    const jobsCols = osparc.jobs.JobsTable.COLS;
    const colLabels = Object.values(jobsCols).map(col => col.label);
    const colIDs = Object.values(jobsCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    this.setSortColumnIndexWithoutSortingData(jobsCols.SUBMIT.column);
    this.setSortAscendingWithoutSortingData(false);
    this.setColumnSortable(jobsCols.STATE.column, false);
    this.setColumnSortable(jobsCols.INFO.column, false);
    this.setColumnSortable(jobsCols.ACTION_STOP.column, false);
    this.setColumnSortable(jobsCols.ACTION_RUN.column, false);
    this.setColumnSortable(jobsCols.ACTION_RETRY.column, false);
    this.setColumnSortable(jobsCols.ACTION_MORE.column, false);
  },

  properties: {
    isFetching: {
      check: "Boolean",
      init: false,
      event: "changeFetching"
    },

    orderBy: {
      check: "Object",
      init: {
        field: "submitted_at",
        direction: "desc"
      }
    },
  },

  members: {
    // overridden
    _loadRowCount() {
      const offset = 0;
      const limit = 1;
      const resolveWResponse = true;
      osparc.store.Jobs.getInstance().fetchJobs(offset, limit, JSON.stringify(this.getOrderBy()), resolveWResponse)
        .then(resp => {
          this._onRowCountLoaded(resp["_meta"].total)
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
      const getFetchPromise = (offset, limit) => {
        return osparc.store.Jobs.getInstance().fetchJobs(offset, limit, JSON.stringify(this.getOrderBy()))
          .then(jobs => {
            const data = [];
            const jobsCols = osparc.jobs.JobsTable.COLS;
            jobs.forEach(job => {
              data.push({
                [jobsCols.PROJECT_UUID.id]: job.getProjectUuid(),
                [jobsCols.PROJECT_NAME.id]: job.getProjectName(),
                [jobsCols.STATE.id]: job.getState(),
                [jobsCols.SUBMIT.id]: job.getSubmittedAt() ? osparc.utils.Utils.formatDateAndTime(job.getSubmittedAt()) : "-",
                [jobsCols.START.id]: job.getStartedAt() ? osparc.utils.Utils.formatDateAndTime(job.getStartedAt()) : "-",
                [jobsCols.END.id]: job.getEndedAt() ? osparc.utils.Utils.formatDateAndTime(job.getEndedAt()) : "-",
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
