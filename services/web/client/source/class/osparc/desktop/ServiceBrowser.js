/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows all the information available regarding services.
 *
 * It has three main focuses:
 * - Services list (ServiceBrowserListItem) on the left side with some filter
 *   - Filter as you type
 *   - Filter by service type
 *   - Filter by service type
 * - List of versions of the selected service
 * - Description of the selected service using JsonTreeWidget
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let servicesView = this.__serviceBrowser = new osparc.desktop.ServiceBrowser();
 *   this.getRoot().add(servicesView);
 * </pre>
 * 
 * @asset(form/service.json)
 */

qx.Class.define("osparc.desktop.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    const iframe = osparc.utils.Utils.createLoadingIFrame(this.tr("Services"));
    this._add(iframe, {
      flex: 1
    });

    const interval = 1000;
    const userTimer = new qx.event.Timer(interval);
    userTimer.addListener("interval", () => {
      if (this.__servicesReady) {
        userTimer.stop();
        this._removeAll();
        iframe.dispose();
        this.__createServicesLayout();
        this.__attachEventHandlers();
      }
    }, this);
    userTimer.start();

    this.__initResources();
  },

  members: {
    __servicesReady: null,
    __serviceFilters: null,
    __allServices: null,
    __servicesList: null,
    __versionsList: null,
    __searchTextfield: null,

    /**
     * Function that resets the selected item by reseting the filters and the service selection
     */
    resetSelection: function() {
      if (this.__serviceFilters) {
        this.__serviceFilters.reset();
      }
      if (this.__servicesList) {
        this.__servicesList.setSelection([]);
      }
    },

    __initResources: function() {
      this.__getServicesPreload();
    },

    __getServicesPreload: function() {
      const store = osparc.store.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        // Do not validate if are not taking actions
        // this.__nodeCheck(e.getData());
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    },

    __createServicesLayout: function() {
      const servicesList = this.__createServicesListLayout();
      this._add(servicesList);

      const serviceDescription = this.__createServiceDescriptionLayout();
      this._add(serviceDescription, {
        flex: 1
      });
    },

    __createServicesListLayout: function() {
      const servicesLayout = this.__createVBoxWLabel(this.tr("Services"));

      const serviceFilters = this.__serviceFilters = new osparc.component.filter.group.ServiceFilterGroup("serviceBrowser");
      servicesLayout.add(serviceFilters);

      const servicesList = this.__servicesList = new qx.ui.form.List().set({
        orientation: "vertical",
        minWidth: 400,
        appearance: "pb-list"
      });
      servicesList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedKey = e.getData()[0].getModel();
          this.__serviceSelected(selectedKey);
        }
      }, this);
      const store = osparc.store.Store.getInstance();
      const latestServices = [];
      const services = this.__allServices = store.getServices();
      for (const serviceKey in services) {
        latestServices.push(osparc.utils.Services.getLatest(services, serviceKey));
      }
      const latestServicesModel = new qx.data.Array(
        latestServices.map(s => qx.data.marshal.Json.createModel(s))
      );
      const servCtrl = new qx.data.controller.List(latestServicesModel, servicesList, "name");
      servCtrl.setDelegate({
        createItem: () => {
          const item = new osparc.desktop.ServiceBrowserListItem();
          item.subscribeToFilterGroup("serviceBrowser");
          item.addListener("tap", e => {
            servicesList.setSelection([item]);
          });
          return item;
        },
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("key", "model", null, item, id);
          ctrl.bindProperty("key", "key", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "description", null, item, id);
          ctrl.bindProperty("type", "type", null, item, id);
          ctrl.bindProperty("category", "category", null, item, id);
          ctrl.bindProperty("contact", "contact", null, item, id);
        }
      });
      servicesLayout.add(servicesList, {
        flex: 1
      });

      // Workaround to the list.changeSelection
      servCtrl.addListener("changeValue", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedService = e.getData().toArray()[0];
          this.__serviceSelected(selectedService);
        } else {
          this.__serviceSelected(null);
        }
      }, this);

      return servicesLayout;
    },

    __createServiceDescriptionLayout: function() {
      const descriptionView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        marginTop: 20
      });

      const titleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const label = new qx.ui.basic.Label(this.tr("Description")).set({
        font: qx.bom.Font.fromConfig(osparc.theme.Font.fonts["nav-bar-label"]),
        minWidth: 150
      });
      titleContainer.add(label);

      titleContainer.add(new qx.ui.basic.Atom(this.tr("Version")));

      const versions = this.__versionsList = new qx.ui.form.SelectBox();
      osparc.utils.Utils.setIdToWidget(versions, "serviceBrowserVersionsDrpDwn");
      titleContainer.add(versions);
      versions.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length) {
          this.__versionSelected(e.getData()[0].getLabel());
        }
      }, this);
      descriptionView.add(titleContainer);

      const descriptionContainer = this.__serviceDescription = new qx.ui.container.Scroll();
      descriptionView.add(descriptionContainer, {
        flex: 1
      });
      return descriptionView;
    },

    __createVBoxWLabel: function(text) {
      const vBoxLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        marginTop: 20
      });

      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const label = new qx.ui.basic.Label(text).set({
        font: qx.bom.Font.fromConfig(osparc.theme.Font.fonts["nav-bar-label"]),
        allowStretchX: true
      });
      header.add(label, {
        flex: 1
      });
      const addServiceButton = new qx.ui.form.Button(this.tr("Add service"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.addListener("execute", () => {
        const addServiceWindow = new qx.ui.window.Window(this.tr("Create a new service")).set({
          appearance: "service-window",
          modal: true,
          autoDestroy: true,
          showMinimize: false,
          allowMinimize: false,
          centerOnAppear: true,
          layout: new qx.ui.layout.Grow()
        });
        const scroll = new qx.ui.container.Scroll();
        addServiceWindow.add(scroll);
        const form = new osparc.component.form.JsonSchemaForm("/resource/form/service.json");
        form.addListener("ready", () => {
          addServiceWindow.open();
          addServiceWindow.maximize();
        });
        scroll.add(form);
      });
      header.add(addServiceButton);
      vBoxLayout.add(header);

      return vBoxLayout;
    },

    __attachEventHandlers: function() {
      const textfield = this.__serviceFilters.getTextFilter().getChildControl("textfield", true);
      textfield.addListener("appear", () => {
        osparc.component.filter.UIFilterController.getInstance().resetGroup("serviceCatalog");
        textfield.focus();
      }, this);
      textfield.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          const selectables = this.__servicesList.getSelectables();
          if (selectables) {
            this.__servicesList.setSelection([selectables[0]]);
          }
        }
      }, this);
    },

    __serviceSelected: function(serviceKey) {
      if (this.__versionsList) {
        const versionsList = this.__versionsList;
        versionsList.removeAll();
        if (serviceKey in this.__allServices) {
          const versions = osparc.utils.Services.getVersions(this.__allServices, serviceKey);
          if (versions) {
            let lastItem = null;
            versions.forEach(version => {
              lastItem = new qx.ui.form.ListItem(version);
              versionsList.add(lastItem);
            });
            if (lastItem) {
              versionsList.setSelection([lastItem]);
              this.__versionSelected(lastItem.getLabel());
            }
          }
        } else {
          this.__updateServiceDescription(null);
        }
      }
    },

    __versionSelected: function(versionKey) {
      const serviceSelection = this.__servicesList.getSelection();
      if (serviceSelection.length > 0) {
        const serviceKey = serviceSelection[0].getModel();
        const selectedService = osparc.utils.Services.getFromObject(this.__allServices, serviceKey, versionKey);
        this.__updateServiceDescription(selectedService);
      }
    },

    __updateServiceDescription: function(selectedService) {
      const serviceDescription = this.__serviceDescription;
      if (serviceDescription) {
        if (selectedService) {
          const serviceInfo = new osparc.component.metadata.ServiceInfo(selectedService);
          serviceDescription.add(serviceInfo);
        } else {
          serviceDescription.add(null);
        }
      }
    },

    __nodeCheck: function(services) {
      /** a little ajv test */
      let nodeCheck = new qx.io.request.Xhr("/resource/osparc/node-meta-v0.0.1.json");
      nodeCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new osparc.wrapper.Ajv(data);
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
