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

  construct(filters) {
    this.base(arguments);

    const jobsCols = osparc.jobs.JobsTable.COLS;
    const colLabels = Object.values(jobsCols).map(col => col.label);
    const colIDs = Object.values(jobsCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    if (filters) {
      this.setFilters(filters);
    }

    this.setSortColumnIndexWithoutSortingData(jobsCols.SUBMIT.column);
    this.setSortAscendingWithoutSortingData(false);
    this.setColumnSortable(jobsCols.INFO.column, false);
    this.setColumnSortable(jobsCols.ACTION_STOP.column, false);
    this.setColumnSortable(jobsCols.ACTION_DELETE.column, false);
    this.setColumnSortable(jobsCols.ACTION_LOGS.column, false);
  },

  properties: {
    isFetching: {
      check: "Boolean",
      init: false,
      event: "changeFetching"
    },

    filters: {
      check: "Object",
      init: null,
      apply: "reloadData", // force reload
    },

    orderBy: {
      check: "Object",
      init: {
        field: "started_at",
        direction: "desc"
      }
    },
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
    COLUMN_ID_TO_DB_COLUMN_MAP: {
      0: "started_at",
    },
  },

  members: {
    // this should be done by the backend
    __filterJobs: function(jobs) {
      const filters = this.getFilters();
      return jobs.filter(job => {
        if (filters) {
          let match = false;
          [
            "jobId",
            "solver",
            "status",
            "instance",
          ].forEach(filterableField => {
            const getter = "get" + qx.lang.String.firstUp(filterableField);
            const value = job[getter]();
            // lowercase both
            if (!match && value && value.toLowerCase().includes(filters.text.toLowerCase())) {
              match = true;
            }
          });
          return match;
        }
        return true;
      });
    },

    // overridden
    sortByColumn(columnIndex, ascending) {
      this.setOrderBy({
        field: this.self().COLUMN_ID_TO_DB_COLUMN_MAP[columnIndex],
        direction: ascending ? "asc" : "desc"
      })
      this.base(arguments, columnIndex, ascending);
    },

    // overridden
    _loadRowCount() {
      const urlParams = {
        offset: 0,
        limit: 1,
        filters: this.getFilters() ?
          JSON.stringify({
            "started_at": this.getFilters()
          }) :
          null,
        orderBy: JSON.stringify(this.getOrderBy()),
      };
      const options = {
        resolveWResponse: true
      };
      osparc.store.Jobs.getInstance().fetchJobs(urlParams, options)
        .then(jobs => {
          const filteredJobs = this.__filterJobs(jobs);
          this._onRowCountLoaded(filteredJobs.length);
        })
        .catch(() => this._onRowCountLoaded(null));
    },

    // overridden
    _loadRowData(firstRow, qxLastRow) {
      this.setIsFetching(true);

      const lastRow = Math.min(qxLastRow, this._rowCount - 1);
      // Returns a request promise with given offset and limit
      const getFetchPromise = (offset, limit=this.self().SERVER_MAX_LIMIT) => {
        const urlParams = {
          limit,
          offset,
          filters: this.getFilters() ?
            JSON.stringify({
              "started_at": this.getFilters()
            }) :
            null,
          orderBy: JSON.stringify(this.getOrderBy())
        };
        return osparc.store.Jobs.getInstance().fetchJobs(urlParams)
          .then(jobs => {
            const filteredJobs = this.__filterJobs(jobs);
            const data = [];
            const jobsCols = osparc.jobs.JobsTable.COLS;
            filteredJobs.forEach(job => {
              data.push({
                [jobsCols.JOB_ID.id]: job.getJobId(),
                [jobsCols.SOLVER.id]: job.getSolver(),
                [jobsCols.STATUS.id]: job.getStatus(),
                [jobsCols.PROGRESS.id]: job.getProgress() ? (job.getProgress() + "%") : "-",
                [jobsCols.SUBMIT.id]: job.getSubmittedAt() ? osparc.utils.Utils.formatDateAndTime(job.getSubmittedAt()) : "-",
                [jobsCols.START.id]: job.getStartedAt() ? osparc.utils.Utils.formatDateAndTime(job.getStartedAt()) : "-",
                [jobsCols.INSTANCE.id]: job.getInstance(),
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
