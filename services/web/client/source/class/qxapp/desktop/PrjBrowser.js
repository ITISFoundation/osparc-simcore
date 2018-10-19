/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    let leftSpacer = new qx.ui.core.Spacer(150);
    let mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    let rightSpacer = new qx.ui.core.Spacer(150);

    this.add(leftSpacer);
    this.add(mainView, {
      flex: 1
    });
    this.add(rightSpacer);

    let controlsLayout = this.__createControls();

    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let myPrjsLabel = this.__mainViewCaption = new qx.ui.basic.Label(this.tr("My Projects")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    let userProjectList = this.__list = this.__createUserProjectList();

    let pubPrjsLabel = this.__mainViewCaption = new qx.ui.basic.Label(this.tr("Popular Projects")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    let publicProjectList = this.__list2 = this.__createPublicProjectList();

    mainView.add(new qx.ui.core.Spacer(null, 10));
    mainView.add(controlsLayout);
    mainView.add(new qx.ui.core.Spacer(null, 10));
    mainView.add(myPrjsLabel);
    mainView.add(userProjectList);
    mainView.add(new qx.ui.core.Spacer(null, 10));
    mainView.add(pubPrjsLabel);
    mainView.add(publicProjectList);
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

      return controlsLayout;
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
      let prjLst = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 10,
        height: 230
      });

      // controller
      let userPrjList = qxapp.data.Store.getInstance().getUserProjectList();
      let userPrjArray = this.__getProjectArray(userPrjList);
      let prjCtr = this.__controller = new qx.data.controller.List(userPrjArray, prjLst, "name");
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

      return prjLst;
    },

    __createPublicProjectList: function() {
      // layout
      let prjLst = new qx.ui.form.List();
      prjLst.set({
        orientation: "horizontal",
        spacing: 10,
        height: 230
      });

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

      return prjLst;
    },

    /**
     * Delegates appearance and binding of each project item
     */
    __setDelegate: function(projectController) {
      const thumbnailWidth = 246;
      const thumbnailHeight = 144;
      let delegate = {
        // Item's Layout
        createItem: function() {
          return new qxapp.desktop.PrjBrowserListItem();
        },
        // Item's data binding
        bindItem: function(controller, item, id) {
          controller.bindProperty("thumbnail", "icon", {
            converter: function(data) {
              let thumbnailUrl = data === null ? "https://placeimg.com/"+thumbnailWidth+"/"+thumbnailHeight+"/tech/grayscale/?random.jpg" : data;
              thumbnailUrl = thumbnailUrl.replace("https://placeimg.com/171/96/", "https://placeimg.com/"+thumbnailWidth+"/"+thumbnailHeight+"/");
              return thumbnailUrl;
            }
          }, item, id);
          controller.bindProperty("name", "prjTitle", {
            converter: function(data, model, source, target) {
              return "<b>" + data + "</b>";
            }
          }, item, id);
          controller.bindProperty("owner", "creator", {
            converter: function(data, model, source, target) {
              return "Created by: <b>" + data + "</b>";
            }
          }, item, id);
          controller.bindProperty("created", "created", {
            converter: function(data) {
              // FIXME
              // let date = new Date(data);
              // return new Date(data);
              return "Created on: " + data;
            }
          }, item, id);
        },
        configureItem : function(item) {
          item.set({
            paddingTop: 5,
            paddingBottom: 5
          });
          item.getChildControl("icon").set({
            width: thumbnailWidth,
            height: thumbnailHeight
          });
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
              owner: p.owner
            })
          )
      );
    }
  }
});
