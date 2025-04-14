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


qx.Class.define("osparc.jobs.ClustersTableModel", {
  extend: qx.ui.table.model.Remote,

  construct(filters) {
    this.base(arguments);

    const clustersCols = osparc.jobs.ClustersTable.COLS;
    const colLabels = Object.values(clustersCols).map(col => col.label);
    const colIDs = Object.values(clustersCols).map(col => col.id);
    this.setColumns(colLabels, colIDs);

    if (filters) {
      this.setFilters(filters);
    }

    this.setSortAscendingWithoutSortingData(false);
    this.setColumnSortable(clustersCols.CLUSTER_ID.column, false);
    this.setColumnSortable(clustersCols.N_WORKERS.column, false);
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
        field: "name",
        direction: "asc"
      }
    },
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
  },

  members: {
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
      osparc.store.Clusters.getInstance().fetchClusters(urlParams, options)
        .then(clusters => {
          this._onRowCountLoaded(clusters.length);
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
        return osparc.store.Clusters.getInstance().fetchClusters(urlParams)
          .then(clusters => {
            const data = [];
            const jobsCols = osparc.jobs.JobsTable.COLS;
            clusters.forEach(cluster => {
              data.push({
                [jobsCols.CLUSTER_ID.id]: cluster.getClusterId(),
                [jobsCols.NAME.id]: cluster.getName(),
                [jobsCols.STATUS.id]: cluster.getStatus(),
                [jobsCols.N_WORKERS.id]: cluster.getNWorkers() ? cluster.getNWorkers() : 0,
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
