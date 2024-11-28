/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2024 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */


qx.Class.define("osparc.desktop.credits.UsageTableModel", {
  extend: qx.ui.table.model.Remote,

  construct(walletId, filters) {
    this.base(arguments);

    const usageCols = osparc.desktop.credits.UsageTable.COLS;
    const colLabels = Object.values(usageCols).map(col => col.label);
    const colIDs = Object.values(usageCols).map(col => col.id);

    this.setColumns(colLabels, colIDs);
    this.setWalletId(walletId)
    if (filters) {
      this.setFilters(filters)
    }
    this.setSortColumnIndexWithoutSortingData(usageCols.START.column);
    this.setSortAscendingWithoutSortingData(false)
    this.setColumnSortable(usageCols.DURATION.column, false);
  },

  properties: {
    walletId: {
      check: "Number",
      nullable: true
    },
    filters: {
      check: "Object",
      init: null
    },
    isFetching: {
      check: "Boolean",
      init: false,
      event: "changeFetching"
    },
    orderBy: {
      check: "Object",
      init: {
        field: "started_at",
        direction: "desc"
      }
    }
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
    COLUMN_ID_TO_DB_COLUMN_MAP: {
      0: "root_parent_project_name",
      1: "node_name",
      2: "service_key",
      3: "started_at",
      // 4: (not used) SORTING BY DURATION
      5: "service_run_status",
      6: "credit_cost",
      7: "user_email"
    }
  },

  members: {
    // overridden
    sortByColumn(columnIndex, ascending) {
      this.setOrderBy({
        field: this.self().COLUMN_ID_TO_DB_COLUMN_MAP[columnIndex],
        direction: ascending ? "asc" : "desc"
      })
      this.base(arguments, columnIndex, ascending)
    },

    // overridden
    _loadRowCount() {
      const endpoint = this.getWalletId() == null ? "get" : "getWithWallet"
      const params = {
        url: {
          walletId: this.getWalletId(),
          limit: 1,
          offset: 0,
          filters: this.getFilters() ?
            JSON.stringify({
              "started_at": this.getFilters()
            }) :
            null,
          orderBy: JSON.stringify(this.getOrderBy())
        }
      };
      const options = {
        resolveWResponse: true
      };
      osparc.data.Resources.fetch("resourceUsage", endpoint, params, options)
        .then(resp => {
          this._onRowCountLoaded(resp["_meta"].total)
        })
        .catch(() => {
          this._onRowCountLoaded(null)
        })
    },

    // overridden
    _loadRowData(firstRow, qxLastRow) {
      this.setIsFetching(true)
      // Please Qloocloox don't ask for more rows than there are
      const lastRow = Math.min(qxLastRow, this._rowCount - 1)
      // Returns a request promise with given offset and limit
      const getFetchPromise = (offset, limit=this.self().SERVER_MAX_LIMIT) => {
        const endpoint = this.getWalletId() == null ? "get" : "getWithWallet"
        return osparc.data.Resources.fetch("resourceUsage", endpoint, {
          url: {
            walletId: this.getWalletId(),
            limit,
            offset,
            filters: this.getFilters() ?
              JSON.stringify({
                "started_at": this.getFilters()
              }) :
              null,
            orderBy: JSON.stringify(this.getOrderBy())
          }
        })
          .then(rawData => {
            const data = []
            const usageCols = osparc.desktop.credits.UsageTable.COLS;
            rawData.forEach(rawRow => {
              let service = ""
              if (rawRow["service_key"]) {
                const serviceName = rawRow["service_key"].split("/").pop()
                service = `${serviceName}:${rawRow["service_version"]}`
              }
              let start = ""
              let duration = ""
              if (rawRow["started_at"]) {
                start = osparc.utils.Utils.formatDateAndTime(new Date(rawRow["started_at"]))
                if (rawRow["stopped_at"]) {
                  duration = osparc.utils.Utils.formatMsToHHMMSS(new Date(rawRow["stopped_at"]) - new Date(rawRow["started_at"]))
                }
              }
              data.push({
                // root_parent_project is the same as project if it has no parent
                [usageCols.PROJECT.id]: rawRow["root_parent_project_name"] || rawRow["root_parent_project_id"] || rawRow["project_name"] || rawRow["project_id"],
                [usageCols.NODE.id]: rawRow["node_name"] || rawRow["node_id"],
                [usageCols.SERVICE.id]: service,
                [usageCols.START.id]: start,
                [usageCols.DURATION.id]: duration,
                [usageCols.STATUS.id]: qx.lang.String.firstUp(rawRow["service_run_status"].toLowerCase()),
                [usageCols.COST.id]: rawRow["credit_cost"] ? parseFloat(rawRow["credit_cost"]).toFixed(2) : "",
                [usageCols.USER.id]: rawRow["user_email"]
              })
            })
            return data
          })
      }
      // Divides the model row request into several server requests to comply with the number of rows server limit
      const reqLimit = lastRow - firstRow + 1 // Number of requested rows
      const nRequests = Math.ceil(reqLimit / this.self().SERVER_MAX_LIMIT)
      if (nRequests > 1) {
        let requests = []
        for (let i=firstRow; i <= lastRow; i += this.self().SERVER_MAX_LIMIT) {
          requests.push(getFetchPromise(i, i > lastRow - this.self().SERVER_MAX_LIMIT + 1 ? reqLimit % this.self().SERVER_MAX_LIMIT : this.self().SERVER_MAX_LIMIT))
        }
        Promise.all(requests)
          .then(responses => {
            this._onRowDataLoaded(responses.flat())
          })
          .catch(err => {
            console.error(err)
            this._onRowDataLoaded(null)
          })
          .finally(() => this.setIsFetching(false))
      } else {
        getFetchPromise(firstRow, reqLimit)
          .then(data => {
            this._onRowDataLoaded(data)
          })
          .catch(err => {
            console.error(err)
            this._onRowDataLoaded(null)
          })
          .finally(() => this.setIsFetching(false))
      }
    }
  }
})
