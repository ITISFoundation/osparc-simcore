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


    // Controls
    // create the textfield
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
    filterLayout.add(showAll);
    // buttons for reloading services
    let reloadBtn = new qx.ui.form.Button().set({
      icon: "@FontAwesome5Solid/sync-alt/16"
    });
    reloadBtn.addListener("execute", function() {
      this.__reloadServices();
    }, this);
    filterLayout.add(reloadBtn);
    this.add(filterLayout);


    // Services list
    this.__allServices = [];

    let list = this.__list = new qx.ui.form.List();
    list.setSelectionMode("one");

    // create the controller
    let controller = this.__controller = new qx.data.controller.List(new qx.data.Array([]), list);
    // set the name for the label property
    controller.setLabelPath("name");
    // convert for the label
    controller.setLabelOptions({
      converter: function(data, model) {
        return model.getName() + " " + model.getVersion();
      }
    });

    // create the filter
    let filterObj = new qxapp.component.workbench.servicesCatalogue.SearchTypeFilter(this.__controller);
    // set the filter
    this.__controller.setDelegate(filterObj);

    // make every input in the textfield update the controller
    textfield.bind("changeValue", filterObj, "searchString");

    this.add(list, {
      flex: 1
    });


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
      let clearData = new qx.data.Array([]);
      this.__controller.setModel(clearData);
    },

    __refilterData: function() {
      this.__setNewData(this.__allServices);
    },

    __setNewData: function(newData) {
      let filteredData = [];
      for (let i = 0; i < newData.length; i++) {
        const service = newData[i];
        if (this.__showAll.getValue() || !service.getKey().includes("demodec")) {
          filteredData.push(service);
        }
      }
      let newModel = new qx.data.Array(filteredData);
      this.__controller.setModel(newModel);
      this.__controller.update();
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

      let selection = this.__list.getSelection()[0];
      for (let i = 0; i < this.__allServices.length; i++) {
        if (selection.getModel().getKey() === this.__allServices[i].getKey() &&
          selection.getModel().getVersion() === this.__allServices[i].getVersion()) {
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
