/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.data.model.Wallet", {
  extend: qx.core.Object,

  construct: function(walletData) {
    this.base(arguments);

    this.set({
      walletId: walletData["wallet_id"],
      name: walletData["name"],
      description: walletData["description"] ? walletData["description"] : null,
      thumbnail: walletData["thumbnail"] ? walletData["thumbnail"] : null,
      status: walletData["status"] ? walletData["status"] : false,
      creditsAvailable: walletData["available_credits"] ? walletData["available_credits"] : 0,
      // walletType: walletData["type"] ? walletData["type"] : "personal",
      accessRights: walletData["accessRights"]
    });
  },

  properties: {
    walletId: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeWalletId"
    },

    name: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeName"
    },

    description: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeDescription"
    },

    thumbnail: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeThumbnail"
    },

    creditsAvailable: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCreditsAvailable"
    },

    status: {
      check: ["ACTIVE", "INACTIVE"],
      init: false,
      nullable: false,
      event: "changeStatus"
    },

    accessRights: {
      check: "Object",
      init: null,
      nullable: false,
      event: "changeAccessRights"
    },

    walletType: {
      check: ["personal", "shared"],
      init: null,
      nullable: false,
      event: "changeWalletType"
    }
  }
});
