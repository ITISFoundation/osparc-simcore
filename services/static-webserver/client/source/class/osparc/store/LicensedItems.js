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
  },

  statics: {
    populateSeatsFromPurchases: function(licensedItems, purchases) {
      // reset seats
      licensedItems.forEach(licensedItem => licensedItem["seats"] = []);
      // populate seats
      purchases.forEach(purchase => {
        const {
          key,
          version,
        } = purchase;
        licensedItems.forEach(licensedItem => {
          if (licensedItem["key"] === key && licensedItem["version"] <= version) {
            licensedItem["seats"].push({
              licensedItemPurchaseId: purchase["licensedItemPurchaseId"],
              numOfSeats: purchase["numOfSeats"],
              expireAt: new Date(purchase["expireAt"]),
            });
          }
        });
      })
    },

    getLowerLicensedItems: function(licensedItems, key, version) {
      const lowerLicensedItems = [];
      licensedItems.forEach(licensedItem => {
        if (licensedItem["key"] === key && licensedItem["version"] < version) {
          lowerLicensedItems.push(licensedItem);
        }
      });
      return lowerLicensedItems;
    },

    seatsToNSeats: function(seats) {
      let nSeats = 0;
      seats.forEach(seat => {
        if ("numOfSeats" in seat) {
          nSeats += seat["numOfSeats"];
        } else if ("getNumOfSeats" in seat) {
          nSeats += seat.getNumOfSeats();
        }
      });
      return nSeats;
    },
  },

  members: {
    __licensedItems: null,

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
      return osparc.data.Resources.fetch("licensedItems", "purchases", purchasesParams, options);
    },

    purchaseLicensedItem: function(licensedItemId, walletId, pricingPlanId, pricingUnitId, numOfSeats) {
      const params = {
        url: {
          licensedItemId
        },
        data: {
          "wallet_id": walletId,
          "pricing_plan_id": pricingPlanId,
          "pricing_unit_id": pricingUnitId,
          "num_of_seats": numOfSeats, // this should go away
        },
      }
      return osparc.data.Resources.fetch("licensedItems", "purchase", params);
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
