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
 *   let servicesView = this.__serviceBrowser = new qxapp.desktop.ServiceBrowser();
 *   this.getRoot().add(servicesView);
 * </pre>
 */

qx.Class.define("qxapp.desktop.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const prjBrowserLayout = new qx.ui.layout.VBox(10);
    this._setLayout(prjBrowserLayout);

    const iframe = qxapp.utils.Utils.createLoadingIFrame(this.tr("Services"));
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
    __searchTextfield: null,

    __initResources: function() {
      this.__getServicesPreload();
    },

    __getServicesPreload: function() {
      const store = qxapp.data.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        // Do not validate if are not taking actions
        // this.__nodeCheck(e.getData());
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    },

    __createServicesLayout: function() {
      const servicesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      const servicesList = this.__createServicesList();
      servicesLayout.add(servicesList);

      const versionsList = this.__createVersionsList();
      servicesLayout.add(versionsList);

      const serviceDescription = this.__createServiceDescription();
      servicesLayout.add(serviceDescription, {
        flex: 1
      });

      this._add(servicesLayout);
    },

    __createServicesList: function() {
      const servicesLayout = this.__createVBoxWLabel(this.tr("Services"));

      const serviceFilters = new qxapp.desktop.ServiceFilters("serviceBrowser");
      servicesLayout.add(serviceFilters);

      const servicesList = this.__servicesList = new qx.ui.form.List().set({
        orientation: "vertical",
        spacing: 10,
        minWidth: 500,
        height: 600,
        appearance: "pb-list"
      });
      servicesList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedKey = e.getData()[0].getModel();
          this.__serviceSelected(selectedKey);
        }
      }, this);
      const store = qxapp.data.Store.getInstance();
      const latestServices = [];
      const services = this.__allServices = store.getServices();
      for (const serviceKey in services) {
        latestServices.push(qxapp.utils.Services.getLatest(services, serviceKey));
      }
      const latestServicesModel = new qx.data.Array(
        latestServices.map(s => qx.data.marshal.Json.createModel(s))
      );
      const servCtrl = new qx.data.controller.List(latestServicesModel, servicesList, "name");
      servCtrl.setDelegate({
        createItem: () => {
          const item = new qxapp.desktop.ServiceBrowserListItem();
          item.subscribeToFilterGroup("serviceBrowser");
          item.addListener("tap", e => {
            // const serviceKey = item.getModel();
            // this.__serviceSelected(serviceKey);
            servicesList.setSelection([item]);
          });
          return item;
        },
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("key", "model", null, item, id);
          ctrl.bindProperty("key", "title", null, item, id);
          ctrl.bindProperty("name", "name", null, item, id);
          ctrl.bindProperty("type", "type", null, item, id);
          ctrl.bindProperty("category", "category", null, item, id);
          ctrl.bindProperty("contact", "contact", null, item, id);
        }
      });
      servicesLayout.add(servicesList);

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

    __createFilterByLayout: function(label, btns) {
      let filterTypeLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      let typeLabel = new qx.ui.basic.Label(label);
      filterTypeLayout.add(typeLabel);

      let group = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });
      btns.forEach(cat => {
        let button = new qx.ui.form.ToggleButton(cat).set({
          maxWidth: 150
        });
        group.add(button);
        filterTypeLayout.add(button, {
          flex: 1
        });
      }, this);

      return {
        layout: filterTypeLayout,
        radioGroup: group
      };
    },

    __createVersionsList: function() {
      let versionsLayout = this.__createVBoxWLabel(this.tr("Versions"));

      let versionsList = this.__versionsList = new qx.ui.form.List().set({
        orientation: "vertical",
        spacing: 10,
        minWidth: 100,
        height: 600,
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
      const descriptionLayout = this.__createVBoxWLabel(this.tr("Description"));
      const scroller = this.__serviceDescription = new qx.ui.container.Scroll();
      scroller.add(descriptionLayout);
      descriptionLayout.add(scroller, {
        flex: 1
      });
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
        this.__updateServciceDescription(selectedService);
      }
    },

    __updateServciceDescription: function(selectedService) {
      const serviceDescription = this.__serviceDescription;
      if (selectedService && serviceDescription) {
        let jsonTreeWidget = new qxapp.component.widget.JsonTreeWidget(selectedService, "serviceDescription");
        serviceDescription.add(jsonTreeWidget);
      }
    },

    __nodeCheck: function(services) {
      /** a little ajv test */
      let nodeCheck = new qx.io.request.Xhr("/resource/qxapp/node-meta-v0.0.1.json");
      nodeCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new qxapp.wrapper.Ajv(data);
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
