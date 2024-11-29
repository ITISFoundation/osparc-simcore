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

    const walletId = walletData["walletId"];
    this.set({
      walletId,
      name: walletData["name"],
      description: walletData["description"] ? walletData["description"] : null,
      thumbnail: walletData["thumbnail"] ? walletData["thumbnail"] : null,
      owner: walletData["owner"] ? walletData["owner"] : null,
      status: walletData["status"] ? walletData["status"] : "INACTIVE",
      creditsAvailable: walletData["availableCredits"] ? parseFloat(walletData["availableCredits"]) : 0,
      accessRights: walletData["accessRights"] ? walletData["accessRights"] : [],
      autoRecharge: walletData["autoRecharge"] ? walletData["autoRecharge"] : null,
      preferredWallet: osparc.Preferences.getInstance().getPreferredWalletId() === walletData["walletId"]
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
      nullable: true,
      event: "changeDescription"
    },

    thumbnail: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeThumbnail"
    },

    owner: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeOwner"
    },

    status: {
      check: ["ACTIVE", "INACTIVE"],
      init: false,
      nullable: false,
      event: "changeStatus"
    },

    creditsAvailable: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCreditsAvailable"
    },

    accessRights: {
      check: "Array",
      init: null,
      nullable: false,
      event: "changeAccessRights"
    },

    autoRecharge: {
      check: "Object",
      init: null,
      nullable: true,
      event: "changeAutoRecharge"
    },

    preferredWallet: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changePreferredWallet"
    }
  },

  statics: {
    getMyAccessRights: function(accessRights) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid && accessRights) {
        return accessRights.find(aR => aR["gid"] === myGid);
      }
      return null;
    }
  },

  members: {
    getMyAccessRights: function() {
      return this.self().getMyAccessRights(this.getAccessRights());
    },

    serialize: function() {
      return JSON.parse(qx.util.Serializer.toJson(this));
    }
  }
});
