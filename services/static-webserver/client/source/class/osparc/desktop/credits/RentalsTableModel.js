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


qx.Class.define("osparc.desktop.credits.RentalsTableModel", {
  extend: qx.ui.table.model.Remote,

  construct(walletId, filters) {
    this.base(arguments);

    const rentalsCols = osparc.desktop.credits.RentalsTable.COLS;
    const colLabels = Object.values(rentalsCols).map(col => col.label);
    const colIDs = Object.values(rentalsCols).map(col => col.id);

    this.setColumns(colLabels, colIDs);
    this.setWalletId(walletId)
    if (filters) {
      this.setFilters(filters)
    }
    this.setSortColumnIndexWithoutSortingData(rentalsCols.START.column);
    this.setSortAscendingWithoutSortingData(false);
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
    COLUMN_ID_TO_DB_COLUMN_MAP: Object.values(osparc.desktop.credits.RentalsTable.COLS).reduce((acc, { id, column }) => {
      acc[column] = id;
      return acc;
    }, {}),
    /*
    COLUMN_ID_TO_DB_COLUMN_MAP: {
      0: "purchaseId",
      1: "itemId",
      2: "itemLabel",
      3: "start",
      4: "duration",
      5: "seats",
      6: "cost",
      7: "user",
    },
    */
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
      osparc.data.Resources.fetch("wallets", "purchases", params, options)
        .then(resp => {
          this._onRowCountLoaded(resp["_meta"].total)
        })
        .catch(() => {
          this._onRowCountLoaded(null)
        });
    },

    // overridden
    _loadRowData(firstRow, qxLastRow) {
      this.setIsFetching(true);

      const lastRow = Math.min(qxLastRow, this._rowCount - 1)
      // Returns a request promise with given offset and limit
      const getFetchPromise = (offset, limit=this.self().SERVER_MAX_LIMIT) => {
        return osparc.data.Resources.fetch("wallets", "purchases", {
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
            const rentalsCols = osparc.desktop.credits.RentalsTable.COLS;
            rawData.forEach(rawRow => {
              data.push({
                [rentalsCols.PURCHASE_ID.id]: rawRow["licensedItemPurchaseId"],
                [rentalsCols.ITEM_ID.id]: rawRow["licensedItemId"],
                [rentalsCols.ITEM_LABEL.id]: "Hello",
                [rentalsCols.START.id]: osparc.utils.Utils.formatDateAndTime(new Date(rawRow["startAt"])),
                [rentalsCols.END.id]: osparc.utils.Utils.formatDateAndTime(new Date(rawRow["expireAt"])),
                [rentalsCols.SEATS.id]: rawRow["numOfSeats"],
                [rentalsCols.COST.id]: rawRow["pricingUnitCost"] ? parseFloat(rawRow["pricingUnitCost"]).toFixed(2) : "",
                [rentalsCols.USER.id]: rawRow["purchasedByUser"],
              })
            })
            return data;
          });
      };

      // Divides the model row request into several server requests to comply with the number of rows server limit
      const reqLimit = lastRow - firstRow + 1; // Number of requested rows
      const nRequests = Math.ceil(reqLimit / this.self().SERVER_MAX_LIMIT);
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
