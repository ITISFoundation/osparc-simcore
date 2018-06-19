/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.workbench.servicesCatalogue.ServicesCatalogue", {
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
    let searchLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
    let searchLabel = new qx.ui.basic.Label("Search");
    searchLayout.add(searchLabel);
    let textfield = new qx.ui.form.TextField();
    textfield.setLiveUpdate(true);
    searchLayout.add(textfield, {
      flex: 1
    });
    this.add(searchLayout);

    this.__allServices = qxapp.data.Fake.getServices();
    // TODO: OM & PC replace this with delegates
    let rawData2 = [];
    for (let i = 0; i < this.__allServices.length; i++) {
      rawData2.push(this.__allServices[i].name);
    }
    this.__rawData = new qx.data.Array(rawData2);

    this.__list = new qx.ui.form.List();
    this.add(this.__list, {
      flex: 1
    });
    this.__list.setSelectionMode("one");

    // create the controller
    this.__controller = new qx.data.controller.List(this.__rawData, this.__list);
    // controller.setLabelPath("name");

    // create the filter
    let filterObj = new qxapp.components.workbench.servicesCatalogue.SearchTypeFilter(this.__controller);
    // Item's data sorting
    filterObj.sorter = function(a, b) {
      return a > b;
    };
    // set the filter
    this.__controller.setDelegate(filterObj);

    // make every input in the textfield update the controller
    textfield.bind("changeValue", filterObj, "searchString");


    // crate buttons
    let box = new qx.ui.layout.HBox(10);
    box.setAlignX("right");
    let buttonsLayout = new qx.ui.container.Composite(box);

    let addBtn = new qx.ui.form.Button("Add");
    addBtn.addListener("execute", this.__onAddService, this);
    addBtn.setAllowGrowX(false);
    buttonsLayout.add(addBtn);

    let cancelBtn = new qx.ui.form.Button("Cancel");
    cancelBtn.addListener("execute", this.__onCancel, this);
    cancelBtn.setAllowGrowX(false);
    buttonsLayout.add(cancelBtn);

    this.add(buttonsLayout);

    // Listen to "Enter" key
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__onAddService();
      }
    }, this);

    // Listen to "Double Click" key
    this.__list.addListener("dblclick", function(mouseEvent) {
      this.__onAddService();
    }, this);
  },

  events: {
    "AddService": "qx.event.type.Data"
  },

  members: {
    __allServices: null,
    __rawData: null,
    __list: null,
    __controller: null,
    __contextNodeId: null,
    __contextPort: null,

    setContext: function(nodeId, port) {
      this.__contextNodeId = nodeId;
      this.__contextPort = port;
      this.__updateCompatibleList();
    },

    __updateCompatibleList: function() {
      let newData = [];
      for (let i = 0; i < this.__allServices.length; i++) {
        if (this.__contextPort.isInput === true) {
          for (let j = 0; j < this.__allServices[i].outputs.length; j++) {
            if (this.__allServices[i].outputs[j].type === this.__contextPort.portType) {
              newData.push(this.__allServices[i].name);
              break;
            }
          }
        } else {
          for (let j = 0; j < this.__allServices[i].inputs.length; j++) {
            if (this.__allServices[i].inputs[j].type === this.__contextPort.portType) {
              newData.push(this.__allServices[i].name);
              break;
            }
          }
        }
      }
      this.__setNewData(newData);
    },

    __setNewData: function(newData) {
      let filteredData = new qx.data.Array(newData);
      this.__controller.setModel(filteredData);
    },

    __keyEvent: function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__onAddService();
      }
    },

    __onAddService: function() {
      if (this.__list.isSelectionEmpty()) {
        return;
      }

      let selection = this.__list.getSelection();
      let selectedLabel = selection[0].getLabel();
      for (let i = 0; i < this.__allServices.length; i++) {
        if (selectedLabel === this.__allServices[i].name) {
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
