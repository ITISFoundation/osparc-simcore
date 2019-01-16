/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let prjBrowserLayout = new qx.ui.layout.VBox(10);
    this._setLayout(prjBrowserLayout);

    let iframe = qxapp.utils.Utils.createLoadingIFrame(this.tr("Services"));
    this._add(iframe, {
      flex: 1
    });

    const interval = 1000;
    let userTimer = new qx.event.Timer(interval);
    userTimer.addListener("interval", () => {
      if (this.__servicesReady) {
        userTimer.stop();
        this._removeAll();
        iframe.dispose();
        this.__createServicesLayout();
      }
    }, this);
    userTimer.start();

    this.__initResources();
  },

  members: {
    __servicesReady: null,
    __allServices: null,
    __servicesList: null,
    __versionsList: null,

    __initResources: function() {
      this.__getServicesPreload();
    },

    __getServicesPreload: function() {
      let store = qxapp.data.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        // Do not validate if are not taking actions
        // this.__nodeCheck(e.getData());
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    },

    __createServicesLayout: function() {
      let servicesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      let servicesList = this.__createServicesList();
      servicesLayout.add(servicesList);

      let versionsList = this.__createVersionsList();
      servicesLayout.add(versionsList);

      let serviceDescription = this.__createServiceDescription();
      servicesLayout.add(serviceDescription, {
        flex: 1
      });

      this._add(servicesLayout);
    },

    __createServicesList: function() {
      let servicesLayout = this.__createVBoxWLabel(this.tr("Services"));

      let servicesList = this.__servicesList = new qx.ui.form.List().set({
        orientation: "vertical",
        spacing: 10,
        minWidth: 500,
        height: 400,
        appearance: "pb-list"
      });
      servicesList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedKey = e.getData()[0].getModel();
          this.__serviceSelected(selectedKey, true);
        }
      }, this);
      let store = qxapp.data.Store.getInstance();
      let latestServices = [];
      let services = this.__allServices = store.getServices();
      for (const serviceKey in services) {
        latestServices.push(qxapp.utils.Services.getLatest(services, serviceKey));
      }
      let latestServicesModel = new qx.data.Array(
        latestServices.map(s => qx.data.marshal.Json.createModel(s))
      );
      let prjCtr = new qx.data.controller.List(latestServicesModel, servicesList, "name");
      prjCtr.setDelegate({
        createItem: () => new qxapp.desktop.ServiceBrowserListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("key", "model", null, item, id);
          ctrl.bindProperty("key", "title", null, item, id);
          ctrl.bindProperty("name", "name", null, item, id);
          ctrl.bindProperty("type", "type", null, item, id);
          ctrl.bindProperty("contact", "contact", null, item, id);
        }
      });
      servicesLayout.add(servicesList);

      return servicesLayout;
    },

    __createVersionsList: function() {
      let versionsLayout = this.__createVBoxWLabel(this.tr("Versions"));

      let versionsList = this.__versionsList = new qx.ui.form.List().set({
        orientation: "vertical",
        spacing: 10,
        minWidth: 100,
        height: 400,
        appearance: "pb-list"
      });
      versionsList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedVersion = e.getData()[0].getLabel();
          this.__versionSelected(selectedVersion, true);
        }
      }, this);
      versionsLayout.add(versionsList);

      return versionsLayout;
    },

    __createServiceDescription: function() {
      let descriptionLayout = this.__createVBoxWLabel(this.tr("Description"));

      let serviceDescriptionGrid = new qx.ui.layout.Grid();
      serviceDescriptionGrid.setSpacing(5);
      serviceDescriptionGrid.setColumnFlex(0, 0);
      serviceDescriptionGrid.setColumnFlex(1, 0);
      serviceDescriptionGrid.setColumnAlign(0, "right", "top");
      serviceDescriptionGrid.setColumnAlign(1, "left", "top");
      let serviceDescription = this.__serviceDescription = new qx.ui.container.Composite(serviceDescriptionGrid);

      const tagsOrder = qxapp.utils.Services.getTagsOrder();
      for (let i=0; i<tagsOrder.length; i++) {
        let label = new qx.ui.basic.Label(tagsOrder[i] + ":").set({
          font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"])
        });
        serviceDescription.add(label, {
          row: i,
          column: 0
        });
      }
      descriptionLayout.add(serviceDescription);

      return descriptionLayout;
    },

    __createVBoxWLabel: function(text) {
      let vBoxLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      let label = new qx.ui.basic.Label(text).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]),
        minWidth: 150
      });
      vBoxLayout.add(label);

      return vBoxLayout;
    },

    __serviceSelected: function(serviceKey) {
      if (this.__versionsList) {
        let versionsList = this.__versionsList;
        versionsList.removeAll();
        if (serviceKey in this.__allServices) {
          let versions = qxapp.utils.Services.getVersions(this.__allServices, serviceKey);
          for (let i = versions.length; i--;) {
            let listItem = new qx.ui.form.ListItem(versions[i]);
            versionsList.add(listItem);
            if (i === versions.length-1) {
              versionsList.setSelection([listItem]);
            }
          }
        }
      }
    },

    __versionSelected: function(versionKey) {
      const serviceSelection = this.__servicesList.getSelection();
      if (serviceSelection.length > 0) {
        const serviceKey = serviceSelection[0].getModel();
        const selectedService = qxapp.utils.Services.getFromObject(this.__allServices, serviceKey, versionKey);
        console.log(selectedService);
      }
    },

    __nodeCheck: function(services) {
      /** a little ajv test */
      let nodeCheck = new qx.io.request.Xhr("/resource/qxapp/node-meta-v0.0.1.json");
      nodeCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new qxapp.wrappers.Ajv(data);
          for (const srvId in services) {
            const service = services[srvId];
            let check = ajv.validate(service);
            console.log("services validation result " + service.key + ":", check);
          }
        } catch (err) {
          console.error(err);
        }
      }, this);
      nodeCheck.send();
    }
  }
});
