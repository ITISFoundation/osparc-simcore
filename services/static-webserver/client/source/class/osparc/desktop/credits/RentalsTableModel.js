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
        field: "purchased_at",
        direction: "desc"
      }
    }
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
    COLUMN_ID_TO_DB_COLUMN_MAP: {
      0: "purchased_at",
    },
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
      const walletId = this.getWalletId();
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
      osparc.store.LicensedItems.getInstance().getPurchasedLicensedItems(walletId, urlParams, options)
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
        const walletId = this.getWalletId();
        const urlParams = {
          limit,
          offset,
          filters: this.getFilters() ?
            JSON.stringify({
              "started_at": this.getFilters()
            }) :
            null,
          orderBy: JSON.stringify(this.getOrderBy())
        }
        return Promise.all([
          osparc.store.LicensedItems.getInstance().getLicensedItems(),
          osparc.store.LicensedItems.getInstance().getPurchasedLicensedItems(walletId, urlParams),
        ])
          .then(values => {
            const licensedItems = values[0];
            const purchasesItems = values[1];

            const data = [];
            const rentalsCols = osparc.desktop.credits.RentalsTable.COLS;
            purchasesItems.forEach(purchasesItem => {
              const licensedItemId = purchasesItem["licensedItemId"];
              const licensedItem = licensedItems.find(licItem => licItem["licensedItemId"] === licensedItemId);
              data.push({
                [rentalsCols.PURCHASE_ID.id]: purchasesItem["licensedItemPurchaseId"],
                [rentalsCols.ITEM_ID.id]: licensedItemId,
                [rentalsCols.ITEM_LABEL.id]: licensedItem ? licensedItem["name"] : "unknown model",
                [rentalsCols.START.id]: osparc.utils.Utils.formatDateAndTime(new Date(purchasesItem["startAt"])),
                [rentalsCols.END.id]: osparc.utils.Utils.formatDateAndTime(new Date(purchasesItem["expireAt"])),
                [rentalsCols.SEATS.id]: purchasesItem["numOfSeats"],
                [rentalsCols.COST.id]: purchasesItem["pricingUnitCost"] ? parseFloat(purchasesItem["pricingUnitCost"]).toFixed(2) : "",
                [rentalsCols.USER.id]: purchasesItem["purchasedByUser"],
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
