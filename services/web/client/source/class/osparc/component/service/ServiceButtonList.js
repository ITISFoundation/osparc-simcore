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
        case "hits":
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
      serviceModel.bind("description", this.getChildControl("description-md"), "value");

      // ITEM
      this.__applyHits(serviceModel);
    },

    __applyHits: function(serviceModel) {
      const hitsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2).set({
        alignY: "middle"
      })).set({
        toolTipText: this.tr("Number of times it was instantiated")
      });
      const hitsLabel = new qx.ui.basic.Label(this.tr("Recents: "));
      hitsLayout.add(hitsLabel);
      const hitsValue = new qx.ui.basic.Label(String(serviceModel.hits));
      hitsLayout.add(hitsValue);
      this._addAt(hitsLayout, osparc.dashboard.ListButtonBase.POS.TSR);
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
        const type = this.getServiceModel().getType() || "";
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
