/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *   Window that shows a list of filter as you type services. For the selected service, below the list
 * a dropdown menu is populated with al the available versions of the selection (by default latest
 * is selected).
 *
 *   When the user really selects the service an "addService" data event is fired.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let srvCat = new osparc.workbench.ServiceCatalog();
 *   srvCat.center();
 *   srvCat.open();
 * </pre>
 */

qx.Class.define("osparc.workbench.ServiceCatalog", {
  extend: osparc.ui.window.Window,

  construct: function() {
    this.base();

    this.set({
      autoDestroy: true,
      caption: this.tr("Service catalog"),
      showMinimize: false,
      minWidth: 490,
      width: this.self().Width,
      minHeight: 400,
      height: this.self().Height,
      modal: true,
      contentPadding: 0,
      clickAwayClose: true
    });

    this.__sortBy = osparc.service.SortServicesButtons.DefaultSorting;

    let catalogLayout = new qx.ui.layout.VBox();
    this.setLayout(catalogLayout);

    let filterLayout = this.__createFilterLayout();
    this.add(filterLayout);

    let list = this.__createListLayout();
    this.add(list, {
      flex: 1
    });

    let btnLayout = this.__createButtonsLayout();
    this.add(btnLayout);

    this.__createEvents();

    this.__populateList();

    this.__attachEventHandlers();
  },

  events: {
    "addService": "qx.event.type.Data"
  },

  statics: {
    LATEST: "latest",
    Width: 580,
    Height: 500
  },

  members: {
    __allServicesList: null,
    __filteredServicesObj: null,
    __textFilter: null,
    __contextLeftNodeId: null,
    __contextRightNodeId: null,
    __versionsBox: null,
    __infoBtn: null,
    __serviceBrowser: null,
    __addBtn: null,
    __sortBy: null,

    __createFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        appearance: "margined-layout"
      });

      const filters = new osparc.filter.group.ServiceFilterGroup("serviceCatalog").set({
        maxHeight: 25
      });
      this.__textFilter = filters.getTextFilter().getChildControl("textfield", true);
      layout.add(filters);

      layout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      if (osparc.data.Permissions.getInstance().canDo("services.all.reupdate")) {
        const reloadBtn = new qx.ui.form.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/12");
        reloadBtn.addListener("execute", () => this.__populateList(true), this);
        layout.add(reloadBtn);
      }

      const containterSortBtns = new osparc.service.SortServicesButtons();
      containterSortBtns.addListener("sortBy", e => {
        this.__sortBy = e.getData();
        this.__populateList();
      }, this);
      layout.add(containterSortBtns);

      return layout;
    },

    __createListLayout: function() {
      // Services list
      this.__allServicesList = [];
      this.__filteredServicesObj = {};

      const services = this.__serviceBrowser = new osparc.service.ServiceList("serviceCatalog").set({
        width: 568,
        backgroundColor: "background-main"
      });
      const scrolledServices = new qx.ui.container.Scroll().set({
        height: 260
      });
      scrolledServices.add(services);

      this.__serviceBrowser.addListener("changeValue", e => {
        if (e.getData() && e.getData().getServiceModel()) {
          const selectedService = e.getData().getServiceModel();
          this.__changedSelection(selectedService.getKey());
        } else {
          this.__changedSelection(null);
        }
      }, this);

      return scrolledServices;
    },

    __createButtonsLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        appearance: "margined-layout"
      });

      const versionLabel = new qx.ui.basic.Atom(this.tr("Version"));
      layout.add(versionLabel);
      const selectBox = this.__versionsBox = new qx.ui.form.SelectBox().set({
        enabled: false
      });
      layout.add(selectBox);
      const infoBtn = this.__infoBtn = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/16").set({
        enabled: false
      });
      infoBtn.addListener("execute", () => this.__showServiceDetails(), this);
      layout.add(infoBtn);

      layout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const cancelBtn = new qx.ui.form.Button("Cancel");
      cancelBtn.addListener("execute", this.__onCancel, this);
      cancelBtn.setAllowGrowX(false);
      layout.add(cancelBtn);
      const addBtn = this.__addBtn = new qx.ui.form.Button("Add").set({
        appearance: "strong-button",
        enabled: false
      });
      addBtn.addListener("execute", () => this.__onAddService(), this);
      layout.add(addBtn);

      return layout;
    },

    __createEvents: function() {
      this.__serviceBrowser.addListener("serviceAdd", e => {
        this.__onAddService(e.getData());
      }, this);
    },

    setContext: function(leftNodeId = null, rightNodeId = null) {
      this.__contextLeftNodeId = leftNodeId;
      this.__contextRightNodeId = rightNodeId;
      this.__updateList();
    },

    __populateList: function(reload = false) {
      this.__allServicesList = [];
      let store = osparc.store.Store.getInstance();
      store.getAllServices(reload, false)
        .then(services => {
          this.__allServicesList = osparc.utils.Services.convertObjectToArray(services);
          this.__updateList();
        });
    },

    __updateList: function() {
      osparc.filter.UIFilterController.getInstance().resetGroup("serviceCatalog");
      const filteredServices = [];
      this.__allServicesList.forEach(service => {
        if (this.__contextLeftNodeId === null && this.__contextRightNodeId === null) {
          filteredServices.push(service);
        } else {
          // filter out services that can't be connected
          const needsInputs = this.__contextLeftNodeId !== null;
          const needsOutputs = this.__contextRightNodeId !== null;
          let connectable = needsInputs ? Boolean(Object.keys(service.inputs).length) : true;
          connectable = connectable && (needsOutputs ? Boolean(Object.keys(service.outputs).length) : true);
          if (connectable) {
            filteredServices.push(service);
          }
        }
      });

      osparc.utils.Services.addHits(filteredServices);
      osparc.utils.Services.sortObjectsBasedOn(filteredServices, this.__sortBy);
      const filteredServicesObj = this.__filteredServicesObj = osparc.utils.Services.convertArrayToObject(filteredServices);

      const groupedServicesList = [];
      for (const key in filteredServicesObj) {
        let service = osparc.utils.Services.getLatest(filteredServicesObj, key);
        osparc.utils.Services.addHits([service]);
        service = osparc.utils.Utils.deepCloneObject(service);
        osparc.utils.Services.removeFileToKeyMap(service);
        groupedServicesList.push(qx.data.marshal.Json.createModel(service));
      }

      this.__serviceBrowser.setModel(new qx.data.Array(groupedServicesList));
    },

    __changedSelection: function(key) {
      if (this.__versionsBox) {
        let selectBox = this.__versionsBox;
        selectBox.removeAll();
        if (key in this.__filteredServicesObj) {
          let versions = osparc.utils.Services.getVersions(this.__filteredServicesObj, key);
          const latest = new qx.ui.form.ListItem(this.self(arguments).LATEST);
          selectBox.add(latest);
          for (let i = versions.length; i--;) {
            selectBox.add(new qx.ui.form.ListItem(versions[i]));
          }
          selectBox.setSelection([latest]);
        }
      }
      if (this.__addBtn) {
        this.__addBtn.setEnabled(key !== null);
      }
      if (this.__infoBtn) {
        this.__infoBtn.setEnabled(key !== null);
      }
      if (this.__versionsBox) {
        this.__versionsBox.setEnabled(key !== null);
      }
    },

    __onAddService: function(model) {
      if (model == null && this.__serviceBrowser.isSelectionEmpty()) {
        return;
      }

      let serviceModel = model;
      if (!serviceModel) {
        let service = this.__getSelectedService();
        service = osparc.utils.Utils.deepCloneObject(service);
        osparc.utils.Services.removeFileToKeyMap(service);
        serviceModel = qx.data.marshal.Json.createModel(service);
      }
      if (serviceModel) {
        const eData = {
          service: serviceModel,
          nodeLeftId: this.__contextLeftNodeId,
          nodeRightId: this.__contextRightNodeId
        };
        this.fireDataEvent("addService", eData);
      }
      this.close();
    },

    __getSelectedService: function() {
      const selected = this.__serviceBrowser.getSelected();
      const key = selected.getKey();
      let version = this.__versionsBox.getSelection()[0].getLabel().toString();
      if (version == this.self(arguments).LATEST.toString()) {
        version = this.__versionsBox.getChildrenContainer().getSelectables()[1].getLabel();
      }
      return osparc.utils.Services.getFromArray(this.__allServicesList, key, version);
    },

    __showServiceDetails: function() {
      const serviceDetails = new osparc.info.ServiceLarge(this.__getSelectedService());
      const title = this.tr("Service information");
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
    },

    __onCancel: function() {
      this.close();
    },

    __attachEventHandlers: function() {
      this.addListener("appear", () => {
        osparc.filter.UIFilterController.getInstance().resetGroup("serviceCatalog");
        this.__textFilter.focus();
      }, this);
      this.__textFilter.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          this.__serviceBrowser.selectFirstVisible();
          const selected = this.__serviceBrowser.getSelected();
          if (selected !== null) {
            this.__onAddService(selected);
          }
        }
      }, this);
    }
  }
});
