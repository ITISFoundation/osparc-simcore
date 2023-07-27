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
      walletId: walletData["id"],
      name: walletData["name"],
      description: walletData["description"] ? walletData["description"] : null,
      thumbnail: walletData["thumbnail"] ? walletData["thumbnail"] : null,
      walletType: walletData["type"] ? walletData["type"] : "personal",
      accessRights: walletData["accessRights"],
      credits: walletData["credits"]["left"]
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

    walletType: {
      check: ["personal", "shared"],
      init: "personal",
      nullable: false,
      event: "changeWalletType"
    },

    accessRights: {
      check: "Object",
      init: null,
      nullable: false,
      event: "changeAccessRights"
    },

    credits: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCredits"
    }
  }
});
