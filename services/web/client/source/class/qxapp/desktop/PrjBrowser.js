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

    let editPrjLayout = this.__editPrjLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    let editPrjLabel = new qx.ui.basic.Label(this.tr("Edit Project")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    editPrjLayout.add(editPrjLabel);
    editPrjLayout.setVisibility("excluded");


    mainView.add(new qx.ui.core.Spacer(null, 5));
    mainView.add(myPrjsLabel);
    mainView.add(userProjectList);
    mainView.add(new qx.ui.core.Spacer(null, 5));
    mainView.add(pubPrjsLabel);
    mainView.add(publicProjectList);
    mainView.add(new qx.ui.core.Spacer(null, 5));
    mainView.add(this.__editPrjLayout);

    let commandEsc = new qx.ui.command.Command("Esc");
    commandEsc.addListener("execute", e => {
      this.__itemSelected(null);
    });
  },

  events: {
    "StartProject": "qx.event.type.Data"
  },

  members: {
    __projectResources: null,
    __userProjectList: null,
    __publicProjectList: null,
    __editPrjLayout: null,

    __newPrjBtnClkd: function() {
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

      resource.addListenerOnce("getSuccess", e => {
        // TODO: is this listener added everytime we call ?? It does not depend on input params
        // but it needs to be here to implemenet startProjectModel
        let projectData = e.getRequest().getResponse().data;
        let model = new qxapp.data.model.ProjectModel(projectData, fromTemplate);
        const data = {
          projectModel: model
        };
        this.fireDataEvent("StartProject", data);
      }, this);

      resource.addListener("getError", e => {
        console.log(e);
      });

      resource.get({
        "project_id": projectId
      });
    },

    __createUserProjectList: function() {
      // layout
      let usrLst = this.__userProjectList = this.__cretePrjListLayout();
      usrLst.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          this.__publicProjectList.resetSelection();
          const selectedId = e.getData()[0].getModel();
          if (selectedId) {
            this.__itemSelected(selectedId, false);
          } else {
            // "New Project" selected
            this.__itemSelected(null);
          }
        }
      }, this);

      this.reloadUserProjects();

      return usrLst;
    },

    reloadUserProjects: function() {
      // resources
      // let userPrjList = qxapp.data.Store.getInstance().getUserProjectList();
      this.__userProjectList.removeAll();

      let resources = this.__projectResources.projects;

      resources.addListenerOnce("getSuccess", e => {
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
        let prjCtr = new qx.data.controller.List(userPrjArrayModel, this.__userProjectList, "name");
        const fromTemplate = false;
        let delegate = this.__getDelegate(fromTemplate);
        prjCtr.setDelegate(delegate);
      }, this);

      resources.addListener("getError", e => {
        console.log(e);
      }, this);

      resources.get();

      this.__itemSelected(null);
    },

    __createPublicProjectList: function() {
      // layout
      let pblLst = this.__publicProjectList = this.__cretePrjListLayout();
      pblLst.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          this.__userProjectList.resetSelection();
          const selectedId = e.getData()[0].getModel();
          this.__itemSelected(selectedId, true);
        }
      }, this);

      // controller
      let publicPrjList = qxapp.data.Store.getInstance().getPublicProjectList();
      let publicPrjArrayModel = this.__getProjectArrayModel(publicPrjList);
      let prjCtr = new qx.data.controller.List(publicPrjArrayModel, pblLst, "name");
      const fromTemplate = true;
      let delegate = this.__getDelegate(fromTemplate);
      prjCtr.setDelegate(delegate);
      return pblLst;
    },

    __cretePrjListLayout: function() {
      let list = new qx.ui.form.List().set({
        orientation: "horizontal",
        spacing: 10,
        height: 225,
        alignY: "middle",
        appearance: "pb-list"
      });
      return list;
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
              that.__newPrjBtnClkd(); // eslint-disable-line no-underscore-dangle
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

    __itemSelected: function(projectId, fromTemplate = false) {
      if (projectId === null) {
        if (this.__userProjectList) {
          this.__userProjectList.resetSelection();
        }
        if (this.__publicProjectList) {
          this.__publicProjectList.resetSelection();
        }
        if (this.__editPrjLayout) {
          this.__editPrjLayout.setVisibility("excluded");
        }
        return;
      }

      let resource = this.__projectResources.project;

      resource.addListenerOnce("getSuccess", e => {
        this.__editPrjLayout.setVisibility("visible");
        let projectData = e.getRequest().getResponse().data;
        this.__createForm(projectData, fromTemplate);
        console.log(projectData);
      }, this);

      resource.addListener("getError", e => {
        console.log(e);
      });

      resource.get({
        "project_id": projectId
      });
    },

    __createForm: function(projectData, fromTemplate) {
      while (this.__editPrjLayout.getChildren().length > 1) {
        this.__editPrjLayout.removeAt(1);
      }

      const itemsToBeDisplayed = ["name", "description", "notes", "owner", "collaborators", "creationDate", "lastChangeDate"];
      const itemsToBeModified = fromTemplate ? [] : ["name", "description", "notes"];
      let form = new qx.ui.form.Form();
      let control;
      for (const dataId in projectData) {
        if (itemsToBeDisplayed.includes(dataId)) {
          switch (dataId) {
            case "name":
              control = new qx.ui.form.TextField();
              form.add(control, this.tr("Name"));
              break;
            case "description":
              control = new qx.ui.form.TextField();
              form.add(control, this.tr("Description"));
              break;
            case "notes":
              control = new qx.ui.form.TextArea().set({
                minimalLineHeight: 2
              });
              form.add(control, this.tr("Notes"));
              break;
            case "owner":
              control = new qx.ui.form.TextField();
              form.add(control, this.tr("Owner"));
              break;
            case "collaborators":
              control = new qx.ui.form.TextField();
              form.add(control, this.tr("Collaborators"));
              break;
            case "creationDate":
              control = new qx.ui.form.TextField();
              form.add(control, this.tr("Creation Date"));
              break;
            case "lastChangeDate":
              control = new qx.ui.form.TextField();
              form.add(control, this.tr("Last Change Date"));
              break;
          }
          let value = projectData[dataId];
          if (typeof value === "object") {
            if (value === null) {
              value = "";
            } else {
              value = Object.keys(value).join(", ");
            }
          }
          control.set({
            value: value
          });
          control.setEnabled(itemsToBeModified.includes(dataId));
        }
      }

      let controller = new qx.data.controller.Form(null, form);
      let model = controller.createModel();

      // buttons
      let saveButton = new qx.ui.form.Button(this.tr("Save"));
      saveButton.setMaxWidth(70);
      saveButton.setEnabled(!fromTemplate);
      saveButton.addListener("execute", e => {
        for (let i=0; i<itemsToBeModified.length; i++) {
          const key = itemsToBeModified[i];
          let getter = "get" + qx.lang.String.firstUp(key);
          let newVal = model[getter]();
          projectData[key] = newVal;
        }
        let resource = this.__projectResources.project;

        resource.addListenerOnce("putSuccess", ev => {
          this.reloadUserProjects();
        }, this);

        resource.put({
          "project_id": projectData["projectUuid"]
        }, projectData);

        this.__itemSelected(null);
      }, this);
      form.addButton(saveButton);

      let cancelButton = new qx.ui.form.Button(this.tr("Cancel"));
      cancelButton.setMaxWidth(70);
      cancelButton.addListener("execute", e => {
        this.__itemSelected(null);
      }, this);
      form.addButton(cancelButton);

      let deleteButton = new qx.ui.form.Button(this.tr("Delete"));
      deleteButton.setMaxWidth(70);
      deleteButton.setEnabled(!fromTemplate);
      deleteButton.addListener("execute", e => {
        let resource = this.__projectResources.project;

        resource.addListenerOnce("delSuccess", ev => {
          this.reloadUserProjects();
        }, this);

        resource.del({
          "project_id": projectData["projectUuid"]
        });

        this.__itemSelected(null);
      }, this);
      form.addButton(deleteButton);

      this.__editPrjLayout.add(new qx.ui.form.renderer.Single(form));
      this.__editPrjLayout.add(saveButton);
      this.__editPrjLayout.add(cancelButton);
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
