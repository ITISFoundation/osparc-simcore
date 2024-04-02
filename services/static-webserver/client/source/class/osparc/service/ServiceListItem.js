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

  construct: function(serviceModel) {
    this.base(arguments);

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      paddingTop: 0,
      paddingBottom: 0,
      allowGrowX: true
    });

    if (serviceModel) {
      this.setServiceModel(serviceModel);
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
    serviceModel: {
      check: "qx.core.Object",
      nullable: false,
      apply: "__applyServiceModel"
    }
  },

  statics: {
    LATEST: "latest",
    ITEM_WIDTH: 550,
    ITEM_HEIGHT: 35,
    SERVICE_ICON: "@FontAwesome5Solid/paw/24"
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

    __applyServiceModel: function(serviceModel) {
      // BASE
      if (serviceModel.getThumbnail()) {
        this.getChildControl("icon").setSource(serviceModel.getThumbnail());
      } else {
        this.getChildControl("icon").setSource(this.self().SERVICE_ICON);
      }
      serviceModel.bind("name", this.getChildControl("title"), "value");

      // ITEM
      this.__applyVersion(serviceModel);
      this.__applyHitsOnItem(serviceModel);
    },

    __applyVersion: function(serviceModel) {
      const latestVLabel = new qx.ui.basic.Label("v" + serviceModel.getVersion()).set({
        alignY: "middle"
      });
      this._add(latestVLabel, {
        row: 0,
        column: osparc.dashboard.ListButtonBase.POS.LAST_CHANGE
      });
    },

    __applyHitsOnItem: function(serviceModel) {
      if ("getHits" in serviceModel) {
        const hitsLabel = new qx.ui.basic.Label(this.tr("Hits: ") + String(serviceModel.getHits())).set({
          alignY: "middle",
          toolTipText: this.tr("Number of times you instantiated it")
        });
        this._add(hitsLabel, {
          row: 0,
          column: osparc.dashboard.ListButtonBase.POS.HITS
        });
      }
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
      const serviceKey = this.getServiceModel().getKey();
      const selectBox = this.__versionsBox;
      selectBox.removeAll();
      const versions = osparc.service.Utils.getVersions(null, serviceKey);
      const latest = new qx.ui.form.ListItem(this.self().LATEST);
      selectBox.add(latest);
      for (let i = versions.length; i--;) {
        selectBox.add(new qx.ui.form.ListItem(versions[i]));
      }
      selectBox.setSelection([latest]);
    },

    __getSelectedServiceMetadata: function() {
      const key = this.getServiceModel().getKey();
      let version = this.__versionsBox.getSelection()[0].getLabel().toString();
      if (version === this.self().LATEST) {
        version = this.__versionsBox.getChildrenContainer().getSelectables()[1].getLabel();
      }
      return osparc.service.Utils.getFromObject(null, key, version);
    },

    __showServiceDetails: function() {
      const serviceMetadata = this.__getSelectedServiceMetadata();
      const serviceDetails = new osparc.info.ServiceLarge(serviceMetadata);
      const title = this.tr("Service information");
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
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
