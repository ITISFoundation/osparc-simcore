/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2024 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.TransactionsTableModel", {
  extend: qx.ui.table.model.Remote,

  construct() {
    this.base(arguments)
    this.setBlockSize(24)
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
      osparc.data.Resources.fetch("payments", "get", {
        url: {
          limit: 1,
          offset: 0
        }
      }, undefined, {
        resolveWResponse: true
      })
        .then(({ data: resp }) => {
          this._onRowCountLoaded(resp._meta.total)
        })
        .catch(() => {
          this._onRowCountLoaded(null)
        })
    },
    // overridden
    _loadRowData(firstRow, lastRow) {
      this.setIsFetching(true)
      osparc.data.Resources.fetch("payments", "get", {
        url: {
          limit: lastRow - firstRow + 1,
          offset: firstRow
        }
      })
        .then(({ data: rawData }) => {
          const data = []
          rawData.forEach(rawRow => {
            data.push({
              date: osparc.utils.Utils.formatDateAndTime(new Date(rawRow.createdAt)),
              price: rawRow.priceDollars ? rawRow.priceDollars.toFixed(2) : 0,
              credits: rawRow.osparcCredits ? rawRow.osparcCredits.toFixed(2) * 1 : 0,
              status: this.__addColorTag(rawRow.completedStatus),
              comment: rawRow.comment,
              invoice: rawRow.invoiceUrl ? this.__createPdfIconWithLink(rawRow.invoiceUrl) : ""
            })
          })
          this._onRowDataLoaded(data)
        })
        .catch(() => {
          this._onRowDataLoaded(null)
        })
        .finally(() => this.setIsFetching(false))
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
    __createPdfIconWithLink: function(link) {
      return `<a href='${link}' target='_blank'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/PDF_file_icon.svg/833px-PDF_file_icon.svg.png' alt='Invoice' width='16' height='20'></a>`;
    }
  }
})
