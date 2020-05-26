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
 * @ignore(Headers)
 * @ignore(fetch)
 */

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
 *   let servicesView = this.__serviceBrowser = new osparc.dashboard.ServiceBrowser();
 *   this.getRoot().add(servicesView);
 * </pre>
 *
 * @asset(form/service.json)
 * @asset(form/service-data.json)
 */

qx.Class.define("osparc.dashboard.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    const loadingPage = new osparc.ui.message.Loading(this.tr("Loading Services"));
    this._add(loadingPage, {
      flex: 1
    });

    this.__initResources();
  },

  members: {
    __reloadBtn: null,
    __serviceFilters: null,
    __allServices: null,
    __latestServicesModel: null,
    __servicesUIList: null,
    __versionsUIBox: null,
    __deleteServiceBtn: null,
    __selectedService: null,

    /**
     * Function that resets the selected item by reseting the filters and the service selection
     */
    resetSelection: function() {
      if (this.__serviceFilters) {
        this.__serviceFilters.reset();
      }
      if (this.__servicesUIList) {
        this.__servicesUIList.setSelection([]);
      }
    },

    __initResources: function() {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs(true)
        .then(services => {
          this._removeAll();
          this.__createServicesLayout();
          this.__populateList(false);
          this.__attachEventHandlers();
        });
    },

    __populateList: function(reload) {
      this.__reloadBtn.setFetching(true);

      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs(reload)
        .then(services => {
          this.__allServices = services;
          this.__latestServicesModel.removeAll();
          for (const serviceKey in services) {
            const latestService = osparc.utils.Services.getLatest(services, serviceKey);
            this.__latestServicesModel.append(qx.data.marshal.Json.createModel(latestService));
          }
        })
        .finally(() => {
          this.__reloadBtn.setFetching(false);
          this.__serviceFilters.dispatch();
        });
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
      const servicesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        marginTop: 20
      });

      servicesLayout.add(this.__createButtonContainer());

      const serviceFilters = this.__serviceFilters = new osparc.component.filter.group.ServiceFilterGroup("serviceBrowser");
      servicesLayout.add(serviceFilters);

      const servicesUIList = this.__servicesUIList = new qx.ui.form.List().set({
        orientation: "vertical",
        minWidth: 400,
        appearance: "pb-list"
      });
      servicesUIList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedKey = e.getData()[0].getModel();
          this.__serviceSelected(selectedKey);
        }
      }, this);

      const latestServicesModel = this.__latestServicesModel = new qx.data.Array();
      const servCtrl = new qx.data.controller.List(latestServicesModel, servicesUIList, "name");
      servCtrl.setDelegate({
        createItem: () => {
          const item = new osparc.dashboard.ServiceBrowserListItem();
          item.subscribeToFilterGroup("serviceBrowser");
          item.addListener("tap", e => {
            servicesUIList.setSelection([item]);
          });
          return item;
        },
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("key", "model", null, item, id);
          ctrl.bindProperty("key", "key", null, item, id);
          ctrl.bindProperty("version", "version", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("type", "type", null, item, id);
          ctrl.bindProperty("category", "category", null, item, id);
          ctrl.bindProperty("contact", "contact", null, item, id);
        }
      });
      servicesLayout.add(servicesUIList, {
        flex: 1
      });

      return servicesLayout;
    },

    __createServiceDescriptionLayout: function() {
      const descriptionView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        marginTop: 20
      });

      const titleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const descLabel = new qx.ui.basic.Label(this.tr("Description")).set({
        font: "title-16",
        minWidth: 150
      });
      titleContainer.add(descLabel);

      const versionLabel = new qx.ui.basic.Label(this.tr("Version")).set({
        font: "text-14",
        alignY: "middle"
      });
      titleContainer.add(versionLabel);

      const versions = this.__versionsUIBox = new qx.ui.form.SelectBox().set({
        font: "text-14"
      });
      osparc.utils.Utils.setIdToWidget(versions, "serviceBrowserVersionsDrpDwn");
      titleContainer.add(versions);
      versions.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length) {
          this.__versionSelected(e.getData()[0].getLabel());
        }
      }, this);
      descriptionView.add(titleContainer);

      const actionsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      actionsContainer.add(new qx.ui.core.Spacer(300, null));
      const deleteServiceBtn = this.__deleteServiceBtn = new osparc.ui.form.FetchButton(this.tr("Delete")).set({
        allowGrowX: false,
        visibility: "hidden"
      });
      deleteServiceBtn.addListener("execute", () => {
        const msg = this.tr("Are you sure you want to delete the group?");
        const win = new osparc.ui.window.Confirmation(msg);
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteService();
          }
        }, this);
        win.center();
        win.open();
      }, this);
      actionsContainer.add(deleteServiceBtn);
      descriptionView.add(actionsContainer);

      const descriptionContainer = this.__serviceDescription = new qx.ui.container.Scroll();
      descriptionView.add(descriptionContainer, {
        flex: 1
      });
      return descriptionView;
    },

    __createButtonContainer: function() {
      const hBoxLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));

      // button for refetching services
      const reloadBtn = this.__reloadBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Reload"),
        font: "text-14",
        icon: "@FontAwesome5Solid/sync-alt/14",
        allowGrowX: false
      });
      reloadBtn.addListener("execute", function() {
        this.__populateList(true);
      }, this);
      hBoxLayout.add(reloadBtn);
      hBoxLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      osparc.utils.LibVersions.getPlatformName()
        .then(platformName => {
          if (platformName === "dev") {
            const testDataButton = new qx.ui.form.Button(this.tr("Test with data"), "@FontAwesome5Solid/plus-circle/14");
            testDataButton.addListener("execute", () => {
              osparc.utils.Utils.fetchJSON("/resource/form/service-data.json")
                .then(data => {
                  this.__displayServiceSubmissionForm(data);
                });
            });
            hBoxLayout.add(testDataButton);
          }
        });

      const addServiceButton = new qx.ui.form.Button(this.tr("Submit new service"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.addListener("execute", () => {
        this.__displayServiceSubmissionForm();
      });

      hBoxLayout.add(addServiceButton);

      return hBoxLayout;
    },

    __displayServiceSubmissionForm: function(formData) {
      const addServiceWindow = new qx.ui.window.Window(this.tr("Submit a new service")).set({
        appearance: "service-window",
        modal: true,
        autoDestroy: true,
        showMinimize: false,
        allowMinimize: false,
        centerOnAppear: true,
        layout: new qx.ui.layout.Grow(),
        width: 600,
        height: 660
      });
      const scroll = new qx.ui.container.Scroll();
      addServiceWindow.add(scroll);
      const form = new osparc.component.form.json.JsonSchemaForm("/resource/form/service.json", formData);
      form.addListener("ready", () => {
        addServiceWindow.open();
      });
      form.addListener("submit", e => {
        const data = e.getData();
        const headers = new Headers();
        headers.append("Accept", "application/json");
        const body = new FormData();
        body.append("metadata", new Blob([JSON.stringify(data.json)], {
          type: "application/json"
        }));
        if (data.files && data.files.length) {
          const size = data.files[0].size;
          const maxSize = 10; // 10 MB
          if (size > maxSize * 1024 * 1024) {
            osparc.component.message.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          body.append("attachment", data.files[0], data.files[0].name);
        }
        form.setFetching(true);
        fetch("/v0/publications/service-submission", {
          method: "POST",
          headers,
          body
        })
          .then(resp => {
            if (resp.ok) {
              osparc.component.message.FlashMessenger.logAs("Your data was sent to our curation team. We will get back to you shortly.", "INFO");
              addServiceWindow.close();
            } else {
              osparc.component.message.FlashMessenger.logAs("A problem occured while processing your data", "ERROR");
            }
          })
          .finally(() => form.setFetching(false));
      });
      scroll.add(form);
    },

    __attachEventHandlers: function() {
      const textfield = this.__serviceFilters.getTextFilter().getChildControl("textfield", true);
      textfield.addListener("appear", () => {
        osparc.component.filter.UIFilterController.getInstance().resetGroup("serviceCatalog");
        textfield.focus();
      }, this);
      textfield.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          const selectables = this.__servicesUIList.getSelectables();
          if (selectables) {
            this.__servicesUIList.setSelection([selectables[0]]);
          }
        }
      }, this);
    },

    __serviceSelected: function(serviceKey) {
      if (this.__versionsUIBox) {
        const versionsList = this.__versionsUIBox;
        versionsList.removeAll();
        if (serviceKey in this.__allServices) {
          const versions = osparc.utils.Services.getVersions(this.__allServices, serviceKey);
          if (versions) {
            let lastItem = null;
            versions.forEach(version => {
              lastItem = new qx.ui.form.ListItem(version).set({
                font: "text-14"
              });
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
      const serviceSelection = this.__servicesUIList.getSelection();
      if (serviceSelection.length > 0) {
        const serviceKey = serviceSelection[0].getModel();
        const selectedService = osparc.utils.Services.getFromObject(this.__allServices, serviceKey, versionKey);
        this.__updateServiceDescription(selectedService);
      }
    },

    __updateServiceDescription: function(selectedService) {
      let showDelete = false;
      const serviceDescription = this.__serviceDescription;
      if (serviceDescription) {
        const serviceInfo = selectedService ? new osparc.component.metadata.ServiceInfo(selectedService) : null;
        serviceDescription.add(serviceInfo);
        this.__selectedService = selectedService;
        showDelete = this.__canServiceBeDeleted(selectedService);
      }
      this.__deleteServiceBtn.setVisibility(showDelete ? "visible" : "hidden");
    },

    __canServiceBeDeleted: function(selectedService) {
      if (selectedService) {
        const isMacro = selectedService.key.includes("frontend/nodes-group/macros");
        const isOwner = selectedService.contact === osparc.auth.Data.getInstance().getEmail();
        return isMacro && isOwner;
      }
      return false;
    },

    __deleteService: function() {
      this.__deleteServiceBtn.setFetching(true);

      const serviceId = this.__selectedService.id;
      const params = {
        url: {
          dagId: serviceId
        }
      };
      osparc.data.Resources.fetch("dags", "delete", params, serviceId)
        .then(() => {
          this.__updateServiceDescription(null);
          this.__populateList(true);
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Unable to delete the group."), "ERROR");
          console.error(err);
        })
        .finally(() => {
          this.__deleteServiceBtn.setFetching(false);
        });
    }
  }
});
