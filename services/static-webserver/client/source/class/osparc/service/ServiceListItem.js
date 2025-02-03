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

qx.Class.define("osparc.service.ServiceListItem", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function(service) {
    this.base(arguments);

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      paddingTop: 0,
      paddingBottom: 0,
      allowGrowX: true,
      focusable: true,
    });

    this.setResourceType("service");
    if (service) {
      this.setService(service);
    }

    this.subscribeToFilterGroup("serviceCatalog");

    this.bind("selected", this, "backgroundColor", {
      converter: selected => selected ? "strong-main" : "info"
    });
  },

  properties: {
    service: {
      check: "qx.core.Object",
      nullable: false,
      apply: "__applyService"
    }
  },

  statics: {
    LATEST: "latest",
    ITEM_WIDTH: 550,
    ITEM_HEIGHT: 35,
    SERVICE_THUMBNAIL: osparc.product.Utils.getProductThumbUrl()
  },

  members: {
    __versionsBox: null,
    __infoBtn: null,

    __applyService: function(service) {
      // BASE
      if (service.getThumbnail()) {
        this.getChildControl("icon").setSource(service.getThumbnail());
      } else {
        this.getChildControl("icon").setSource(this.self().SERVICE_THUMBNAIL);
      }
      service.bind("name", this.getChildControl("title"), "value");

      // ITEM
      this.__applyVersion(service);
      this.__applyHitsOnItem(service);
    },

    __applyVersion: function(service) {
      const text = service.getVersionDisplay() ? service.getVersionDisplay() : "v" + service.getVersion();
      const label = new qx.ui.basic.Label(text).set({
        alignY: "middle"
      });
      this._add(label, {
        row: 0,
        column: osparc.dashboard.ListButtonBase.POS.LAST_CHANGE
      });
    },

    __applyHitsOnItem: function(service) {
      const hitsLabel = new qx.ui.basic.Label(this.tr("Hits: ") + String(service.getHits())).set({
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
        this.getService().getName(),
        this.getService().getDescription(),
        this.getService().getContact()
      ];
      return osparc.dashboard.CardBase.filterText(checks, text);
    },

    _filterTags: function(tags) {
      if (tags && tags.length) {
        // xtype is a tuned type by the frontend
        const type = this.getService().getXType() || "";
        if (!tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    _filterClassifiers: function(classifiers) {
      const checks = this.getService().getClassifiers();
      return osparc.dashboard.CardBase.filterText(checks, classifiers);
    }
  }
});
