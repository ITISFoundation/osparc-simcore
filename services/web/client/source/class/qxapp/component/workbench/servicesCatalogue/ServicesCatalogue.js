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
    __allServicesList: null,
    __allServicesObj: null,
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
        this.__updateList();
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
        this.__populateList(true);
      }, this);
      filterLayout.add(reloadBtn);

      return filterLayout;
    },

    __createListLayout: function() {
      // Services list
      this.__allServicesList = [];
      this.__allServicesObj = {};

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
      let filterObj = new qxapp.component.workbench.servicesCatalogue.SearchTypeFilter(this.__controller, ["name"]);
      // set the filter
      filterObj.bindItem = (ctrl, item, id) => {
        controller.bindDefaultProperties(item, id);
      };
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

    setContext: function(nodeId, port) {
      this.__contextNodeId = nodeId;
      this.__contextPort = port;
      this.__updateList();
    },

    __populateList: function(reload = false) {
      this.__allServicesList = [];
      let store = qxapp.data.Store.getInstance();
      let services = store.getServices(reload);
      if (services === null) {
        store.addListener("servicesRegistered", e => {
          const data = e.getData();
          this.__addNewData(data["services"]);
        }, this);
      } else {
        this.__addNewData(services);
      }
    },

    __addNewData: function(newData) {
      this.__allServicesList = qxapp.utils.Services.convertObjectToArray(newData);
      this.__updateList(this.__allServicesList);
    },

    __updateList: function() {
      let filteredServices = [];
      for (let i = 0; i < this.__allServicesList.length; i++) {
        const service = this.__allServicesList[i];
        if (this.__showAll.getValue() || !service.key.includes("demodec")) {
          filteredServices.push(service);
        }
      }

      let groupedServices = this.__allServicesObj = qxapp.utils.Services.convertArrayToObject(filteredServices);

      let groupedServicesList = [];
      for (const serviceKey in groupedServices) {
        let service = qxapp.utils.Services.getLatest(groupedServices, serviceKey);
        let newModel = qx.data.marshal.Json.createModel(service);
        groupedServicesList.push(newModel);
      }


      let newModel = new qx.data.Array(groupedServicesList);
      this.__controller.setModel(newModel);
      this.__controller.update();
    },

    __changedSelection: function(serviceKey) {
      if (this.__versionsBox) {
        let selectBox = this.__versionsBox;
        selectBox.removeAll();
        if (serviceKey in this.__allServicesObj) {
          let versions = qxapp.utils.Services.getVersions(this.__allServicesObj, serviceKey);
          const latest = new qx.ui.form.ListItem(this.tr(LATEST));
          selectBox.add(latest);
          for (let i = versions.length; i--;) {
            selectBox.add(new qx.ui.form.ListItem(versions[i]));
          }
          selectBox.setSelection([latest]);
        }
      }
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
      let service = qxapp.utils.Services.getFromArray(this.__allServicesList, serviceKey, serviceVersion);
      if (service) {
        let serviceModel = qx.data.marshal.Json.createModel(service);
        const eData = {
          service: serviceModel,
          contextNodeId: this.__contextNodeId,
          contextPort: this.__contextPort
        };
        this.fireDataEvent("addService", eData);
      }
      this.close();
    },

    __onCancel: function() {
      this.close();
    }
  }
});
