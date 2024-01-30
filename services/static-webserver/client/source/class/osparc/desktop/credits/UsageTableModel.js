/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2024 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

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
  },

  properties: {
    walletId: {
      check: "Number",
      nullable: false
    },
    filters: {
      check: "Object",
      init: null
    }
  },

  members: {
    // overridden
    _loadRowCount() {
      osparc.data.Resources.fetch("resourceUsagePerWallet", "getPage", {
        url: {
          walletId: this.getWalletId(),
          limit: 1,
          offset: 0,
          filters: this.getFilters() ?
          JSON.stringify({
            "started_at": this.getFilters()
          }) :
          null
        }
      }, undefined, {
        resolveWResponse: true
      })
        .then(resp => {
          this._onRowCountLoaded(resp._meta.total)
        })
        .catch(() => {
          this._onRowCountLoaded(null)
        })
    },
    // overridden
    _loadRowData(firstRow, lastRow) {
      osparc.data.Resources.fetch("resourceUsagePerWallet", "getPage", {
        url: {
          walletId: this.getWalletId(),
          limit: lastRow - firstRow,
          offset: firstRow,
          filters: this.getFilters() ?
            JSON.stringify({
              "started_at": this.getFilters()
            }) :
            null
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
                duration = osparc.utils.Utils.formatMilliSeconds(new Date(rawRow["stopped_at"]) - new Date(rawRow["started_at"]))
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
              user: rawRow["user_id"]
            })
          })
          this._onRowDataLoaded(data)
        })
        .catch(() => {
          this._onRowDataLoaded(null)
        })
    }
  }
})
