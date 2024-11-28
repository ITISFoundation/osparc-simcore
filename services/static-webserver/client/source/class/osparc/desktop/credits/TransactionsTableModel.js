/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2024 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */
const SERVER_MAX_LIMIT = 49

qx.Class.define("osparc.desktop.credits.TransactionsTableModel", {
  extend: qx.ui.table.model.Remote,

  construct() {
    this.base(arguments)
    this.setColumns([
      qx.locale.Manager.tr("Date"),
      qx.locale.Manager.tr("Price USD"),
      qx.locale.Manager.tr("Credits"),
      qx.locale.Manager.tr("Status"),
      qx.locale.Manager.tr("Comment"),
      qx.locale.Manager.tr("Invoice")
    ], [
      "date",
      "price",
      "credits",
      "status",
      "comment",
      "invoice"
    ])
    this.setColumnSortable(0, false)
    this.setColumnSortable(1, false)
    this.setColumnSortable(2, false)
    this.setColumnSortable(3, false)
    this.setColumnSortable(4, false)
    this.setColumnSortable(5, false)
  },

  properties: {
    walletId: {
      check: "Number",
      nullable: false
    },
    filters: {
      check: "Object",
      init: null
    },
    isFetching: {
      check: "Boolean",
      init: false,
      event: "changeFetching"
    }
  },

  members: {
    // overridden
    _loadRowCount() {
      const params = {
        url: {
          limit: 1,
          offset: 0
        }
      };
      const options = {
        resolveWResponse: true
      };
      osparc.data.Resources.fetch("payments", "get", params, options)
        .then(({ data: resp }) => {
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
      const getFetchPromise = (offset, limit=SERVER_MAX_LIMIT) => {
        return osparc.data.Resources.fetch("payments", "get", {
          url: {
            limit,
            offset
          }
        })
          .then(({ data: rawData }) => {
            const data = []
            rawData.forEach(rawRow => {
              data.push({
                date: osparc.utils.Utils.formatDateAndTime(new Date(rawRow.createdAt)),
                price: rawRow.priceDollars ? parseFloat(rawRow.priceDollars).toFixed(2) : 0,
                credits: rawRow.osparcCredits ? parseFloat(rawRow.osparcCredits).toFixed(2) * 1 : 0,
                status: this.__addColorTag(rawRow.completedStatus),
                comment: rawRow.comment,
                invoice: rawRow.invoiceUrl ? this.__createPdfIconWithLink(rawRow.walletId, rawRow.paymentId) : ""
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
    },
    __getLevelColor: function(status) {
      const colorManager = qx.theme.manager.Color.getInstance();
      let logLevel = null;
      switch (status) {
        case "SUCCESS":
          logLevel = "info";
          break;
        case "PENDING":
          logLevel = "warning";
          break;
        case "CANCELED":
        case "FAILED":
          logLevel = "error";
          break;
        default:
          console.error("completedStatus unknown");
          break;
      }
      return colorManager.resolve(`logger-${logLevel}-message`);
    },
    __addColorTag: function(status) {
      return `<font color=${this.__getLevelColor(status)}>${osparc.utils.Utils.onlyFirstsUp(status)}</font>`;
    },

    __createPdfIconWithLink: function(walletId, paymentId) {
      const urlParams = {
        walletId,
        paymentId
      };
      const req = osparc.data.Resources.getInstance().replaceUrlParams("payments", "invoiceLink", urlParams);
      return `<a href='${req.url}' target='_blank'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/PDF_file_icon.svg/833px-PDF_file_icon.svg.png' alt='Invoice' width='16' height='20'></a>`;
    }
  }
})
