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
      allowGrowX: true
    });

    this.setResourceType("service");
    if (service) {
      this.setService(service);
    }

    this.subscribeToFilterGroup("serviceCatalog");

    /**
     * The idea here is to show some extra options when a service is selected:
     * - Version selection
     * - Pricing unit selection if applies
     */
    // But the toggle button consumes all the events, I believe that the trick is to use the anonymous property
    // this.addListener("changeValue", e => this.__itemSelected(e.getData()));
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
    SERVICE_ICON: osparc.product.Utils.getProductThumbUrl()
  },

  members: {
    __versionsBox: null,
    __infoBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "extended-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this._add(control, {
            row: 1,
            column: 0,
            colSpan: osparc.dashboard.ListButtonBase.POS.HITS
          });
          break;
        case "version-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this.getChildControl("extended-layout").add(control);
          const versionLabel = new qx.ui.basic.Label(this.tr("Version"));
          control.add(versionLabel);
          const selectBox = this.__versionsBox = new qx.ui.form.SelectBox();
          control.add(selectBox);
          const infoBtn = this.__infoBtn = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/16");
          infoBtn.addListener("execute", () => this.__showServiceDetails(), this);
          control.add(infoBtn);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyService: function(service) {
      // BASE
      if (service.getThumbnail()) {
        this.getChildControl("icon").setSource(service.getThumbnail());
      } else {
        this.getChildControl("icon").setSource(this.self().SERVICE_ICON);
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

    __itemSelected: function(selected) {
      this.setHeight(selected ? 70 : 35);
      const extendedLayout = this.getChildControl("extended-layout");
      const versionLayout = this.getChildControl("version-layout");
      extendedLayout.setVisibility(selected ? "visible" : "excluded");
      versionLayout.setVisibility(selected ? "visible" : "excluded");
      this.__populateVersions();
    },

    __populateVersions: function() {
      const serviceKey = this.getService().getKey();
      const selectBox = this.__versionsBox;
      selectBox.removeAll();
      const versions = osparc.service.Utils.getVersions(serviceKey);
      const latest = new qx.ui.form.ListItem(this.self().LATEST);
      latest.version = this.self().LATEST;
      selectBox.add(latest);
      versions.forEach(version => {
        const listItem = osparc.service.Utils.versionToListItem(serviceKey, version);
        selectBox.add(listItem);
      });
      osparc.utils.Utils.growSelectBox(selectBox, 200);
      selectBox.setSelection([latest]);
    },

    __showServiceDetails: function() {
      const key = this.getService().getKey();
      let version = this.__versionsBox.getSelection()[0].version;
      if (version === this.self().LATEST) {
        version = this.__versionsBox.getChildrenContainer().getSelectables()[1].version;
      }
      osparc.store.Services.getService(key, version)
        .then(serviceMetadata => {
          const serviceDetails = new osparc.info.ServiceLarge(serviceMetadata);
          osparc.info.ServiceLarge.popUpInWindow(serviceDetails);
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
