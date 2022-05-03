/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Big button representing a service. It shows its name and icon and description as tooltip.
 * It also adds filtering capabilities.
 */
qx.Class.define("osparc.component.service.ServiceButtonList", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function(serviceModel) {
    this.base(arguments);

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      allowGrowX: true
    });

    if (serviceModel) {
      this.setServiceModel(serviceModel);
    }

    this.subscribeToFilterGroup("serviceCatalog");
  },

  properties: {
    serviceModel: {
      check: "qx.core.Object",
      nullable: false,
      apply: "__applyServiceModel"
    }
  },

  statics: {
    ITEM_WIDTH: 550,
    ITEM_HEIGHT: 40,
    SERVICE_ICON: "@FontAwesome5Solid/paw/24"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "shared-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50,
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.SHARED);
          break;
        }
        case "hits": {
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-13",
            allowGrowY: false,
            minWidth: 120,
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.LAST_CHANGE);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyServiceModel: function(serviceModel) {
      // BASE
      if (serviceModel.getThumbnail()) {
        this.getChildControl("icon").setSource(serviceModel.getThumbnail());
      } else {
        this.getChildControl("icon").setSource(this.self().SERVICE_ICON);
      }
      serviceModel.bind("name", this.getChildControl("title"), "value");
      serviceModel.bind("description", this.getChildControl("description"), "value");

      // ITEM
      this.__applyHits(JSON.parse(qx.util.Serializer.toJson(serviceModel.get("access_rights"))));
    },

    __applyHits: function() {
      console.log("Apply hits");
    }
  }
});
