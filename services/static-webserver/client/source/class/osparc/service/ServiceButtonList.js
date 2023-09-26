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
qx.Class.define("osparc.service.ServiceButtonList", {
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
    ITEM_HEIGHT: 35,
    SERVICE_ICON: "@FontAwesome5Solid/paw/24"
  },

  members: {
    __applyServiceModel: function(serviceModel) {
      // BASE
      if (serviceModel.getThumbnail()) {
        this.getChildControl("icon").setSource(serviceModel.getThumbnail());
      } else {
        this.getChildControl("icon").setSource(this.self().SERVICE_ICON);
      }
      serviceModel.bind("name", this.getChildControl("title"), "value");
      serviceModel.bind("description", this.getChildControl("description-md"), "value");

      // ITEM
      this.__applyLatestVersion(serviceModel);
      this.__applyHitsOnItem(serviceModel);
    },

    __applyLatestVersion: function(serviceModel) {
      const latestVLabel = new qx.ui.basic.Label("v" + serviceModel.getVersion()).set({
        alignY: "middle"
      });
      this._add(latestVLabel, {
        row: 0,
        column: osparc.dashboard.ListButtonBase.POS.LAST_CHANGE
      });
    },

    __applyHitsOnItem: function(serviceModel) {
      const hitsLabel = new qx.ui.basic.Label(this.tr("Hits: ") + String(serviceModel.getHits())).set({
        alignY: "middle",
        toolTipText: this.tr("Number of times you instantiated it")
      });
      this._add(hitsLabel, {
        row: 0,
        column: osparc.dashboard.ListButtonBase.POS.HITS
      });
    },

    _filterText: function(text) {
      const checks = [
        this.getServiceModel().getName(),
        this.getServiceModel().getDescription(),
        this.getServiceModel().getContact()
      ];
      return osparc.dashboard.CardBase.filterText(checks, text);
    },

    _filterTags: function(tags) {
      if (tags && tags.length) {
        // xtype is a tuned type by the frontend
        const type = this.getServiceModel().getXType() || "";
        if (!tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    _filterClassifiers: function(classifiers) {
      const checks = this.getServiceModel().getClassifiers();
      return osparc.dashboard.CardBase.filterText(checks, classifiers);
    }
  }
});
