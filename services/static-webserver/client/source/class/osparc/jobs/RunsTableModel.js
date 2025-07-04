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
    this.__cachedData = new Map();
    this.__loadedRanges = [];

    this.set({
      projectUuid,
    });

    this.setBlockSize(osparc.store.Jobs.SERVER_MAX_LIMIT);

    const jobsCols = osparc.jobs.RunsTable.COLS;
    const colLabels = Object.values(jobsCols).map(col => col.label);
    const colIDs = Object.values(jobsCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    this.setSortColumnIndexWithoutSortingData(jobsCols.SUBMIT.column);
    this.setSortAscendingWithoutSortingData(false);
    Object.values(jobsCols).forEach(col => {
      this.setColumnSortable(col.column, Boolean(col.sortableMap));
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
        field: "submitted_at", // submitted_at|started_at|ended_at
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

  members: {
    __includeChildren: null,
    __cachedData: null,
    __loadedRanges: null,

    // overridden
    sortByColumn(columnIndex, ascending) {
      const jobsCols = osparc.jobs.RunsTable.COLS;
      const colInfo = Object.values(jobsCols).find(col => col.column === columnIndex);
      this.setOrderBy({
        field: colInfo.sortableMap,
        direction: ascending ? "asc" : "desc"
      })
      this.base(arguments, columnIndex, ascending)
    },

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
      console.info(`🔄 _loadRowData requested: firstRow=${firstRow}, qxLastRow=${qxLastRow}`);

      // Prevent multiple simultaneous requests
      if (this.getIsFetching()) {
        console.info(`⏳ Already fetching data, queuing request for ${firstRow}-${qxLastRow}`);
        setTimeout(() => this._loadRowData(firstRow, qxLastRow), 100);
        return;
      }

      // Limit the request to smaller chunks for better pagination
      const serverMaxLimit = osparc.store.Jobs.SERVER_MAX_LIMIT;
      const PAGE_SIZE = serverMaxLimit;
      const nextChunkStart = this.__findNextChunkStart(firstRow);
      const lastRow = Math.min(nextChunkStart + PAGE_SIZE - 1, this._rowCount - 1);

      console.info(`📏 Loading sequential chunk: ${nextChunkStart}-${lastRow} (requested: ${firstRow}-${qxLastRow})`);

      const rangesToFetch = [{start: nextChunkStart, end: lastRow}];
      console.info(`📡 Loading next sequential chunk:`, rangesToFetch);

      this.setIsFetching(true);

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

      const fetchPromises = rangesToFetch.map(range => {
        const rangeSize = range.end - range.start + 1;

        if (rangeSize <= serverMaxLimit) {
          return getFetchPromise(range.start, rangeSize).then(data => ({
            start: range.start,
            data: data
          }));
        } else {
          const requests = [];
          for (let i = range.start; i <= range.end; i += serverMaxLimit) {
            const chunkSize = Math.min(serverMaxLimit, range.end - i + 1);
            requests.push(getFetchPromise(i, chunkSize).then(data => ({
              start: i,
              data: data
            })));
          }
          return Promise.all(requests).then(chunks => ({
            start: range.start,
            data: chunks.flatMap(chunk => chunk.data)
          }));
        }
      });

      Promise.all(fetchPromises)
        .then(loadedRanges => {
          loadedRanges.forEach(loadedRange => {
            loadedRange.data.forEach((rowData, index) => {
              this.__cachedData.set(loadedRange.start + index, rowData);
            });
            this.__loadedRanges.push({start: loadedRange.start, end: loadedRange.start + loadedRange.data.length - 1});
          });

          const requestedData = this.__getCachedData(firstRow, lastRow);
          this._onRowDataLoaded(requestedData);
        })
        .catch(err => {
          console.error(err);
          this._onRowDataLoaded(null);
        })
        .finally(() => this.setIsFetching(false));
    },

    __findNextChunkStart: function() {
      let consecutiveEnd = -1;
      for (let i = 0; i < this._rowCount; i++) {
        if (this.__cachedData.has(i)) {
          consecutiveEnd = i;
        } else {
          break;
        }
      }

      const nextStart = consecutiveEnd + 1;
      console.info(`📍 Consecutive data ends at row ${consecutiveEnd}, next chunk starts at ${nextStart}`);
      return Math.max(nextStart, 0);
    },

    __getCachedData: function(firstRow, lastRow) {
      const data = [];
      for (let i = firstRow; i <= lastRow; i++) {
        if (this.__cachedData.has(i)) {
          data.push(this.__cachedData.get(i));
        }
      }
      return data;
    },
  }
})
