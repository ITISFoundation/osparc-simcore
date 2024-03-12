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
    WIDTH: 830,
    HEIGHT: 700,

    popUpInWindow: function(moreOpts) {
      // eslint-disable-next-line no-underscore-dangle
      const resourceAlias = osparc.utils.Utils.resourceTypeToAlias(moreOpts.__resourceData["resourceType"]);
      // eslint-disable-next-line no-underscore-dangle
      const title = `${resourceAlias} ${qx.locale.Manager.tr("Details")} - ${moreOpts.__resourceData.name}`
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
    __tabsView: null,
    __dataPage: null,
    __permissionsPage: null,
    __tagsPage: null,
    __billingSettings: null,
    __classifiersPage: null,
    __qualityPage: null,
    __servicesUpdatePage: null,
    __openButton: null,
    _services: null,

    __createToolbar: function() {
      const toolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
        alignX: "right",
        alignY: "top"
      })).set({
        maxHeight: 40
      });
      return toolbar;
    },

    __addOpenButton: function(page) {
      const resourceData = this.__resourceData;

      const toolbar = this.__createToolbar();
      page.addToHeader(toolbar);

      if (osparc.utils.Resources.isService(resourceData)) {
        const serviceVersionSelector = this.__createServiceVersionSelector();
        toolbar.add(serviceVersionSelector);
      }

      const openButton = this.__openButton = new osparc.ui.form.FetchButton(this.tr("Open")).set({
        enabled: true
      });
      osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(openButton);
      osparc.utils.Utils.setIdToWidget(openButton, "openResource");
      const store = osparc.store.Store.getInstance();
      store.bind("currentStudy", openButton, "visibility", {
        converter: study => (study === null && this.isShowOpenButton()) ? "visible" : "excluded"
      });
      this.bind("showOpenButton", openButton, "visibility", {
        converter: show => (store.getCurrentStudy() === null && show) ? "visible" : "excluded"
      });

      openButton.addListener("execute", () => this.__openTapped());

      toolbar.add(openButton);
    },

    __openTapped: function() {
      if (this.__resourceData["resourceType"] !== "study") {
        // Nothing to pre-check
        this.__openResource();
        return;
      }
      this.__openButton.setFetching(true);
      const params = {
        url: {
          "studyId": this.__resourceData["uuid"]
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(updatedStudyData => {
          this.__openButton.setFetching(false);
          const workbench = updatedStudyData.workbench;
          const updatableServices = [];
          let anyUpdatable = false;
          for (const nodeId in workbench) {
            const node = workbench[nodeId];
            const latestCompatibleMetadata = osparc.service.Utils.getLatestCompatible(this._services, node["key"], node["version"]);
            if (latestCompatibleMetadata === null) {
              osparc.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
            }
            const isUpdatable = osparc.service.Utils.isUpdatable(node);
            if (isUpdatable) {
              anyUpdatable = true;
              updatableServices.push(nodeId);
            }
          }
          if (anyUpdatable) {
            this.__confirmUpdate();
          } else {
            this.__openResource();
          }
        })
        .catch(() => this.__openButton.setFetching(false));
    },

    __confirmUpdate: function() {
      const msg = this.tr("Some of your services are outdated. Please update to the latest version for better performance.\n\nDo you want to update now?");
      const win = new osparc.dashboard.ResourceUpgradeHelper(msg).set({
        primaryAction: "create",
        secondaryAction: "primary"
      });
      win.center();
      win.open();
      win.addListenerOnce("close", () => {
        if (win.getConfirmed()) {
          this.__openPage(this.__servicesUpdatePage);
        } else {
          this.__openResource();
        }
      });
    },

    __openResource: function() {
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
      this.__addOpenButton(page);
      page.addToContent(infoCard);
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
      const billingScroll = new qx.ui.container.Scroll(billingSettings);
      this.__addOpenButton(page);
      page.addToContent(billingScroll);
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
      this.__addOpenButton(page);
      page.addToContent(preview);
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

      const commentsList = new osparc.info.CommentsList(resourceData["uuid"]);
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);
      page.addToContent(commentsList);
      if (osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
        const addComment = new osparc.info.CommentAdd(resourceData["uuid"]);
        addComment.setPaddingLeft(10);
        addComment.addListener("commentAdded", () => commentsList.fetchComments());
        page.addToFooter(addComment);
      }
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
      this.__addOpenButton(page);
      page.addToContent(studyDataManager);
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
      this.__addOpenButton(page);
      page.addToContent(permissionsView);
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
      this.__addOpenButton(page);
      page.addToContent(classifiers);
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
        this.__addOpenButton(page);
        page.addToContent(qualityEditor);
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
      this.__addOpenButton(page);
      page.addToContent(tagManager);
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
      });

      const page = this.__servicesUpdatePage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);
      page.addToContent(servicesUpdate);
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
      this.__addOpenButton(page);
      page.addToContent(servicesBootOpts);

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
        const publishTemplateButton = saveAsTemplate.getPublishTemplateButton();
        osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(publishTemplateButton);
        const toolbar = this.__createToolbar();
        toolbar.add(publishTemplateButton);
        page.addToHeader(toolbar);
        page.addToContent(saveAsTemplate);

        return page;
      }
      return null;
    }
  }
});
