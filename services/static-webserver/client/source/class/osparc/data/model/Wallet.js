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
      label: walletData["label"],
      description: walletData["description"] ? walletData["description"] : null,
      thumbnail: walletData["thumbnail"] ? walletData["thumbnail"] : null,
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

    label: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeLabel"
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
