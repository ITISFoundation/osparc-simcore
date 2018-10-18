/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox());

    this.__createControls();

    this.__createUserProjectList();
    this.__createPublicProjectList();
  },

  events: {
    "StartProject": "qx.event.type.Data"
  },

  members: {
    __controller: null,
    __list: null,
    __controller2: null,
    __list2: null,

    __createControls: function() {
      let controlsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      let newPrjBtn = new qx.ui.form.Button(this.tr("New Project")).set({
        width: 150,
        height: 50
      });
      newPrjBtn.addListener("execute", function() {
        this.__newPrjBtnClkd();
      }, this);
      controlsLayout.add(newPrjBtn);

      this.add(controlsLayout);
    },

    __newPrjBtnClkd: function() {
      let win = new qx.ui.window.Window(this.tr("Create New Project")).set({
        layout: new qx.ui.layout.Canvas(),
        contentPadding: 0,
        showMinimize: false,
        showMaximize: false,
        minWidth: 500
      });

      let newProjectDlg = new qxapp.component.widget.NewProjectDlg();
      newProjectDlg.addListener("CreatePrj", e => {
        const data = e.getData();
        const newPrj = {
          name: data.prjTitle,
          description: data.prjDescription
        };
        this.__startBlankProject(newPrj);
        win.close();
      }, this);
      win.add(newProjectDlg, {
        top: 0,
        right: 0,
        bottom: 0,
        left: 0
      });

      win.center();
      win.open();
    },

    __getProjectModel: function(projectId) {
      let project = new qxapp.data.model.ProjectModel();
      if (projectId) {
        let projectData = qxapp.data.Store.getInstance().getProjectData(projectId);
        projectData.id = String(projectId);
        project = new qxapp.data.model.ProjectModel(projectData);
      }
      return project;
    },

    __createUserProjectList: function() {
      // layout
      let prjLst = this.__list = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 0,
        allowGrowY: false
      });

      this.add(prjLst);

      // controller
      let userPrjList = qxapp.data.Store.getInstance().getUserProjectList();
      let userPrjArray = this.__getProjectArray(userPrjList);
      let prjCtr = this.__controller = new qx.data.controller.List(userPrjArray, prjLst, "name"
      );
      this.__setDelegate(prjCtr);
      // FIXME: selection does not work if model is not passed in the constructor!!!!
      // prjCtr.setModel();

      // Monitors change in selection
      prjCtr.getSelection().addListener("change", e => {
        const selectedItem = e.getTarget().toArray()[0];
        const data = {
          projectModel: this.__getProjectModel(selectedItem.getProjectUuid())
        };
        this.fireDataEvent("StartProject", data);
      }, this);
    },

    __startBlankProject: function(newPrj) {
      let blankProject = this.__getProjectModel();
      blankProject.set({
        name: newPrj.name,
        description: newPrj.description
      });
      const data = {
        projectModel: blankProject
      };
      this.fireDataEvent("StartProject", data);
    },

    __createPublicProjectList: function() {
      // layout
      let prjLst = this.__list2 = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 0,
        allowGrowY: false
      });

      this.add(prjLst);

      // controller
      let publicPrjList = qxapp.data.Store.getInstance().getPublicProjectList();
      let publicPrjArray = this.__getProjectArray(publicPrjList);
      let prjCtr = this.__controller2 = new qx.data.controller.List(publicPrjArray, prjLst, "name");
      this.__setDelegate(prjCtr);
      // FIXME: selection does not work if model is not passed in the constructor!!!!
      // prjCtr.setModel();

      // Monitors change in selection
      prjCtr.getSelection().addListener("change", e => {
        const selectedItem = e.getTarget().toArray()[0];
        const data = {
          projectModel: this.__getProjectModel(selectedItem.getProjectUuid())
        };
        this.fireDataEvent("StartProject", data);
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

    __getProjectArray: function(prjList) {
      return new qx.data.Array(
        prjList
          .map(
            (p, i) => qx.data.marshal.Json.createModel({
              name: p.name,
              thumbnail: p.thumbnail,
              projectUuid: p.projectUuid,
              created: p.creationDate,
              collaborators: p.collaborators
            })
          )
      );
    }
  }
});
