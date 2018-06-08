/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox());

    this.__createUserList();
    this.__createTempList();
  },

  events: {
    "StartPrj": "qx.event.type.Data"
  },

  members: {
    __controller: null,
    __list: null,
    __controller2: null,
    __list2: null,

    __createUserList: function() {
      // layout
      let prjLst = this.__list = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 0,
        allowGrowY: false
      });

      this.add(prjLst);

      // controller

      let prjCtr = this.__controller = new qx.data.controller.List(qxapp.desktop.PrjBrowser.getFakeUserModel(), prjLst, "name");
      this.__setDelegate(prjCtr);
      // FIXME: selection does not work if model is not passed in the constructor!!!!
      // prjCtr.setModel();

      // Monitors change in selection
      prjCtr.getSelection().addListener("change", function(e) {
        const selectedItem = e.getTarget().toArray()[0];
        this.fireDataEvent("StartPrj", selectedItem);
      }, this);
    },

    __createTempList: function() {
      // layout
      let prjLst = this.__list2 = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 0,
        allowGrowY: false
      });

      this.add(prjLst);

      // controller

      let prjCtr = this.__controller2 = new qx.data.controller.List(qxapp.desktop.PrjBrowser.getFakeTempModel(), prjLst, "name");
      this.__setDelegate(prjCtr);
      // FIXME: selection does not work if model is not passed in the constructor!!!!
      // prjCtr.setModel();

      // Monitors change in selection
      prjCtr.getSelection().addListener("change", function(e) {
        console.debug("Selected", this.__controller2.getSelection());

        const selectedItem = e.getTarget().toArray()[0];
        this.fireDataEvent("StartPrj", selectedItem);
      }, this);
    },

    /**
     * Delegates apperance and binding of each project item
     */
    __setDelegate: function(projectController) {
      let delegate = {
        // Item's Layout
        configureItem: function(item) {
          item.set({
            iconPosition: "top",
            gap: 0,
            rich: true,
            allowGrowY: false,
            maxWidth: 200
          });
        },
        // Item's data binding
        bindItem: function(controler, item, id) {
          controler.bindProperty("name", "label", {
            converter: function(data, model, source, target) {
              return "<b>" + data + "</b>"; // + model.getDescription();
            }
          }, item, id);
          controler.bindProperty("thumbnail", "icon", {
            converter: function(data) {
              return data === null ? "http://via.placeholder.com/171x96" : data;
            }
          }, item, id);
        }
      };

      projectController.setDelegate(delegate);
    }

  }, // members

  statics: {

    /**
     * Mockup data
     */
    getFakeUserModel: function() {
      let data = qxapp.data.Fake.getUserProjects(3, "bizzy");
      data.insertAt(0, qxapp.data.Fake.NEW_PROJECT_DESCRIPTOR);
      return data;
    },

    getFakeTempModel: function() {
      let data = qxapp.data.Fake.getTemplateProjects();
      data.insertAt(0, qxapp.data.Fake.NEW_PROJECT_DESCRIPTOR);
      return data;
    }

  } // statics
});
