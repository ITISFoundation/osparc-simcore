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


qx.Class.define("osparc.desktop.credits.PurchasesTableModel", {
  extend: qx.ui.table.model.Remote,

  construct(walletId, filters) {
    this.base(arguments);

    const purchasesCols = osparc.desktop.credits.PurchasesTable.COLS;
    const colLabels = Object.values(purchasesCols).map(col => col.label);
    const colIDs = Object.values(purchasesCols).map(col => col.id);

    this.setColumns(colLabels, colIDs);
    this.setWalletId(walletId);
    if (filters) {
      this.setFilters(filters);
    }
    this.setSortColumnIndexWithoutSortingData(purchasesCols.START.column);
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
        field: "startAt",
        direction: "desc"
      }
    },
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
    COLUMN_ID_TO_DB_COLUMN_MAP: {
      0: "startAt",
    },
  },

  members: {
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
      const walletId = this.getWalletId();
      const urlParams = {
        offset: 0,
        limit: 1,
        filters: this.getFilters() ?
          JSON.stringify({
            "startAt": this.getFilters()
          }) :
          null,
        orderBy: JSON.stringify(this.getOrderBy()),
      };
      const options = {
        resolveWResponse: true
      };
      osparc.store.LicensedItems.getInstance().getPurchasedLicensedItems(walletId, urlParams, options)
        .then(resp => this._onRowCountLoaded(resp["_meta"].total))
        .catch(() => this._onRowCountLoaded(null));
    },

    // overridden
    _loadRowData(firstRow, qxLastRow) {
      this.setIsFetching(true);

      const lastRow = Math.min(qxLastRow, this._rowCount - 1);
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
        };
        const licensedItemsStore = osparc.store.LicensedItems.getInstance();
        return Promise.all([
          licensedItemsStore.getLicensedItems(),
          licensedItemsStore.getPurchasedLicensedItems(walletId, urlParams),
        ])
          .then(values => {
            const licensedItems = values[0];
            const purchasesItems = values[1];

            const data = [];
            const purchasesCols = osparc.desktop.credits.PurchasesTable.COLS;
            purchasesItems.forEach(purchasesItem => {
              const licensedItemId = purchasesItem["licensedItemId"];
              const licensedItem = licensedItems[licensedItemId];
              data.push({
                [purchasesCols.PURCHASE_ID.id]: purchasesItem["licensedItemPurchaseId"],
                [purchasesCols.ITEM_ID.id]: licensedItemId,
                [purchasesCols.ITEM_LABEL.id]: licensedItem ? licensedItem.getDisplayName() : "unknown model",
                [purchasesCols.START.id]: osparc.utils.Utils.formatDateAndTime(new Date(purchasesItem["startAt"])),
                [purchasesCols.END.id]: osparc.utils.Utils.formatDateAndTime(new Date(purchasesItem["expireAt"])),
                [purchasesCols.SEATS.id]: purchasesItem["numOfSeats"],
                [purchasesCols.COST.id]: purchasesItem["pricingUnitCost"] ? ("-" + parseFloat(purchasesItem["pricingUnitCost"]).toFixed(2)) : "", // show it negative
                [purchasesCols.USER.id]: purchasesItem["userEmail"],
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
          .then(data => this._onRowDataLoaded(data))
          .catch(err => {
            console.error(err)
            this._onRowDataLoaded(null);
          })
          .finally(() => this.setIsFetching(false));
      }
    }
  }
})
