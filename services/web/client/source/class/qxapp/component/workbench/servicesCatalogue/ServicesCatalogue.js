/* eslint no-warning-comments: "off" */

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


    // create the textfield
    let filterLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
    let searchLabel = new qx.ui.basic.Label(this.tr("Search"));
    filterLayout.add(searchLabel);
    let textfield = this.__textfield = new qx.ui.form.TextField();
    textfield.setLiveUpdate(true);
    filterLayout.add(textfield, {
      flex: 1
    });
    let showAll = this.__showAll = new qx.ui.form.CheckBox(this.tr("Show all"));
    showAll.setValue(true);
    showAll.addListener("changeValue", e => {
      this.__showAllServices(e.getData());
    }, this);
    filterLayout.add(showAll);
    this.add(filterLayout);

    this.__allServices = [];
    let names = [];
    let rawData = new qx.data.Array(names);

    this.__list = new qx.ui.form.List();
    this.add(this.__list, {
      flex: 1
    });
    this.__list.setSelectionMode("one");

    // create the controller
    this.__controller = new qx.data.controller.List(rawData, this.__list);
    // controller.setLabelPath("name");

    // create the filter
    let filterObj = new qxapp.component.workbench.servicesCatalogue.SearchTypeFilter(this.__controller);
    // Item's data sorting
    filterObj.sorter = function(a, b) {
      return a > b;
    };
    // set the filter
    this.__controller.setDelegate(filterObj);

    // make every input in the textfield update the controller
    textfield.bind("changeValue", filterObj, "searchString");


    // create buttons
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

    this.add(btnLayout);

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

    this.__populateList();
  },

  events: {
    "AddService": "qx.event.type.Data"
  },

  members: {
    __allServices: null,
    __textfield: null,
    __showAll: null,
    __list: null,
    __controller: null,
    __contextNodeId: null,
    __contextPort: null,

    setContext: function(nodeId, port) {
      this.__contextNodeId = nodeId;
      this.__contextPort = port;
      this.__updateCompatibleList();
    },

    __populateList: function() {
      let store = qxapp.data.Store.getInstance();
      let services = store.getServices();
      if (services === null) {
        store.addListener("servicesRegistered", e => {
          this.__addNewData(e.getData());
        }, this);
      } else {
        this.__addNewData(services);
      }
    },

    __getServiceNameInList: function(service) {
      return (service.name + " " + service.version);
    },

    __showAllServices: function(show) {
      let newData = [];
      for (let i = 0; i < this.__allServices.length; i++) {
        const service = this.__allServices[i];
        if (show) {
          const listName = this.__getServiceNameInList(service);
          newData.push(listName);
        } else if (!service.key.includes("demodec")) {
          const listName = this.__getServiceNameInList(service);
          newData.push(listName);
        }
      }
      this.__setNewData(newData);
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
                const listName = this.__getServiceNameInList(this.__allServices[i]);
                newData.push(listName);
                break;
              }
            }
          } else {
            let inputsMap = this.__allServices[i].inputs;
            for (let key in inputsMap) {
              if (this.__areNodesCompatible(inputsMap[key], this.__contextPort)) {
                const listName = this.__getServiceNameInList(this.__allServices[i]);
                newData.push(listName);
                break;
              }
            }
          }
        }
      } else {
        for (let i = 0; i < this.__allServices.length; i++) {
          const listName = this.__getServiceNameInList(this.__allServices[i]);
          newData.push(listName);
        }
      }
      this.__setNewData(newData);
    },


    __areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      return qxapp.data.Store.getInstance().areNodesCompatible(topLevelPort1, topLevelPort2);
    },

    __setNewData: function(newData) {
      let filteredData = new qx.data.Array(newData);
      this.__controller.setModel(filteredData);
    },

    __addNewData: function(newData) {
      for (const serviceKey in newData) {
        this.__allServices.push(newData[serviceKey]);
      }
      this.__updateCompatibleList();
    },

    __onAddService: function() {
      if (this.__list.isSelectionEmpty()) {
        return;
      }

      let selection = this.__list.getSelection();
      let selectedLabel = selection[0].getLabel();
      for (let i = 0; i < this.__allServices.length; i++) {
        const listName = this.__getServiceNameInList(this.__allServices[i]);
        if (selectedLabel === listName) {
          const eData = {
            service: this.__allServices[i],
            contextNodeId: this.__contextNodeId,
            contextPort: this.__contextPort
          };
          this.fireDataEvent("AddService", eData);
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
