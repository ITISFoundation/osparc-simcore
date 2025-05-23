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


qx.Class.define("osparc.jobs.RunsTableModel", {
  extend: qx.ui.table.model.Remote,

  construct: function(projectUuid = null, includeChildren = false) {
    this.base(arguments);

    this.__includeChildren = includeChildren;

    this.set({
      projectUuid,
    });

    const jobsCols = osparc.jobs.RunsTable.COLS;
    const colLabels = Object.values(jobsCols).map(col => col.label);
    const colIDs = Object.values(jobsCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    this.setSortColumnIndexWithoutSortingData(jobsCols.SUBMIT.column);
    this.setSortAscendingWithoutSortingData(false);
    Object.values(jobsCols).forEach(col => {
      this.setColumnSortable(col.column, Boolean(col.sortable));
    });
  },

  properties: {
    projectUuid: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeProjectUuid",
      apply: "reloadData",
    },

    runningOnly: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeRunningOnly",
      apply: "reloadData",
    },

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

    filterString: {
      nullable: true,
      check : "String",
      init: "",
      apply: "reloadData",
    },
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
  },

  members: {
    __includeChildren: false,

    // overridden
    _loadRowCount() {
      const offset = 0;
      const limit = 1;
      const orderBy = this.getOrderBy();
      const resolveWResponse = true;
      let promise;
      if (this.getProjectUuid()) {
        promise = osparc.store.Jobs.getInstance().fetchJobsHistory(this.getProjectUuid(), this.__includeChildren, offset, limit, orderBy, resolveWResponse);
      } else {
        const filters = this.getFilterString() ? { text: this.getFilterString() } : null;
        promise = osparc.store.Jobs.getInstance().fetchJobsLatest(this.getRunningOnly(), offset, limit, orderBy, filters, resolveWResponse);
      }
      promise
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
      const orderBy = this.getOrderBy();
        let promise;
        if (this.getProjectUuid()) {
          promise = osparc.store.Jobs.getInstance().fetchJobsHistory(this.getProjectUuid(), this.__includeChildren, offset, limit, orderBy);
        } else {
          const filters = this.getFilterString() ? { text: this.getFilterString() } : null;
          promise = osparc.store.Jobs.getInstance().fetchJobsLatest(this.getRunningOnly(), offset, limit, orderBy, filters);
        }
        return promise
          .then(jobs => {
            const data = [];
            const jobsCols = osparc.jobs.RunsTable.COLS;
            jobs.forEach(job => {
              data.push({
                [jobsCols.PROJECT_UUID.id]: job.getProjectUuid(),
                [jobsCols.PROJECT_NAME.id]: job.getProjectName(),
                [jobsCols.STATE.id]: osparc.data.Job.STATUS_LABELS[job.getState()] || job.getState(),
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
