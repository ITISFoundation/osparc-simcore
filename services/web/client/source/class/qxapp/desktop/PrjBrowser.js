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

    newPrjBtnClkd: function() {
      let win = new qx.ui.window.Window(this.tr("Create New Project")).set({
        layout: new qx.ui.layout.Grow(),
        contentPadding: 0,
        showMinimize: false,
        showMaximize: false,
        minWidth: 500,
        centerOnAppear: true,
        autoDestroy: true
      });

      let newProjectDlg = new qxapp.component.widget.NewProjectDlg();
      newProjectDlg.addListenerOnce("CreatePrj", e => {
        const data = e.getData();
        const newPrj = {
          name: data.prjTitle,
          description: data.prjDescription
        };
        this.__startBlankProject(newPrj);
        win.close();
      }, this);
      win.add(newProjectDlg);
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

    __getProjectModel: function(projectId, fromTemplate = false) {
      let project = new qxapp.data.model.ProjectModel();
      if (projectId) {
        let projectData = qxapp.data.Store.getInstance().getProjectData(projectId);
        project = new qxapp.data.model.ProjectModel(projectData, fromTemplate);
      }
      return project;
    },

    __createUserProjectList: function() {
      // layout
      let prjLst = this.__cretePrjListLayout();

      // controller
      let userPrjList = qxapp.data.Store.getInstance().getUserProjectList();
      let userPrjArrayModel = this.__getProjectArrayModel(userPrjList);
      userPrjArrayModel.unshift(qx.data.marshal.Json.createModel({
        name: this.tr("New Project"),
        thumbnail: "@FontAwesome5Solid/plus-circle/80",
        projectUuid: null,
        created: null,
        owner: null
      }));
      let prjCtr = this.__controller = new qx.data.controller.List(userPrjArrayModel, prjLst, "name");
      const fromTemplate = false;
      let delegate = this.__getDelegate(fromTemplate);
      prjCtr.setDelegate(delegate);
      return prjLst;
    },

    __createPublicProjectList: function() {
      // layout
      let prjLst = this.__cretePrjListLayout();

      // controller
      let publicPrjList = qxapp.data.Store.getInstance().getPublicProjectList();
      let publicPrjArrayModel = this.__getProjectArrayModel(publicPrjList);
      let prjCtr = this.__controller2 = new qx.data.controller.List(publicPrjArrayModel, prjLst, "name");
      const fromTemplate = true;
      let delegate = this.__getDelegate(fromTemplate);
      prjCtr.setDelegate(delegate);
      return prjLst;
    },

    __cretePrjListLayout: function() {
      return new qx.ui.form.List().set({
        orientation: "horizontal",
        spacing: 10,
        height: 245,
        alignY: "middle",
        appearance: "pb-list"
      });
    },

    /**
     * Delegates appearance and binding of each project item
     */
    __getDelegate: function(fromTemplate) {
      const thumbnailWidth = 246;
      const thumbnailHeight = 144;
      let that = this;
      let getProjectModel = this.__getProjectModel;
      let delegate = {
        // Item's Layout
        createItem: function() {
          let item = new qxapp.desktop.PrjBrowserListItem();
          item.addListener("dbltap", e => {
            const prjUuid = item.getModel();
            if (prjUuid) {
              let projectModel = getProjectModel(prjUuid, fromTemplate);
              const data = {
                projectModel: projectModel
              };
              that.fireDataEvent("StartProject", data);
            } else {
              that.newPrjBtnClkd();
            }
          });
          return item;
        },
        // Item's data binding
        bindItem: function(controller, item, id) {
          controller.bindProperty("thumbnail", "icon", {
            converter: function(data) {
              const nThumbnails = 5;
              let thumbnailUrl = data.match(/^@/) ? data : "qxapp/thumbnail"+ (Math.floor(Math.random()*nThumbnails)) +".png";
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
              return data ? "Created by: <b>" + data + "</b>" : null;
            }
          }, item, id);
          controller.bindProperty("created", "created", {
            converter: function(data) {
              return data ? new Date(data) : null;
            }
          }, item, id);
          controller.bindProperty("projectUuid", "model", {
            converter: function(data) {
              return data;
            }
          }, item, id);
        },
        configureItem : function(item) {
          item.getChildControl("icon").set({
            width: thumbnailWidth,
            height: thumbnailHeight,
            scale: true
          });
        }
      };

      return delegate;
    },

    __getProjectArrayModel: function(prjList) {
      return new qx.data.Array(
        prjList
          .map(
            (p, i) => qx.data.marshal.Json.createModel({
              name: p.name,
              thumbnail: p.thumbnail,
              projectUuid: p.projectUuid,
              created: Date(p.creationDate),
              owner: p.owner
            })
          )
      );
    }
  }
});
