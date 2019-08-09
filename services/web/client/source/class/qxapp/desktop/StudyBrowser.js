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
 * Widget that shows two lists of studies and study editor form:
 * - List1: User's studies (StudyBrowserListItem)
 * - List2: Template studies to start from (StudyBrowserListItem)
 * - Form: Extra editable information of the selected study
 *
 * It is the entry point to start editing or creatina new study.
 *
 * Also takes care of retrieveing the list of services and pushing the changes in the metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let prjBrowser = this.__serviceBrowser = new qxapp.desktop.StudyBrowser();
 *   this.getRoot().add(prjBrowser);
 * </pre>
 */

qx.Class.define("qxapp.desktop.StudyBrowser", {
  extend: qx.ui.core.Widget,

  construct: function(loadStudyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__studyResources = qxapp.io.rest.ResourceFactory.getInstance().createStudyResources();

    this.__studiesPane = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    this.__editPane = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
      appearance: "sidepanel",
      width: 570,
      visibility: "excluded",
      padding: [0, 15]
    });
    this._addAt(this.__studiesPane, 0, {
      flex: 1
    });
    this._addAt(this.__editPane, 1);

    let iframe = qxapp.utils.Utils.createLoadingIFrame(this.tr("Studies"));
    this.__studiesPane.add(iframe, {
      flex: 1
    });

    const interval = 500;
    let userTimer = new qx.event.Timer(interval);
    userTimer.addListener("interval", () => {
      if (this.__userReady) {
        userTimer.stop();
        this.__studiesPane.removeAll();
        this.__editPane.removeAll();
        iframe.dispose();
        this.__createStudiesLayout();
        this.__createCommandEvents();
        if (loadStudyId) {
          let resource = this.__studyResources.project;
          resource.addListenerOnce("getSuccess", e => {
            const studyData = e.getRequest().getResponse().data;
            this.__startStudy(studyData);
          }, this);
          resource.addListener("getError", ev => {
            if (qxapp.data.Permissions.getInstance().getRole() === "Guest") {
              // If guest fails to load study, log him out
              qxapp.auth.Manager.getInstance().logout();
            }
            console.error(ev);
          });
          resource.get({
            "project_id": loadStudyId
          });
        }
      }
    }, this);
    userTimer.start();

    this.__initResources();
  },

  events: {
    "startStudy": "qx.event.type.Data"
  },

  members: {
    __userReady: null,
    __servicesReady: null,
    __studyResources: null,
    __userStudyContainer: null,
    __templateStudyContainer: null,
    __editStudyLayout: null,
    __studyData: null,
    __creatingNewStudy: null,
    __studiesPane: null,
    __editPane: null,
    __sidePanel: null,
    __userStudies: null,
    __templateStudies: null,
    __templateDeleteButton: null,
    __studiesDeleteButton: null,

    __initResources: function() {
      this.__getUserProfile();
      this.__getServicesPreload();
    },

    __getUserProfile: function() {
      let permissions = qxapp.data.Permissions.getInstance();
      permissions.addListener("userProfileRecieved", e => {
        this.__userReady = e.getData();
      }, this);
      permissions.loadUserRoleFromBackend();
    },

    __getServicesPreload: function() {
      let store = qxapp.data.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    },

    __createStudiesLayout: function() {
      const newStudyBtn = new qx.ui.form.Button(this.tr("Create new study"), "@FontAwesome5Solid/plus-circle/18").set({
        appearance: "big-button",
        allowGrowX: false,
        width: 210
      });
      newStudyBtn.addListener("execute", () => this.__createStudyBtnClkd());

      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      const studiesTitleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const studiesDeleteButton = this.__studiesDeleteButton = this.__createDeleteButton();
      const myStudyLabel = new qx.ui.basic.Label(this.tr("My studies")).set({
        font: navBarLabelFont
      });
      studiesTitleContainer.add(myStudyLabel);
      studiesTitleContainer.add(studiesDeleteButton);
      let userStudyList = this.__userStudyContainer = this.__createUserStudyList();
      let userStudyLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        marginTop: 20
      });
      userStudyLayout.add(studiesTitleContainer);
      userStudyLayout.add(newStudyBtn);
      userStudyLayout.add(userStudyList);

      const templateTitleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const templateDeleteButton = this.__templateDeleteButton = this.__createDeleteButton();
      const tempStudyLabel = new qx.ui.basic.Label(this.tr("Template Studies")).set({
        font: navBarLabelFont
      });
      templateTitleContainer.add(tempStudyLabel);
      templateTitleContainer.add(templateDeleteButton);
      let tempStudyList = this.__templateStudyContainer = this.__createTemplateStudyList();
      let tempStudyLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        marginTop: 20
      });
      tempStudyLayout.add(templateTitleContainer);
      tempStudyLayout.add(tempStudyList);

      this.__editStudyLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      this.__studiesPane.add(userStudyLayout);
      this.__studiesPane.add(tempStudyLayout);
      this.__editPane.add(this.__editStudyLayout);
    },

    __createDeleteButton: function() {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        visibility: "excluded"
      });
      deleteButton.addListener("execute", e => {
        const isTemplate = this.__templateDeleteButton === thisButton;
        const selection = isTemplate ? this.__templateStudyContainer.getSelection() : this.__userStudyContainer.getSelection();
        const win = this.__createConfirmWindow(selection.length > 1);
        const thisButton = e.getTarget();
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win["value"] === 1) {
            this.__deleteStudy(selection.map(button => this.__getStudyData(button.getUuid(), isTemplate)), isTemplate);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __createCommandEvents: function() {
      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.__itemSelected(null);
      });
    },

    __createStudyBtnClkd: function(templateData) {
      if (this.__creatingNewStudy) {
        return;
      }
      this.__creatingNewStudy = true;

      const win = new qx.ui.window.Window(this.tr("Create New Study")).set({
        layout: new qx.ui.layout.Grow(),
        contentPadding: 0,
        showMinimize: false,
        showMaximize: false,
        minWidth: 500,
        centerOnAppear: true,
        autoDestroy: true,
        modal: true,
        appearance: "service-window"
      });

      const newStudyDlg = new qxapp.component.widget.NewStudyDlg(templateData);
      newStudyDlg.addListenerOnce("createStudy", e => {
        const minStudyData = qxapp.data.model.Study.createMinimumStudyObject();
        const data = e.getData();
        minStudyData["name"] = data.prjTitle;
        minStudyData["description"] = data.prjDescription;
        this.__createStudy(minStudyData, data.prjTemplateId);
        win.close();
      }, this);
      win.add(newStudyDlg);
      win.open();
      win.addListener("close", () => {
        this.__creatingNewStudy = false;
      }, this);
    },

    __createStudy: function(minStudyData, templateId) {
      const resources = this.__studyResources.projects;

      if (templateId) {
        resources.addListenerOnce("postFromTemplateSuccess", e => {
          const studyData = e.getRequest().getResponse().data;
          this.__startStudy(studyData);
        }, this);
        resources.addListenerOnce("postFromTemplateError", e => {
          console.error(e);
        });
        resources.postFromTemplate({
          "template_id": templateId
        }, minStudyData);
      } else {
        resources.addListenerOnce("postSuccess", e => {
          const studyData = e.getRequest().getResponse().data;
          this.__startStudy(studyData);
        }, this);
        resources.addListenerOnce("postError", e => {
          console.error(e);
        });
        resources.post(null, minStudyData);
      }
    },

    __startStudy: function(studyData) {
      if (this.__servicesReady === null) {
        this.__showChildren(false);
        let iframe = qxapp.utils.Utils.createLoadingIFrame(this.tr("Services"));
        this._add(iframe, {
          flex: 1
        });

        const interval = 500;
        let servicesTimer = new qx.event.Timer(interval);
        servicesTimer.addListener("interval", () => {
          if (this.__servicesReady) {
            servicesTimer.stop();
            this._remove(iframe);
            iframe.dispose();
            this.__showChildren(true);
            this.__loadStudy(studyData);
          }
        }, this);
        servicesTimer.start();
      } else {
        this.__loadStudy(studyData);
      }
    },

    __loadStudy: function(studyData) {
      let study = new qxapp.data.model.Study(studyData);
      let studyEditor = new qxapp.desktop.StudyEditor(study);
      this.fireDataEvent("startStudy", studyEditor);
    },

    __showChildren: function(show) {
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        if (show) {
          children[i].setVisibility("visible");
        } else {
          children[i].setVisibility("excluded");
        }
      }
    },

    __createUserStudyList: function() {
      const usrLst = this.__userStudyContainer = this.__createStudyListLayout();
      this.reloadUserStudies();
      return usrLst;
    },

    reloadUserStudies: function() {
      this.__userStudyContainer.removeAll();

      const resources = this.__studyResources.projects;

      resources.addListenerOnce("getSuccess", e => {
        let userStudyList = e.getRequest().getResponse().data;
        this.__setStudyList(userStudyList);
      }, this);

      resources.addListener("getError", e => {
        console.error(e);
      }, this);

      if (qxapp.data.Permissions.getInstance().canDo("studies.user.read")) {
        resources.get();
      } else {
        this.__setStudyList([]);
      }
    },

    __createTemplateStudyList: function() {
      let tempList = this.__templateStudyContainer = this.__createStudyListLayout();
      this.reloadTemplateStudies();
      return tempList;
    },

    reloadTemplateStudies: function() {
      this.__templateStudyContainer.removeAll();

      const resources = this.__studyResources.templates;

      resources.addListenerOnce("getSuccess", e => {
        const tempStudyList = e.getRequest().getResponse().data;
        const tempFilteredStudyList = [];
        for (let i=0; i<tempStudyList.length; i++) {
          // FIXME: Backend should do the filtering
          if (tempStudyList[i].uuid.includes("DemoDecember") &&
          !qxapp.data.Permissions.getInstance().canDo("services.all.read")) {
            continue;
          }
          tempFilteredStudyList.push(tempStudyList[i]);
        }
        this.__setTemplateList(tempFilteredStudyList);
      }, this);

      resources.addListener("getError", e => {
        console.error(e);
      }, this);

      if (qxapp.data.Permissions.getInstance().canDo("studies.templates.read")) {
        resources.get();
      } else {
        this.__setTemplateList([]);
      }
    },

    __setStudyList: function(userStudyList) {
      this.__userStudies = userStudyList;
      for (let i=0; i<userStudyList.length; i++) {
        this.__userStudyContainer.add(this.__createStudyItem(userStudyList[i], false));
      }
    },

    __setTemplateList: function(tempStudyList) {
      this.__templateStudies = tempStudyList;
      for (let i=0; i<tempStudyList.length; i++) {
        this.__templateStudyContainer.add(this.__createStudyItem(tempStudyList[i], true));
      }
    },

    __createStudyListLayout: function() {
      return new qxapp.component.form.ToggleButtonContainer(new qx.ui.layout.Flow(8, 8));
    },

    __createStudyItem: function(study, isTemplate) {
      const item = new qxapp.desktop.StudyBrowserListItem();

      item.setUuid(study.uuid);
      item.setPrjTitle(study.name);
      item.setIcon(study.thumbnail ? study.thumbnail : qxapp.utils.Utils.getThumbnailFromUuid(study.uuid));
      item.setCreator(study.prjOwner ? "Created by: <b>" + study.prjOwner + "</b>" : null);
      item.setLastChangeDate(study.lastChangeDate ? new Date(study.lastChangeDate) : null);

      item.addListener("dbltap", e => {
        const studyData = this.__getStudyData(item.getUuid(), isTemplate);
        if (isTemplate) {
          this.__createStudyBtnClkd(studyData);
        } else {
          this.__startStudy(studyData);
        }
      });

      item.addListener("execute", e => {
        // Selection logic
        if (item.getValue()) {
          if (isTemplate) {
            this.__userStudyContainer.resetSelection();
            this.__templateStudyContainer.selectOne(item);
          } else {
            this.__templateStudyContainer.resetSelection();
          }
          this.__itemSelected(item.getUuid(), isTemplate);
        } else if (isTemplate) {
          this.__itemSelected(null);
          this.__templateDeleteButton.exclude();
        } else {
          const selection = this.__userStudyContainer.getSelection();
          if (selection.length) {
            this.__itemSelected(selection[0].getUuid());
          } else {
            this.__studiesDeleteButton.exclude();
            this.__itemSelected(null);
          }
        }
      }, this);

      return item;
    },

    __getStudyData: function(id, isTemplate) {
      const matchesId = study => study.uuid === id;
      return isTemplate ? this.__templateStudies.find(matchesId) : this.__userStudies.find(matchesId);
    },

    __itemSelected: function(studyId, fromTemplate = false) {
      if (studyId === null) {
        if (this.__userStudyContainer) {
          this.__userStudyContainer.resetSelection();
        }
        if (this.__templateStudyContainer) {
          this.__templateStudyContainer.resetSelection();
        }
        if (this.__editStudyLayout) {
          this.__editPane.exclude();
        }
        if (this.__studiesDeleteButton) {
          this.__studiesDeleteButton.exclude();
        }
        if (this.__templateDeleteButton) {
          this.__templateDeleteButton.exclude();
        }
        return;
      }
      const studyData = this.__getStudyData(studyId, fromTemplate);
      this.__createForm(studyData, fromTemplate);
      this.__editPane.setVisibility("visible");
    },

    __createForm: function(studyData, isTemplate) {
      this.__editStudyLayout.removeAll();
      const studyDetails = new qxapp.component.widget.StudyDetails(studyData, isTemplate);
      studyDetails.addListener("closed", () => this.__itemSelected(null), this);
      studyDetails.addListener("updatedStudy", study => this.reloadUserStudies(), this);
      studyDetails.addListener("updatedTemplate", template => this.reloadTemplateStudies(), this);
      studyDetails.addListener("openedStudy", () => {
        if (isTemplate) {
          this.__createStudyBtnClkd(studyData);
        } else {
          this.__startStudy(studyData);
        }
      }, this);

      this.__editStudyLayout.add(studyDetails);

      this.__updateDeleteButtons(studyData, isTemplate);
    },

    __updateDeleteButtons: function(studyData, isTemplate) {
      const canDeleteTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.delete");
      const isCurrentUserOwner = studyData.prjOwner === qxapp.data.Permissions.getInstance().getLogin();
      let deleteButton = this.__studiesDeleteButton;
      if (isTemplate) {
        this.__studiesDeleteButton.exclude();
        deleteButton = this.__templateDeleteButton;
      } else {
        this.__templateDeleteButton.exclude();
        this.__studiesDeleteButton.setLabel(this.__userStudyContainer.getSelection().length > 1 ? this.tr("Delete selected") : this.tr("Delete"));
      }
      deleteButton.show();
      deleteButton.setEnabled(isCurrentUserOwner && (!isTemplate || canDeleteTemplate));
    },

    __deleteStudy: function(studyData, isTemplate = false) {
      this.__stopInteractiveServicesInStudy(studyData);

      let resource = this.__studyResources.project;

      resource.addListenerOnce("delSuccess", ev => {
        if (isTemplate) {
          this.reloadTemplateStudies();
        } else {
          this.reloadUserStudies();
        }
      }, this);

      studyData.forEach(study => {
        resource.del({
          "project_id": study.uuid
        });
      });

      this.__itemSelected(null);
    },

    __stopInteractiveServicesInStudy: function(studies) {
      const store = qxapp.data.Store.getInstance();
      studies.forEach(studyData => {
        for (const [nodeId, nodedata] of Object.entries(studyData["workbench"])) {
          const metadata = store.getNodeMetaData(nodedata.key, nodedata.version);
          if (qxapp.data.model.Node.isDynamic(metadata) && qxapp.data.model.Node.isRealService(metadata)) {
            store.stopInteractiveService(nodeId);
          }
        }
      });
    },

    __createConfirmWindow: function(isMulti) {
      let win = new qx.ui.window.Window("Confirmation").set({
        layout: new qx.ui.layout.VBox(10),
        width: 300,
        height: 60,
        modal: true,
        showMaximize: false,
        showMinimize: false,
        showClose: false,
        autoDestroy: false,
        appearance: "service-window"
      });

      const message = `Are you sure you want to delete the ${isMulti ? "studies" : "study"}?`;
      const text = new qx.ui.basic.Label(this.tr(message));
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

    __getStudyArrayModel: function(studyList) {
      let sortByProperty = function(prop) {
        return function(a, b) {
          if (prop === "lastChangeDate") {
            return new Date(b[prop]) - new Date(a[prop]);
          }
          if (typeof a[prop] == "number") {
            return a[prop] - b[prop];
          }
          if (a[prop] < b[prop]) {
            return -1;
          } else if (a[prop] > b[prop]) {
            return 1;
          }
          return 0;
        };
      };
      studyList.sort(sortByProperty("lastChangeDate"));

      let studyArray = new qx.data.Array(
        studyList
          .map(
            (p, i) => qx.data.marshal.Json.createModel({
              name: p.name,
              thumbnail: p.thumbnail,
              uuid: p.uuid,
              lastChangeDate: new Date(p.lastChangeDate),
              prjOwner: p.prjOwner
            })
          )
      );
      return studyArray;
    }
  }
});
