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

qx.Class.define("osparc.data.model.LicensedItem", {
  extend: qx.core.Object,

  /**
   * @param licensedItemData {Object} Object containing the serialized LicensedItem Data
   */
  construct: function(licensedItemData) {
    this.base(arguments);

    console.log("licensedItemData", licensedItemData);

    let thumbnail = "";
    let date = null;
    let licensedResources = [];
    if (licensedItemData["licensedResources"]) {
      if (licensedItemData["licensedResources"].length) {
        const firstItem = licensedItemData["licensedResources"][0]["source"];
        if (firstItem["thumbnail"]) {
          thumbnail = firstItem["thumbnail"];
        }
        if (firstItem["features"] && firstItem["features"]["date"]) {
          date = firstItem["features"]["date"];
        }
      }
      licensedItemData["licensedResources"].forEach(licensedRsrc => licensedResources.push(licensedRsrc["source"]));
    }

    this.set({
      licensedItemId: licensedItemData.licensedItemId,
      categoryId: licensedItemData.categoryId,
      categoryDisplay: licensedItemData.categoryDisplay,
      categoryIcon: licensedItemData.categoryIcon || `osparc/market/${licensedItemData.categoryId}.svg`,
      pricingPlanId: licensedItemData.pricingPlanId,
      key: licensedItemData.key,
      version: licensedItemData.version,
      thumbnail: thumbnail,
      displayName: licensedItemData.displayName,
      date: new Date(date),
      licensedResources: licensedResources,
      seats: licensedItemData.seats || null,
    });
  },

  properties: {
    licensedItemId: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeLicensedItemId",
    },

    categoryId: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeCategoryId",
    },

    categoryDisplay: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeCategoryDisplay",
    },

    categoryIcon: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeCategoryIcon",
    },

    pricingPlanId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changePricingPlanId",
    },

    key: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeKey",
    },

    version: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeVersion",
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeThumbnail",
    },

    displayName: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeDisplayName",
    },

    date: {
      check: "Date",
      nullable: false,
      init: null,
      event: "changeDate",
    },

    licensedResources: {
      check: "Array",
      nullable: false,
      init: [],
      event: "changeLicensedResources",
    },

    seats: {
      check: "Array",
      nullable: true,
      init: null,
      event: "changeSeats",
    },
  },

  statics: {
    addSeatsFromPurchases: function(licensedItems, purchases) {
      // reset seats
      Object.values(licensedItems).forEach(licensedItem => licensedItem.setSeats([]));
      // populate seats
      purchases.forEach(purchase => {
        const {
          key,
          version,
        } = purchase;
        Object.values(licensedItems).forEach(licensedItem => {
          if (licensedItem.getKey() === key && licensedItem.getVersion() <= version) {
            licensedItem.getSeats().push({
              licensedItemId: purchase["licensedItemId"],
              licensedItemPurchaseId: purchase["licensedItemPurchaseId"],
              numOfSeats: purchase["numOfSeats"],
              expireAt: new Date(purchase["expireAt"]),
            });
          }
        });
      })
    },
  },

  members: {
  }
});
