/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ResourceMoreOptions", {
  extend: qx.ui.core.Widget,

  construct: function(resourceData) {
    this.base(arguments);

    this.__resourceData = resourceData;

    this._setLayout(new qx.ui.layout.VBox(10));
    this.set({
      padding: 20,
      paddingLeft: 10
    });
    this.__addTabPagesView();
  },

  events: {
    "openStudy": "qx.event.type.Data",
    "openTemplate": "qx.event.type.Data",
    "openService": "qx.event.type.Data",
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data"
  },

  statics: {
    WIDTH: 1035,
    HEIGHT: 720,

    popUpInWindow: function(moreOpts) {
      const prjAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      // eslint-disable-next-line no-underscore-dangle
      const title = qx.locale.Manager.tr(prjAlias + ` Details - ${moreOpts.__resourceData.name}`);
      return osparc.ui.window.Window.popUpInWindow(moreOpts, title, this.WIDTH, this.HEIGHT).set({
        maxHeight: 1000,
        layout: new qx.ui.layout.Grow(),
        modal: true,
        width: this.WIDTH,
        height: this.HEIGHT,
        showMaximize: false,
        showMinimize: false,
        resizable: true,
        appearance: "service-window"
      });
    }
  },

  properties: {
    showOpenButton: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeShowOpenButton"
    }
  },

  members: {
    __resourceData: null,
    __toolbar: null,
    __tabsView: null,
    __dataPage: null,
    __permissionsPage: null,
    __tagsPage: null,
    __billingSettings: null,
    __classifiersPage: null,
    __qualityPage: null,
    __servicesUpdatePage: null,
    __openButton: null,
    __anyUpdatable: null,
    _services: null,

    __addToolbar: function() {
      const toolbar = this.__toolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
        alignX: "right",
        alignY: "top"
      })).set({
        maxHeight: 40
      });

      const resourceData = this.__resourceData;

      if (osparc.utils.Resources.isService(resourceData)) {
        const serviceVersionSelector = this.__createServiceVersionSelector();
        toolbar.add(serviceVersionSelector);
      }

      this.__createOpenButton();
      this.__handleServiceUpdatableCheck(resourceData.workbench);

      return toolbar;
    },

    __createOpenButton: function() {
      const openButton = this.__openButton = new qx.ui.form.Button(this.tr("Open")).set({
        appearance: "form-button",
        font: "text-14",
        alignX: "right",
        minWidth: 150,
        maxWidth: 150,
        height: 35,
        center: true,
        enabled: true
      });
      osparc.utils.Utils.setIdToWidget(openButton, "openResource");
      const store = osparc.store.Store.getInstance();
      store.bind("currentStudy", openButton, "visibility", {
        converter: study => (study === null && this.isShowOpenButton()) ? "visible" : "excluded"
      });
      this.bind("showOpenButton", openButton, "visibility", {
        converter: show => (store.getCurrentStudy() === null && show) ? "visible" : "excluded"
      });
    },

    __handleServiceUpdatableCheck: function(workbench) {
      const updatableServices = [];
      this.__anyUpdatable = false;
      for (const nodeId in workbench) {
        const node = workbench[nodeId];
        const latestCompatibleMetadata = osparc.service.Utils.getLatestCompatible(this._services, node["key"], node["version"]);
        if (latestCompatibleMetadata === null) {
          osparc.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
        }
        const isUpdatable = osparc.service.Utils.isUpdatable(node);
        if (isUpdatable) {
          this.__anyUpdatable = true;
          updatableServices.push(nodeId);
        }
      }
      if (this.__anyUpdatable) {
        this.__confirmUpdate();
      } else {
        this.__openStudy();
      }
      this.__toolbar.add(this.__openButton);
    },

    __openStudy: function() {
      this.__openButton.setLabel("Open");
      this.__openButton.addListenerOnce("execute", () => {
        switch (this.__resourceData["resourceType"]) {
          case "study":
            this.fireDataEvent("openStudy", this.__resourceData);
            break;
          case "template":
            this.fireDataEvent("openTemplate", this.__resourceData);
            break;
          case "service":
            this.fireDataEvent("openService", this.__resourceData);
            break;
        }
      }, true);
    },

    __confirmUpdate: function() {
      this.__openButton.addListenerOnce("tap", () => {
        const msg = this.tr("Some of your services are outdated. Please update to the latest version for better performance.\n\nDo you want to update now?");
        const win = new osparc.dashboard.ResourceUpgradeHelper(msg).set({
          primaryAction: "create",
          secondaryAction: "primary"
        });
        win.center();
        win.open();
        win.addListenerOnce("close", () => {
          if (win.getConfirmed()) {
            this.__isUpdatable = false;
            this.__openPage(this.__servicesUpdatePage);
          } else {
            this.__isUpdatable = false;
            switch (this.__resourceData["resourceType"]) {
              case "study":
                this.fireDataEvent("openStudy", this.__resourceData);
                break;
              case "template":
                this.fireDataEvent("openTemplate", this.__resourceData);
                break;
              case "service":
                this.fireDataEvent("openService", this.__resourceData);
                break;
            }
          }
        });
      }, this);
    },

    __addTabPagesView: function() {
      const detailsView = this.__tabsView = new qx.ui.tabview.TabView().set({
        barPosition: "left",
        contentPadding: 0
      });
      this._add(detailsView, {
        flex: 1
      });

      this.__addPages();
    },

    __openPage: function(page) {
      if (page) {
        this.__tabsView.setSelection([page]);
      }
    },

    openData: function() {
      this.__openPage(this.__dataPage);
    },

    openAccessRights: function() {
      this.__openPage(this.__permissionsPage);
    },

    openTags: function() {
      this.__openPage(this.__tagsPage);
    },

    openClassifiers: function() {
      this.__openPage(this.__classifiersPage);
    },

    openQuality: function() {
      this.__openPage(this.__qualityPage);
    },

    openBillingSettings: function() {
      this.__openPage(this.__billingSettings);
    },

    openUpdateServices: function() {
      this.__openPage(this.__servicesUpdatePage);
    },

    __createServiceVersionSelector: function() {
      const hBox = this.__serviceVersionLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      }));

      const versionLabel = new qx.ui.basic.Label(this.tr("Version")).set({
        font: "text-14"
      });
      hBox.add(versionLabel);
      const versionsBox = new osparc.ui.toolbar.SelectBox();
      hBox.add(versionsBox);

      // populate it with owned versions
      const store = osparc.store.Store.getInstance();
      store.getAllServices()
        .then(services => {
          const versions = osparc.service.Utils.getVersions(services, this.__resourceData["key"]);
          let selectedItem = null;
          versions.reverse().forEach(version => {
            selectedItem = new qx.ui.form.ListItem(version);
            versionsBox.add(selectedItem);
            if (this.__resourceData["version"] === version) {
              versionsBox.setSelection([selectedItem]);
            }
          });
        });

      versionsBox.addListener("changeSelection", () => {
        const selection = versionsBox.getSelection();
        if (selection && selection.length) {
          const serviceVersion = selection[0].getLabel();
          if (serviceVersion !== this.__resourceData["version"]) {
            store.getAllServices()
              .then(services => {
                const serviceData = osparc.service.Utils.getFromObject(services, this.__resourceData["key"], serviceVersion);
                serviceData["resourceType"] = "service";
                this.__resourceData = serviceData;
                this.__addPages();
              });
          }
        }
      }, this);

      return hBox;
    },

    __addPages: function() {
      const detailsView = this.__tabsView;

      // keep selected page
      const selection = detailsView.getSelection();
      const selectedTabId = selection.length ? selection[0]["tabId"] : null;

      // removeAll
      const pages = detailsView.getChildren().length;
      for (let i=pages-1; i>=0; i--) {
        detailsView.remove(detailsView.getChildren()[i]);
      }

      // add Open service button
      [
        this.__getInfoPage,
        this.__getBillingSettings,
        this.__getServicesUpdatePage,
        this.__getServicesBootOptionsPage,
        this.__getDataPage,
        this.__getCommentsPage,
        this.__getPermissionsPage,
        this.__getSaveAsTemplatePage,
        this.__getTagsPage,
        this.__getQualityPage,
        this.__getClassifiersPage,
        this.__getPreviewPage
      ].forEach(pageCallee => {
        if (pageCallee) {
          const page = pageCallee.call(this);
          if (page) {
            detailsView.add(page);
          }
        }
      });

      if (selectedTabId) {
        const pageFound = detailsView.getChildren().find(page => page.tabId === selectedTabId);
        if (pageFound) {
          detailsView.setSelection([pageFound]);
        }
      }
    },

    __getInfoPage: function() {
      const id = "Information";
      const title = this.tr("Overview");
      const iconSrc = "@FontAwesome5Solid/info/22";
      const resourceData = this.__resourceData;
      const infoCard = osparc.utils.Resources.isService(resourceData) ? new osparc.info.ServiceLarge(resourceData, null, false) : new osparc.info.StudyLarge(resourceData, false);
      infoCard.addListener("openAccessRights", () => this.openAccessRights());
      infoCard.addListener("openClassifiers", () => this.openClassifiers());
      infoCard.addListener("openQuality", () => this.openQuality());
      infoCard.addListener("openTags", () => this.openTags());
      infoCard.addListener("updateStudy", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });
      infoCard.addListener("updateService", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isService(resourceData)) {
          this.fireDataEvent("updateService", updatedData);
        }
      });
      infoCard.addListener("updateTags", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });

      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      const toolBar = this.__addToolbar();
      page.add(toolBar);
      page.add(infoCard, {
        flex: 1
      });
      return page;
    },

    __getBillingSettings: function() {
      const resourceData = this.__resourceData;
      if (
        !osparc.utils.Resources.isStudy(resourceData) ||
        !osparc.desktop.credits.Utils.areWalletsEnabled()
      ) {
        return null;
      }

      const id = "Billing";
      const title = this.tr("Billing Settings");
      const iconSrc = "@FontAwesome5Solid/cogs/22";

      const billingSettings = new osparc.study.BillingSettings(resourceData);
      const page = this.__billingSettings = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      const billingScroll = new qx.ui.container.Scroll(billingSettings);
      page.add(billingScroll, {
        flex: 1
      });
      return page;
    },

    __getPreviewPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const id = "Pipeline";
      const title = this.tr("Pipeline View");
      const iconSrc = "@FontAwesome5Solid/eye/22";
      const preview = new osparc.study.StudyPreview(resourceData);
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(preview, {
        flex: 1
      });

      return page;
    },

    __getCommentsPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const id = "Comments";
      const title = this.tr("Comments");
      const iconSrc = "@FontAwesome5Solid/comments/22";

      const commentsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      const commentsList = new osparc.info.CommentsList(resourceData["uuid"]);
      commentsLayout.add(commentsList);
      if (osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
        const addComment = new osparc.info.CommentAdd(resourceData["uuid"]);
        addComment.setPaddingLeft(10);
        addComment.addListener("commentAdded", () => commentsList.fetchComments());
        commentsLayout.add(addComment);
      }
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      const commentsScroll = new qx.ui.container.Scroll(commentsLayout);
      page.add(commentsScroll, {
        flex: 1
      })
      return page;
    },

    __getDataPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const id = "Data";
      const title = osparc.product.Utils.getStudyAlias({firstUpperCase: true}) + this.tr(" Files");
      const iconSrc = "@FontAwesome5Solid/file/22";
      const studyDataManager = new osparc.widget.NodeDataManager(resourceData["uuid"]);

      const page = this.__dataPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(studyDataManager, {
        flex: 1
      });

      return page;
    },

    __getPermissionsPage: function() {
      const id = "Permissions";
      const resourceData = this.__resourceData;

      const title = this.tr("Sharing");
      const iconSrc = "@FontAwesome5Solid/share-alt/22";
      let permissionsView = null;
      if (osparc.utils.Resources.isService(resourceData)) {
        permissionsView = new osparc.share.CollaboratorsService(resourceData);
        permissionsView.addListener("updateAccessRights", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isService(resourceData)) {
            this.fireDataEvent("updateService", updatedData);
          }
        }, this);
      } else {
        permissionsView = new osparc.share.CollaboratorsStudy(resourceData);
        if (osparc.utils.Resources.isStudy(resourceData)) {
          permissionsView.getChildControl("study-link").show();
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          permissionsView.getChildControl("template-link").show();
        }
        permissionsView.addListener("updateAccessRights", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        }, this);
      }
      const page = this.__permissionsPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(permissionsView, {
        flex: 1
      });

      return page;
    },

    __getClassifiersPage: function() {
      if (!osparc.product.Utils.showClassifiers()) {
        return null;
      }
      const id = "Classifiers";
      if (!osparc.data.Permissions.getInstance().canDo("study.classifier")) {
        return null;
      }
      const title = this.tr("Classifiers");
      const iconSrc = "@FontAwesome5Solid/search/22";
      const resourceData = this.__resourceData;
      let classifiers = null;
      if (
        (osparc.utils.Resources.isStudy(resourceData) || osparc.utils.Resources.isTemplate(resourceData)) && osparc.data.model.Study.canIWrite(resourceData["accessRights"]) ||
        osparc.utils.Resources.isService(resourceData) && osparc.service.Utils.canIWrite(resourceData["accessRights"])
      ) {
        classifiers = new osparc.metadata.ClassifiersEditor(resourceData);
        classifiers.addListener("updateClassifiers", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          } else if (osparc.utils.Resources.isService(resourceData)) {
            this.fireDataEvent("updateService", updatedData);
          }
        }, this);
      } else {
        classifiers = new osparc.metadata.ClassifiersViewer(resourceData);
      }

      const page = this.__permissionsPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(classifiers, {
        flex: 1
      });

      return page;
    },

    __getQualityPage: function() {
      if (!osparc.product.Utils.showQuality()) {
        return null;
      }
      const id = "Quality";
      const resourceData = this.__resourceData;
      if (
        "quality" in resourceData &&
        (!osparc.utils.Resources.isService(resourceData) || osparc.data.model.Node.isComputational(resourceData))
      ) {
        const title = this.tr("Quality");
        const iconSrc = "@FontAwesome5Solid/star-half/22";
        const qualityEditor = new osparc.metadata.QualityEditor(resourceData);
        qualityEditor.addListener("updateQuality", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        });

        const page = this.__qualityPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
        page.showLabelOnTab();
        page.add(qualityEditor, {
          flex: 1
        });

        return page;
      }
      return null;
    },

    __getTagsPage: function() {
      const id = "Tags";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }
      if (!osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
        return null;
      }

      const title = this.tr("Tags");
      const iconSrc = "@FontAwesome5Solid/tags/22";
      const tagManager = new osparc.form.tag.TagManager(resourceData);
      tagManager.addListener("updateTags", e => {
        const updatedData = e.getData();
        tagManager.setStudyData(updatedData);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
      const page = this.__tagsPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(tagManager, {
        flex: 1
      });
      return page;
    },

    __getServicesUpdatePage: function() {
      const id = "ServicesUpdate";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const title = this.tr("Services Updates");
      const iconSrc = "@MaterialIcons/update/22";
      const servicesUpdate = new osparc.metadata.ServicesInStudyUpdate(resourceData);
      servicesUpdate.addListener("updateService", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
        this.__handleServiceUpdatableCheck(updatedData.workbench);
      });

      const page = this.__servicesUpdatePage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(servicesUpdate, {
        flex: 1
      });
      return page;
    },

    __getServicesBootOptionsPage: function() {
      const id = "ServicesBootOptions";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const title = this.tr("Boot Options");
      const iconSrc = "@FontAwesome5Solid/play-circle/22";
      const servicesBootOpts = new osparc.metadata.ServicesInStudyBootOpts(resourceData);
      servicesBootOpts.addListener("updateService", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });

      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      page.showLabelOnTab();
      page.add(servicesBootOpts, {
        flex: 1
      });

      if (osparc.utils.Resources.isStudy(resourceData)) {
        if (osparc.product.Utils.showDisableServiceAutoStart()) {
          const study = new osparc.data.model.Study(resourceData);
          const autoStartButton = osparc.info.StudyUtils.createDisableServiceAutoStart(study);
          // eslint-disable-next-line no-underscore-dangle
          servicesBootOpts._add(new qx.ui.core.Spacer(null, 15));
          // eslint-disable-next-line no-underscore-dangle
          servicesBootOpts._add(autoStartButton);
        }
      }

      return page;
    },

    __getSaveAsTemplatePage: function() {
      const id = "SaveAsTemplate";
      if (!osparc.utils.Resources.isStudy(this.__resourceData)) {
        return null;
      }

      const canIWrite = osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"]);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (canIWrite && canCreateTemplate) {
        const title = this.tr("Publish ") + osparc.product.Utils.getTemplateAlias({firstUpperCase: true});
        const iconSrc = "@FontAwesome5Solid/copy/22";
        const saveAsTemplate = new osparc.study.SaveAsTemplate(this.__resourceData);
        saveAsTemplate.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));

        const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
        page.showLabelOnTab();
        page.add(saveAsTemplate, {
          flex: 1
        });
        return page;
      }
      return null;
    }
  }
});
