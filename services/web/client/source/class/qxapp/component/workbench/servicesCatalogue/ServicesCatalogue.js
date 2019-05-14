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
 *   let srvCat = new qxapp.component.workbench.servicesCatalogue.ServicesCatalogue();
 *   srvCat.center();
 *   srvCat.open();
 * </pre>
 */

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
      caption: this.tr("Services Catalogue"),
      appearance: "service-window",
      contentPadding: 0
    });

    let catalogueLayout = new qx.ui.layout.VBox();
    this.setLayout(catalogueLayout);

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
    LATEST: "latest"
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
    __serviceBrowser: null,

    __createFilterLayout: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();

      const filterPart = new qx.ui.toolbar.Part().set({
        spacing: 10
      });
      const filter = new qxapp.component.filter.TextFilter("text", "services");
      this.__textfield = filter.getChildControl("textfield", true);
      filterPart.add(filter);
      const showAllCheckbox = this.__showAll = new qx.ui.form.CheckBox(this.tr("Show all"));
      showAllCheckbox.set({
        value: false,
        // FIXME: Backend should do the filtering
        visibility: qxapp.data.Permissions.getInstance().canDo("test") ? "visible" : "excluded"
      });
      showAllCheckbox.addListener("changeValue", e => {
        this.__updateList();
      }, this);
      filterPart.add(showAllCheckbox);
      toolbar.add(filterPart);

      toolbar.addSpacer();

      const controlsPart = new qx.ui.toolbar.Part();
      // buttons for reloading services (is this necessary?)
      const reloadBtn = new qx.ui.toolbar.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/16");
      reloadBtn.addListener("execute", () => this.__populateList(true), this);
      controlsPart.add(reloadBtn);
      toolbar.add(controlsPart);
      return toolbar;
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
      this.__textfield.bind("input", filterObj, "searchString");

      const services = this.__serviceBrowser = new qxapp.component.service.ServiceBrowser().set({
        width: 568
      });
      const scrolledServices = new qx.ui.container.Scroll().set({
        height: 260
      });
      scrolledServices.add(services);
      return scrolledServices;

      return list;
    },

    __createButtonsLayout: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();

      const infoPart = new qx.ui.toolbar.Part();
      const versionLabel = new qx.ui.basic.Atom(this.tr("Version"));
      infoPart.add(versionLabel);
      const selectBox = this.__versionsBox = new qxapp.ui.toolbar.SelectBox();
      selectBox.add(new qx.ui.form.ListItem(this.tr(this.self(arguments).LATEST)));
      selectBox.setValue(selectBox.getChildrenContainer().getSelectables()[0].getLabel());
      infoPart.add(selectBox);
      const infoBtn = new qx.ui.toolbar.Button(null, "@FontAwesome5Solid/info-circle/16");
      infoBtn.addListener("execute", function() {
        this.__showServiceInfo();
      }, this);
      infoPart.add(infoBtn);
      toolbar.add(infoPart);

      toolbar.addSpacer();

      const buttonsPart = new qx.ui.toolbar.Part();
      const addBtn = new qx.ui.toolbar.Button("Add");
      addBtn.addListener("execute", this.__onAddService, this);
      addBtn.setAllowGrowX(false);
      buttonsPart.add(addBtn);
      const cancelBtn = new qx.ui.toolbar.Button("Cancel");
      cancelBtn.addListener("execute", this.__onCancel, this);
      cancelBtn.setAllowGrowX(false);
      buttonsPart.add(cancelBtn);
      toolbar.add(buttonsPart);

      return toolbar;
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

      this.__serviceBrowser.setModel(newModel);
    },

    __changedSelection: function(serviceKey) {
      if (this.__versionsBox) {
        let selectBox = this.__versionsBox;
        selectBox.removeAll();
        if (serviceKey in this.__allServicesObj) {
          let versions = qxapp.utils.Services.getVersions(this.__allServicesObj, serviceKey);
          const latest = new qx.ui.form.ListItem(this.tr(this.self(arguments).LATEST));
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

      const service = this.__getSelectedService();
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

    __getSelectedService: function() {
      const selection = this.__list.getSelection()[0];
      const serviceKey = selection.getModel().getKey();
      let serviceVersion = this.__versionsBox.getSelection()[0].getLabel().toString();
      if (serviceVersion == this.tr(this.self(arguments).LATEST).toString()) {
        serviceVersion = this.__versionsBox.getChildrenContainer().getSelectables()[1].getLabel();
      }
      return qxapp.utils.Services.getFromArray(this.__allServicesList, serviceKey, serviceVersion);
    },

    __showServiceInfo: function() {
      const selectedService = this.__getSelectedService();
      const jsonTreeWidget = new qxapp.component.widget.JsonTreeWidget(selectedService, "serviceDescriptionCatalogue");
      const win = new qx.ui.window.Window("Service info").set({
        showMinimize: false,
        showMaximize: false,
        allowMaximize: false,
        showStatusbar: false,
        modal: true,
        width: 550,
        height: 550,
        layout: new qx.ui.layout.Canvas()
      });
      win.add(jsonTreeWidget, {
        top: -30,
        right: 0,
        bottom: 0,
        left: -60
      });
      win.center();
      win.open();
    },

    __onCancel: function() {
      this.close();
    },

    __attachEventHandlers: function() {
      this.addListener("appear", () => {
        this.__textfield.focus();
      }, this);
    }
  }
});
