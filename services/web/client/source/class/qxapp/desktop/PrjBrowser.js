/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    this.__projectResources = qxapp.io.rest.ResourceFactory.getInstance().createProjectResources();
    // this._projectResources.projects
    // this._projectResources.project
    // this._projectResources.templates

    let leftSpacer = new qx.ui.core.Spacer(150);
    let mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    let rightSpacer = new qx.ui.core.Spacer(150);

    this.add(leftSpacer);
    this.add(mainView, {
      flex: 1
    });
    this.add(rightSpacer);

    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let myPrjsLabel = new qx.ui.basic.Label(this.tr("My Projects")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    let userProjectList = this.__createUserProjectList();

    let pubPrjsLabel = new qx.ui.basic.Label(this.tr("Popular Projects")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    let publicProjectList = this.__createPublicProjectList();


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
    __projectResources: null,

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
      let blankProject = new qxapp.data.model.ProjectModel();
      blankProject.set({
        name: newPrj.name,
        description: newPrj.description
      });
      const data = {
        projectModel: blankProject
      };
      this.fireDataEvent("StartProject", data);
    },

    __startProjectModel: function(projectId, fromTemplate = false) {
      // let projectData = qxapp.data.Store.getInstance().getProjectData(projectId);
      let resource = this.__projectResources.project;

      resource.addListenerOnce("getSuccess", function(e) {
        // TODO: is this listener added everytime we call ?? It does not depend on input params
        // but it needs to be here to implemenet startProjectModel
        let projectData = e.getRequest().getResponse().data;
        let model = new qxapp.data.model.ProjectModel(projectData, fromTemplate);
        const data = {
          projectModel: model
        };
        this.fireDataEvent("StartProject", data);
      }, this);

      resource.addListenerOnce("getError", e => {
        console.log(e);
      });

      resource.get({
        "project_id": projectId
      });
    },

    __createUserProjectList: function() {
      // layout
      let prjLst = this.__cretePrjListLayout();

      // resources
      // let userPrjList = qxapp.data.Store.getInstance().getUserProjectList();
      let resources = this.__projectResources.projects;

      resources.addListener("getSuccess", e => {
        let userPrjList = e.getRequest().getResponse().data;
        let userPrjArrayModel = this.__getProjectArrayModel(userPrjList);
        userPrjArrayModel.unshift(qx.data.marshal.Json.createModel({
          name: this.tr("New Project"),
          thumbnail: "@FontAwesome5Solid/plus-circle/80",
          projectUuid: null,
          created: null,
          owner: null
        }));
        // controller
        let prjCtr = new qx.data.controller.List(userPrjArrayModel, prjLst, "name");
        const fromTemplate = false;
        let delegate = this.__getDelegate(fromTemplate);
        prjCtr.setDelegate(delegate);
      }, this);

      resources.addListener("getError", e => {
        console.log(e);
      }, this);

      resources.get();

      return prjLst;
    },

    __createPublicProjectList: function() {
      // layout
      let prjLst = this.__cretePrjListLayout();

      // controller
      let publicPrjList = qxapp.data.Store.getInstance().getPublicProjectList();
      let publicPrjArrayModel = this.__getProjectArrayModel(publicPrjList);
      let prjCtr = new qx.data.controller.List(publicPrjArrayModel, prjLst, "name");
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
      let delegate = {
        // Item's Layout
        createItem: function() {
          let item = new qxapp.desktop.PrjBrowserListItem();
          item.addListener("dbltap", e => {
            const prjUuid = item.getModel();
            if (prjUuid) {
              that.__startProjectModel(prjUuid, fromTemplate); // eslint-disable-line no-underscore-dangle
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
              created: new Date(p.creationDate),
              owner: p.owner
            })
          )
      );
    }
  }
});
