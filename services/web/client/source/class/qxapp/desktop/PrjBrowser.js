/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox());

    this.__createProjectList();
    this.__createTemplateList();
  },

  events: {
    "StartProject": "qx.event.type.Data"
  },

  members: {
    __controller: null,
    __list: null,
    __controller2: null,
    __list2: null,

    __createProjectList: function() {
      // layout
      let prjLst = this.__list = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 0,
        allowGrowY: false
      });

      this.add(prjLst);

      // controller

      let prjCtr = this.__controller = new qx.data.controller.List(this.__getProjectArray(), prjLst, "name"
      );
      this.__setDelegate(prjCtr);
      // FIXME: selection does not work if model is not passed in the constructor!!!!
      // prjCtr.setModel();

      // Monitors change in selection
      prjCtr.getSelection().addListener("change", function(e) {
        const selectedItem = e.getTarget().toArray()[0];
        this.fireDataEvent("StartProject", selectedItem);
      }, this);
    },

    __createTemplateList: function() {
      // layout
      let prjLst = this.__list2 = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 0,
        allowGrowY: false
      });

      this.add(prjLst);

      // controller

      let prjCtr = this.__controller2 = new qx.data.controller.List(this.__getTemplateArray(), prjLst, "name");
      this.__setDelegate(prjCtr);
      // FIXME: selection does not work if model is not passed in the constructor!!!!
      // prjCtr.setModel();

      // Monitors change in selection
      prjCtr.getSelection().addListener("change", function(e) {
        const selectedItem = e.getTarget().toArray()[0];
        this.fireDataEvent("StartProject", selectedItem);
      }, this);
    },

    /**
     * Delegates appearance and binding of each project item
     */
    __setDelegate: function(projectController) {
      let delegate = {
        // Item's Layout
        configureItem: function(item) {
          item.set({
            iconPosition: "top",
            gap: 0,
            rich: true,
            allowGrowY: false
          });
          item.getChildControl("icon").set({
            height: 96,
            width: 176
          });
        },
        // Item's data binding
        bindItem: function(controller, item, id) {
          controller.bindProperty("name", "label", {
            converter: function(data, model, source, target) {
              return "<b>" + data + "</b>"; // + model.getDescription();
            }
          }, item, id);
          controller.bindProperty("thumbnail", "icon", {
            converter: function(data) {
              return data === null ? "https://placeimg.com/171/96/tech/grayscale/?random.jpg" : data;
            }
          }, item, id);
        }
      };

      projectController.setDelegate(delegate);
    },

    __getProjectArray: function() {
      return new qx.data.Array(
        qxapp.data.Store.getInstance().getProjectList()
          .map(
            (p, i) => qx.data.marshal.Json.createModel({
              name: p.name,
              thumbnail: "https://placeimg.com/171/96/tech/grayscale/?"+i+".jpg",
              projectId: i,
              created: p.creationDate
            })
          )
      );
    },

    __getTemplateArray: function() {
      let data = this.__getProjectArray();
      data.insertAt(0, qx.data.marshal.Json.createModel({
        name: this.tr("New Project"),
        thumbnail: "@MaterialIcons/create/40",
        projectId: null,
        created: null
      }));
      return data;
    }

  } // statics
});
