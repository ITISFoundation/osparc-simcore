/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2024 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */
const SERVER_MAX_LIMIT = 49
const COLUMN_ID_TO_DB_COLUMN_MAP = {
  0: "project_name",
  1: "node_name",
  2: "service_key",
  3: "started_at",
  5: "service_run_status",
  6: "credit_cost",
  7: "user_email"
}

qx.Class.define("osparc.desktop.credits.UsageTableModel", {
  extend: qx.ui.table.model.Remote,

  construct(walletId, filters) {
    this.base(arguments)
    this.setColumns([
      osparc.product.Utils.getStudyAlias({firstUpperCase: true}),
      qx.locale.Manager.tr("Node"),
      qx.locale.Manager.tr("Service"),
      qx.locale.Manager.tr("Start"),
      qx.locale.Manager.tr("Duration"),
      qx.locale.Manager.tr("Status"),
      qx.locale.Manager.tr("Credits"),
      qx.locale.Manager.tr("User")
    ], [
      "project",
      "node",
      "service",
      "start",
      "duration",
      "status",
      "cost",
      "user"
    ])
    this.setWalletId(walletId)
    if (filters) {
      this.setFilters(filters)
    }
    this.setSortColumnIndexWithoutSortingData(3)
    this.setSortAscendingWithoutSortingData(false)
    this.setColumnSortable(4, false)
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

  members: {
    // overrriden
    sortByColumn(columnIndex, ascending) {
      this.setOrderBy({
        field: COLUMN_ID_TO_DB_COLUMN_MAP[columnIndex],
        direction: ascending ? "asc" : "desc"
      })
      this.base(arguments, columnIndex, ascending)
    },
    // overridden
    _loadRowCount() {
      const endpoint = this.getWalletId() == null ? "get" : "getWithWallet"
      osparc.data.Resources.fetch("resourceUsage", endpoint, {
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
      }, undefined, {
        resolveWResponse: true
      })
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
      const getFetchPromise = (offset, limit=SERVER_MAX_LIMIT) => {
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
                project: rawRow["project_name"] || rawRow["project_id"],
                node: rawRow["node_name"] || rawRow["node_id"],
                service,
                start,
                duration,
                status: qx.lang.String.firstUp(rawRow["service_run_status"].toLowerCase()),
                cost: rawRow["credit_cost"] ? rawRow["credit_cost"].toFixed(2) : "",
                user: rawRow["user_email"]
              })
            })
            return data
          })
      }
      // Divides the model row request into several server requests to comply with the number of rows server limit
      const reqLimit = lastRow - firstRow + 1 // Number of requested rows
      const nRequests = Math.ceil(reqLimit / SERVER_MAX_LIMIT)
      if (nRequests > 1) {
        let requests = []
        for (let i=firstRow; i <= lastRow; i += SERVER_MAX_LIMIT) {
          requests.push(getFetchPromise(i, i > lastRow - SERVER_MAX_LIMIT + 1 ? reqLimit % SERVER_MAX_LIMIT : SERVER_MAX_LIMIT))
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
