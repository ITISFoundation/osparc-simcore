/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    this.__projectResources = qxapp.io.rest.ResourceFactory.getInstance().createProjectResources();
    // this._projectResources.projects
    // this._projectResources.project
    // this._projectResources.templates

    let leftSpacer = new qx.ui.core.Spacer(120);
    let mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    let scrollerMainView = new qx.ui.container.Scroll();
    scrollerMainView.add(mainView);
    let rightSpacer = new qx.ui.core.Spacer(120);

    this.add(leftSpacer);
    this.add(scrollerMainView, {
      flex: 1
    });
    this.add(rightSpacer);

    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let myPrjsLabel = new qx.ui.basic.Label(this.tr("My Projects")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    let userProjectList = this.__createUserProjectList();

    let pubPrjsLabel = new qx.ui.basic.Label(this.tr("Template Projects")).set({
      font: navBarLabelFont,
      minWidth: 150
    });
    let publicProjectList = this.__createPublicProjectList();

    let editPrjLayout = this.__editPrjLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    editPrjLayout.setMaxWidth(800);
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
      let resource = this.__projectResources.project;

      resource.addListenerOnce("getSuccess", e => {
        // TODO: is this listener added everytime we call ?? It does not depend on input params
        // but it needs to be here to implemenet startProjectModel
        let projectData = e.getRequest().getResponse().data;
        if (fromTemplate) {
          projectData = qxapp.utils.Utils.replaceTemplateUUIDs(projectData);
        }
        let model = new qxapp.data.model.ProjectModel(projectData);
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
          prjOwner: null
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

      this.reloadPublicProjects();

      return pblLst;
    },

    reloadPublicProjects: function() {
      // resources
      this.__publicProjectList.removeAll();

      let resources = this.__projectResources.templates;

      resources.addListenerOnce("getSuccess", e => {
        let publicPrjList = e.getRequest().getResponse().data;
        let publicFilteredPrjList = [];
        for (let i=0; i<publicPrjList.length; i++) {
          // Temporary HACK
          if (qxapp.data.Store.getInstance().getRole() !== 0 &&
          publicPrjList[i].projectUuid.includes("DemoDecember")) {
            continue;
          }
          publicFilteredPrjList.push(publicPrjList[i]);
        }

        let publicPrjArrayModel = this.__getProjectArrayModel(publicFilteredPrjList);
        // controller
        let prjCtr = new qx.data.controller.List(publicPrjArrayModel, this.__publicProjectList, "name");
        const fromTemplate = true;
        let delegate = this.__getDelegate(fromTemplate);
        prjCtr.setDelegate(delegate);
      }, this);

      resources.addListener("getError", e => {
        console.log(e);
      }, this);

      resources.get();

      this.__itemSelected(null);
    },

    __cretePrjListLayout: function() {
      let list = new qx.ui.form.List().set({
        orientation: "horizontal",
        spacing: 10,
        height: 200,
        alignY: "middle",
        appearance: "pb-list"
      });
      return list;
    },

    /**
     * Delegates appearance and binding of each project item
     */
    __getDelegate: function(fromTemplate) {
      const thumbnailWidth = 200;
      const thumbnailHeight = 120;
      const nThumbnails = 25;
      let thumbnailCounter = 0;
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
              let thumbnailId = thumbnailCounter + (fromTemplate ? 10 : 0);
              if (thumbnailId >= nThumbnails) {
                thumbnailId -= nThumbnails;
              }
              let thumbnailUrl = data.match(/^@/) ? data : "qxapp/img"+ thumbnailId +".jpg";
              thumbnailCounter++;
              return thumbnailUrl;
            }
          }, item, id);
          controller.bindProperty("name", "prjTitle", {
            converter: function(data, model, source, target) {
              return "<b>" + data + "</b>";
            }
          }, item, id);
          controller.bindProperty("prjOwner", "creator", {
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
      saveButton.setMinWidth(70);
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
      cancelButton.setMinWidth(70);
      cancelButton.addListener("execute", e => {
        this.__itemSelected(null);
      }, this);
      form.addButton(cancelButton);

      let deleteButton = new qx.ui.form.Button(this.tr("Delete"));
      deleteButton.setMinWidth(70);
      deleteButton.setEnabled(!fromTemplate);
      deleteButton.addListener("execute", e => {
        let win = this.__createConfirmWindow();
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win["value"] === 1) {
            let resource = this.__projectResources.project;

            resource.addListenerOnce("delSuccess", ev => {
              this.reloadUserProjects();
            }, this);

            resource.del({
              "project_id": projectData["projectUuid"]
            });

            this.__itemSelected(null);
          }
        }, this);
      }, this);
      form.addButton(deleteButton);

      this.__editPrjLayout.add(new qx.ui.form.renderer.Single(form));
    },

    __createConfirmWindow: function() {
      let win = new qx.ui.window.Window("Confirmation").set({
        layout: new qx.ui.layout.VBox(10),
        width: 300,
        height: 60,
        modal: true,
        showMaximize: false,
        showMinimize: false,
        showClose: false,
        autoDestroy: false
      });

      let text = new qx.ui.basic.Label(this.tr("Are you sure you want to delete the project?"));
      win.add(text);

      let buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(10, "right"));
      var btnNo = new qx.ui.form.Button("No");
      var btnYes = new qx.ui.form.Button("Yes");
      btnNo.addListener("execute", e => {
        win["value"] = 0;
        win.close(0);
      }, this);
      btnYes.addListener("execute", e => {
        win["value"] = 1;
        win.close(1);
      }, this);
      buttons.add(btnNo);
      buttons.add(btnYes);
      win.add(buttons);

      return win;
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
              prjOwner: Object.prototype.hasOwnProperty.call(p, "owner") ? p.owner : p.prjOwner
            })
          )
      );
    }
  }
});
