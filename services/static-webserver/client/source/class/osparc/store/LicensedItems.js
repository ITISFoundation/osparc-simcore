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

qx.Class.define("osparc.store.LicensedItems", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__licensedItems = null;
    this.__purchasedLicensedItems = {};
  },

  members: {
    __licensedItems: null,
    __purchasedLicensedItems: null,

    getLicensedItems: function() {
      if (this.__licensedItems) {
        return new Promise(resolve => resolve(this.__licensedItems));
      }

      return osparc.data.Resources.getInstance().getAllPages("licensedItems")
        .then(licensedItems => {
          this.__licensedItems = licensedItems;
          return this.__licensedItems;
        });
    },

    getPurchasedLicensedItems: function(walletId, urlParams, options = {}) {
      if (walletId in this.__purchasedLicensedItems) {
        return new Promise(resolve => resolve(this.__purchasedLicensedItems[walletId]));
      }
      let purchasesParams = {
        url: {
          walletId,
          offset: 0,
          limit: 49,
        }
      };
      if (urlParams) {
        purchasesParams.url = Object.assign(purchasesParams.url, urlParams);
      }
      return osparc.data.Resources.fetch("licensedItems", "purchases", purchasesParams, options)
        .then(purchases => {
          this.__purchasedLicensedItems[walletId] = purchases;
          return purchases;
        });
    },

    purchaseLicensedItem: function(licensedItemId, walletId, pricingPlanId, pricingUnitId, numberOfSeats) {
      const params = {
        url: {
          licensedItemId
        },
        data: {
          "wallet_id": walletId,
          "pricing_plan_id": pricingPlanId,
          "pricing_unit_id": pricingUnitId,
          "num_of_seats": numberOfSeats, // this should go away
        },
      }
      return osparc.data.Resources.fetch("licensedItems", "purchase", params);
      // OM add purchase to cache
    },

    getCheckedOutLicensedItems: function(walletId, urlParams, options = {}) {
      let purchasesParams = {
        url: {
          walletId,
          offset: 0,
          limit: 49,
        }
      };
      if (urlParams) {
        purchasesParams.url = Object.assign(purchasesParams.url, urlParams);
      }
      return osparc.data.Resources.fetch("licensedItems", "checkouts", purchasesParams, options);
    },
  }
});
