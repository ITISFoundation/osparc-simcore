/* ************************************************************************

   osparc - the simcore frontend

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
 *   let prjBrowser = this.__serviceBrowser = new osparc.desktop.StudyBrowser();
 *   this.getRoot().add(prjBrowser);
 * </pre>
 */

qx.Class.define("osparc.desktop.StudyBrowser", {
  extend: qx.ui.core.Widget,

  construct: function(loadStudyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__studiesPane = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    this.__editPane = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
      appearance: "sidepanel",
      width: 570,
      allowGrowX: false,
      visibility: "excluded",
      padding: [0, 15]
    });
    const scroll1 = new qx.ui.container.Scroll();
    scroll1.add(this.__studiesPane);
    this._add(scroll1, {
      flex: 1
    });
    const scroll2 = new qx.ui.container.Scroll();
    scroll2.add(this.__editPane);
    this._add(scroll2);

    let iframe = osparc.utils.Utils.createLoadingIFrame(this.tr("Studies"));
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
        this.__attachEventHandlers();
        if (loadStudyId) {
          const params = {
            url: {
              "project_id": loadStudyId
            }
          };
          osparc.data.Resources.getOne("studies", params, loadStudyId)
            .then(studyData => {
              this.__startStudy(studyData);
            })
            .catch(err => {
              if (osparc.data.Permissions.getInstance().getRole() === "Guest") {
                // If guest fails to load study, log him out
                osparc.auth.Manager.getInstance().logout();
              }
              console.error(err);
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

  statics: {
    sortStudyList: function(studyList) {
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
    }
  },

  members: {
    __userReady: null,
    __servicesReady: null,
    __studyFilters: null,
    __userStudyContainer: null,
    __templateStudyContainer: null,
    __editStudyLayout: null,
    __creatingNewStudy: null,
    __studiesPane: null,
    __editPane: null,
    __userStudies: null,
    __templateStudies: null,
    __templateDeleteButton: null,
    __studiesDeleteButton: null,

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this.__studyFilters) {
        this.__studyFilters.reset();
      }
      this.__itemSelected(null);
    },

    /**
     *  Function that asks the backend for the list of studies belonging to the user
     * and sets it
     */
    reloadUserStudies: function(study) {
      if (osparc.data.Permissions.getInstance().canDo("studies.user.read")) {
        osparc.data.Resources.get("studies")
          .then(studies => {
            this.__setStudyList(studies);
            this.__itemSelected(study ? study.uuid : null, false);
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        this.__setStudyList([]);
      }
    },

    /**
     *  Function that asks the backend for the list of template studies and sets it
     */
    reloadTemplateStudies: function(template) {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        osparc.data.Resources.get("templates")
          .then(templates => {
            this.__setTemplateList(templates);
            this.__itemSelected(template ? template.uuid : null, true);
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        this.__setTemplateList([]);
      }
    },

    __initResources: function() {
      this.__userReady = osparc.data.Permissions.getInstance().arePermissionsReady();
      this.__getServicesPreload();
    },

    __getServicesPreload: function() {
      let store = osparc.store.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    },

    __createStudiesLayout: function() {
      const studyFilters = this.__studyFilters = new osparc.component.filter.TextFilter("text", "studyBrowser");
      osparc.utils.Utils.setIdToWidget(studyFilters, "studyFiltersTextFld");
      studyFilters.getChildControl("textfield").set({
        width: 210
      });

      const newStudyBtn = new qx.ui.form.Button(this.tr("Create new study"), "@FontAwesome5Solid/plus-circle/18").set({
        appearance: "big-button",
        allowGrowX: false,
        width: 210
      });
      osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
      newStudyBtn.addListener("execute", () => this.__createStudyBtnClkd());

      const navBarLabelFont = qx.bom.Font.fromConfig(osparc.theme.Font.fonts["nav-bar-label"]);
      const studiesTitleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const studiesDeleteButton = this.__studiesDeleteButton = this.__createDeleteButton();
      const myStudyLabel = new qx.ui.basic.Label(this.tr("My Studies")).set({
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

      this.__studiesPane.add(studyFilters);
      this.__studiesPane.add(userStudyLayout);
      this.__studiesPane.add(tempStudyLayout);
      this.__editPane.add(this.__editStudyLayout);
    },

    __createDeleteButton: function() {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        visibility: "excluded"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteStudiesBtn");
      deleteButton.addListener("execute", e => {
        const thisButton = e.getTarget();
        const isTemplate = this.__templateDeleteButton === thisButton;
        const selection = isTemplate ? this.__templateStudyContainer.getSelection() : this.__userStudyContainer.getSelection();
        const win = this.__createConfirmWindow(selection.length > 1);
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

    __attachEventHandlers: function() {
      const textfield = this.__studyFilters.getChildControl("textfield", true);
      textfield.addListener("appear", () => {
        textfield.focus();
      }, this);
      const commandEsc = new qx.ui.command.Command("Esc");
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

      const newStudyDlg = new osparc.component.widget.NewStudyDlg(templateData);
      newStudyDlg.addListenerOnce("createStudy", e => {
        const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
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
      if (templateId) {
        const params = {
          url: {
            "template_id": templateId
          },
          data: minStudyData
        };
        osparc.data.Resources.fetch("studies", "postFromTemplate", params)
          .then(study => {
            this.__startStudy(study);
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        const params = {
          data: minStudyData
        };
        osparc.data.Resources.fetch("studies", "post", params)
          .then(study => {
            this.__startStudy(study);
          })
          .catch(err => {
            console.error(err);
          });
      }
    },

    __startStudy: function(studyData) {
      if (this.__servicesReady === null) {
        this.__showChildren(false);
        let iframe = osparc.utils.Utils.createLoadingIFrame(this.tr("Services"));
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
      const study = new osparc.data.model.Study(studyData, true);
      const studyEditor = new osparc.desktop.StudyEditor(study);
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
      osparc.utils.Utils.setIdToWidget(usrLst, "userStudiesList");
      this.reloadUserStudies();
      return usrLst;
    },

    __createTemplateStudyList: function() {
      const tempList = this.__templateStudyContainer = this.__createStudyListLayout();
      osparc.utils.Utils.setIdToWidget(tempList, "templateStudiesList");
      this.reloadTemplateStudies();
      return tempList;
    },

    __setStudyList: function(userStudyList) {
      this.__userStudies = userStudyList;
      this.__userStudyContainer.removeAll();
      osparc.desktop.StudyBrowser.sortStudyList(userStudyList);
      for (let i=0; i<userStudyList.length; i++) {
        this.__userStudyContainer.add(this.__createStudyItem(userStudyList[i], false));
      }
    },

    __setTemplateList: function(tempStudyList) {
      this.__templateStudies = tempStudyList;
      this.__templateStudyContainer.removeAll();
      osparc.desktop.StudyBrowser.sortStudyList(tempStudyList);
      for (let i=0; i<tempStudyList.length; i++) {
        this.__templateStudyContainer.add(this.__createStudyItem(tempStudyList[i], true));
      }
    },

    __createStudyListLayout: function() {
      return new osparc.component.form.ToggleButtonContainer(new qx.ui.layout.Flow(8, 8));
    },

    __createStudyItem: function(study, isTemplate) {
      const item = new osparc.desktop.StudyBrowserListItem().set({
        uuid: study.uuid,
        studyTitle: study.name,
        icon: study.thumbnail ? study.thumbnail : osparc.utils.Utils.getThumbnailFromUuid(study.uuid),
        creator: study.prjOwner ? "Created by: <b>" + study.prjOwner + "</b>" : null,
        lastChangeDate: study.lastChangeDate ? new Date(study.lastChangeDate) : null
      });

      item.subscribeToFilterGroup("studyBrowser");

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

    __itemSelected: function(studyId, isTemplate = false) {
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
      const studyData = this.__getStudyData(studyId, isTemplate);
      this.__createForm(studyData, isTemplate);
      this.__editPane.setVisibility("visible");
    },

    __createForm: function(studyData, isTemplate) {
      this.__editStudyLayout.removeAll();
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(studyData, isTemplate);
      studyDetails.addListener("closed", () => this.__itemSelected(null), this);
      studyDetails.addListener("updatedStudy", e => this.reloadUserStudies(e.getData()), this);
      studyDetails.addListener("updatedTemplate", e => this.reloadTemplateStudies(e.getData()), this);
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
      const canDeleteTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.delete");
      const isCurrentUserOwner = studyData.prjOwner === osparc.auth.Data.getInstance().getEmail();
      let deleteButton = this.__studiesDeleteButton;
      if (isTemplate) {
        this.__studiesDeleteButton.exclude();
        deleteButton = this.__templateDeleteButton;
      } else {
        this.__templateDeleteButton.exclude();
        const nSelected = this.__userStudyContainer.getSelection().length;
        this.__studiesDeleteButton.setLabel(nSelected > 1 ? this.tr("Delete selected")+" ("+nSelected+")" : this.tr("Delete"));
      }
      deleteButton.show();
      deleteButton.setEnabled(isCurrentUserOwner && (!isTemplate || canDeleteTemplate));
    },

    __deleteStudy: function(studyData, isTemplate = false) {
      this.__stopInteractiveServicesInStudy(studyData);
      studyData.forEach(study => {
        const params = {
          url: {
            "project_id": study.uuid
          }
        };
        osparc.data.Resources.fetch(isTemplate ? "templates" : "studies", "delete", params, study.uuid)
          .then(() => {
            if (isTemplate) {
              this.reloadTemplateStudies();
            } else {
              this.reloadUserStudies();
            }
            this.__itemSelected(null);
          })
          .catch(err => console.error(err));
      });
    },

    __stopInteractiveServicesInStudy: function(studies) {
      studies.forEach(studyData => {
        for (const [nodeId, nodedata] of Object.entries(studyData["workbench"])) {
          const metadata = osparc.utils.Services.getNodeMetaData(nodedata.key, nodedata.version);
          if (osparc.data.model.Node.isDynamic(metadata) && osparc.data.model.Node.isRealService(metadata)) {
            osparc.utils.Services.stopInteractiveService(nodeId);
          }
        }
      });
    },

    __createConfirmWindow: function(isMulti) {
      const win = new qx.ui.window.Window("Confirmation").set({
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

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(10, "right"));
      const btnNo = new qx.ui.form.Button("No");
      osparc.utils.Utils.setIdToWidget(btnNo, "cancelDeleteStudyBtn");
      const btnYes = new qx.ui.form.Button("Yes");
      osparc.utils.Utils.setIdToWidget(btnYes, "confirmDeleteStudyBtn");
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
    }
  }
});
