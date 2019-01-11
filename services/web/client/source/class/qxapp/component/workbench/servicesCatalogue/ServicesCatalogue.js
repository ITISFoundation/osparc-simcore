/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

const LATEST = "latest";

qx.Class.define("qxapp.component.workbench.servicesCatalogue.ServicesCatalogue", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base();

    this.set({
      showMinimize: false,
      showStatusbar: false,
      minWidth: 400,
      minHeight: 400,
      modal: true,
      caption: "Services Catalogue"
    });

    let catalogueLayout = new qx.ui.layout.VBox(10);
    this.setLayout(catalogueLayout);

    let filterLayout = this.__createFilterLayout();
    this.add(filterLayout);

    let list = this.__createListLayout();
    this.add(list, {
      flex: 1
    });

    let versionLayout = this.__createVersionsLayout();
    this.add(versionLayout);

    let btnLayout = this.__createButtonsLayout();
    this.add(btnLayout);

    this.__createEvents();

    this.__populateList();
  },

  events: {
    "addService": "qx.event.type.Data"
  },

  members: {
    __allServices: null,
    __groupedServices: null,
    __textfield: null,
    __showAll: null,
    __list: null,
    __controller: null,
    __contextNodeId: null,
    __contextPort: null,
    __versionsBox: null,

    __createFilterLayout: function() {
      let filterLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      let searchLabel = new qx.ui.basic.Label(this.tr("Search"));
      filterLayout.add(searchLabel);
      let textfield = this.__textfield = new qx.ui.form.TextField();
      textfield.setLiveUpdate(true);
      filterLayout.add(textfield, {
        flex: 1
      });
      // check box for filtering
      let showAll = this.__showAll = new qx.ui.form.CheckBox(this.tr("Show all"));
      showAll.setValue(false);
      showAll.addListener("changeValue", e => {
        this.__refilterData();
      }, this);
      // FIXME: Backend should do the filtering
      if (qxapp.data.Permissions.getInstance().canDo("test")) {
        filterLayout.add(showAll);
      }
      // buttons for reloading services
      let reloadBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/sync-alt/16"
      });
      reloadBtn.addListener("execute", function() {
        this.__reloadServices();
      }, this);
      filterLayout.add(reloadBtn);

      return filterLayout;
    },

    __createListLayout: function() {
      // Services list
      this.__allServices = [];
      this.__groupedServices = {};

      let list = this.__list = new qx.ui.form.List();
      list.setSelectionMode("one");
      /*
      list.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedService = e.getData()[0].getModel();
          this.__changedSelection(selectedService.getKey());
        } else {
          this.__changedSelection(null);
        }
      }, this);
      */

      // create the controller
      let controller = this.__controller = new qx.data.controller.List(new qx.data.Array([]), list);
      // set the name for the label property
      controller.setLabelPath("name");
      // convert for the label
      controller.setLabelOptions({
        converter: function(data, model) {
          return model.getName();
        }
      });
      // Workaround to the list.changeSelection
      controller.addListener("changeValue", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedService = e.getData().toArray()[0];
          this.__changedSelection(selectedService.getKey());
        } else {
          this.__changedSelection(null);
        }
      }, this);

      // create the filter
      let filterObj = new qxapp.component.workbench.servicesCatalogue.SearchTypeFilter(this.__controller);
      // set the filter
      this.__controller.setDelegate(filterObj);

      // make every input in the textfield update the controller
      this.__textfield.bind("changeValue", filterObj, "searchString");

      return list;
    },

    __createVersionsLayout: function() {
      let versionLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      let versionLabel = new qx.ui.basic.Label(this.tr("Version"));
      versionLayout.add(versionLabel);
      let selectBox = this.__versionsBox = new qx.ui.form.SelectBox();
      selectBox.add(new qx.ui.form.ListItem(this.tr(LATEST)));
      selectBox.setValue(selectBox.getChildrenContainer().getSelectables()[0].getLabel());
      versionLayout.add(selectBox);
      return versionLayout;
    },

    __createButtonsLayout: function() {
      let btnBox = new qx.ui.layout.HBox(10);
      btnBox.setAlignX("right");
      let btnLayout = new qx.ui.container.Composite(btnBox);

      let addBtn = new qx.ui.form.Button("Add");
      addBtn.addListener("execute", this.__onAddService, this);
      addBtn.setAllowGrowX(false);
      btnLayout.add(addBtn);

      let cancelBtn = new qx.ui.form.Button("Cancel");
      cancelBtn.addListener("execute", this.__onCancel, this);
      cancelBtn.setAllowGrowX(false);
      btnLayout.add(cancelBtn);

      return btnLayout;
    },

    __createEvents: function() {
      // Listen to "Enter" key
      this.addListener("keypress", keyEvent => {
        if (keyEvent.getKeyIdentifier() === "Enter") {
          this.__onAddService();
        }
      }, this);

      // Listen to "Double Click" key
      this.__list.addListener("dbltap", e => {
        this.__onAddService();
      }, this);
    },

    __populateList: function(reload = false) {
      this.__allServices = [];
      let store = qxapp.data.Store.getInstance();
      let services = store.getServices(reload);
      if (services === null) {
        store.addListener("servicesRegistered", e => {
          this.__addNewData(e.getData());
        }, this);
      } else {
        this.__addNewData(services);
      }
    },

    setContext: function(nodeId, port) {
      this.__contextNodeId = nodeId;
      this.__contextPort = port;
      this.__updateCompatibleList();
    },

    __reloadServices: function() {
      this.__clearData();
      this.__populateList(true);
    },

    __updateCompatibleList: function() {
      let newData = [];
      const checkComptibility = false;
      if (checkComptibility && this.__contextNodeId !== null && this.__contextPort !== null) {
        for (let i = 0; i < this.__allServices.length; i++) {
          if (this.__contextPort.isInput === true) {
            let outputsMap = this.__allServices[i].outputs;
            for (let key in outputsMap) {
              if (this.__areNodesCompatible(outputsMap[key], this.__contextPort)) {
                newData.push(this.__allServices[i]);
                break;
              }
            }
          } else {
            let inputsMap = this.__allServices[i].inputs;
            for (let key in inputsMap) {
              if (this.__areNodesCompatible(inputsMap[key], this.__contextPort)) {
                newData.push(this.__allServices[i]);
                break;
              }
            }
          }
        }
      } else {
        for (let i = 0; i < this.__allServices.length; i++) {
          newData.push(this.__allServices[i]);
        }
      }
      this.__setNewData(newData);
    },


    __areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      return qxapp.data.Store.getInstance().areNodesCompatible(topLevelPort1, topLevelPort2);
    },

    __clearData: function() {
      this.__allServices = [];
      this.__refilterData();
    },

    __refilterData: function() {
      this.__setNewData(this.__allServices);
    },

    __setNewData: function(newData) {
      let filteredServices = [];
      for (let i = 0; i < newData.length; i++) {
        const service = newData[i];
        if (this.__showAll.getValue() || !service.getKey().includes("demodec")) {
          filteredServices.push(service);
        }
      }


      let groupedServices = this.__groupedServices = {};
      for (let i = 0; i < filteredServices.length; i++) {
        const service = filteredServices[i];
        if (!Object.prototype.hasOwnProperty.call(groupedServices, service.getKey())) {
          groupedServices[service.getKey()] = [];
        }
        groupedServices[service.getKey()].push({
          [service.getVersion()]: service
        });
        groupedServices[service.getKey()].sort(function(a, b) {
          return qxapp.utils.Utils.compareVersionNumbers(Object.keys(a)[0], Object.keys(b)[0]);
        });
      }

      let groupedServicesList = [];
      for (const serviceKey in groupedServices) {
        const services = groupedServices[serviceKey];
        const service = services[services.length - 1];
        groupedServicesList.push(Object.values(service)[0]);
      }


      let newModel = new qx.data.Array(groupedServicesList);
      this.__controller.setModel(newModel);
      this.__controller.update();
    },

    __changedSelection: function(serviceKey) {
      if (this.__versionsBox) {
        let selectBox = this.__versionsBox;
        selectBox.removeAll();
        if (serviceKey in this.__groupedServices) {
          let versions = this.__getVersions(serviceKey);
          const latest = new qx.ui.form.ListItem(this.tr(LATEST));
          selectBox.add(latest);
          for (let i = versions.length; i--;) {
            selectBox.add(new qx.ui.form.ListItem(versions[i]));
          }
          selectBox.setSelection([latest]);
        }
      }
    },

    __getVersions: function(serviceKey) {
      let versions = [];
      if (serviceKey in this.__groupedServices) {
        const groupedService = this.__groupedServices[serviceKey];
        for (let i = 0; i < groupedService.length; i++) {
          versions.push(Object.keys(groupedService[i])[0]);
        }
      }
      return versions;
    },

    __addNewData: function(newData) {
      for (const serviceKey in newData) {
        let newModel = qx.data.marshal.Json.createModel(newData[serviceKey], true);
        this.__allServices.push(newModel);
      }
      this.__updateCompatibleList();
    },

    __onAddService: function() {
      if (this.__list.isSelectionEmpty()) {
        return;
      }

      const selection = this.__list.getSelection()[0];
      const serviceKey = selection.getModel().getKey();
      let serviceVersion = this.__versionsBox.getSelection()[0].getLabel().toString();
      if (serviceVersion == this.tr(LATEST).toString()) {
        serviceVersion = this.__versionsBox.getChildrenContainer().getSelectables()[1].getLabel();
      }
      for (let i = 0; i < this.__allServices.length; i++) {
        if (serviceKey === this.__allServices[i].getKey() && serviceVersion === this.__allServices[i].getVersion()) {
          const eData = {
            service: this.__allServices[i],
            contextNodeId: this.__contextNodeId,
            contextPort: this.__contextPort
          };
          this.fireDataEvent("addService", eData);
          break;
        }
      }
      this.close();
    },

    __onCancel: function() {
      this.close();
    }
  }
});
