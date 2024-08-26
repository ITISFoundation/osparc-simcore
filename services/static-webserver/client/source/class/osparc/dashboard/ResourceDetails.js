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

qx.Class.define("osparc.dashboard.ResourceDetails", {
  extend: osparc.ui.window.TabbedView,

  construct: function(resourceData) {
    this.base(arguments);

    this.__resourceData = resourceData;

    this.__resourceModel = null;
    switch (resourceData["resourceType"]) {
      case "study":
      case "template":
        this.__resourceModel = new osparc.data.model.Study(resourceData);
        break;
      case "service":
        this.__resourceModel = new osparc.data.model.Service(resourceData);
        break;
    }
    this.__resourceModel["resourceType"] = resourceData["resourceType"];

    this.__addPages();
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

    popUpInWindow: function(resourceDetails) {
      // eslint-disable-next-line no-underscore-dangle
      const resourceAlias = osparc.utils.Utils.resourceTypeToAlias(resourceDetails.__resourceData["resourceType"]);
      // eslint-disable-next-line no-underscore-dangle
      const title = `${resourceAlias} ${qx.locale.Manager.tr("Details")} - ${resourceDetails.__resourceData.name}`;
      const win = osparc.ui.window.Window.popUpInWindow(resourceDetails, title, this.WIDTH, this.HEIGHT).set({
        layout: new qx.ui.layout.Grow(),
      });
      win.set(osparc.ui.window.TabbedWindow.DEFAULT_PROPS);
      win.set({
        width: this.WIDTH,
        height: this.HEIGHT,
      });
      return win;
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
    __resourceModel: null,
    __infoPage: null,
    __dataPage: null,
    __servicesUpdatePage: null,
    __permissionsPage: null,
    __tagsPage: null,
    __billingSettings: null,
    __classifiersPage: null,
    __qualityPage: null,
    __openButton: null,

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

      if (this.__resourceData["resourceType"] === "study") {
        const studyData = this.__resourceData;
        const canBeOpened = osparc.study.Utils.canBeOpened(studyData);
        openButton.setEnabled(canBeOpened);
      }

      toolbar.add(openButton);
    },

    __openTapped: function() {
      if (this.__resourceData["resourceType"] !== "study") {
        // Template or Service, nothing to pre-check
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
          this.openUpdateServices();
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

    __openInfo: function() {
      this._openPage(this.__infoPage);
    },

    openData: function() {
      this._openPage(this.__dataPage);
    },

    openUpdateServices: function() {
      this._openPage(this.__servicesUpdatePage);
    },

    openAccessRights: function() {
      this._openPage(this.__permissionsPage);
    },

    openTags: function() {
      this._openPage(this.__tagsPage);
    },

    openClassifiers: function() {
      this._openPage(this.__classifiersPage);
    },

    openQuality: function() {
      this._openPage(this.__qualityPage);
    },

    openBillingSettings: function() {
      this._openPage(this.__billingSettings);
    },

    __createServiceVersionSelector: function() {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      }));

      const versionLabel = new qx.ui.basic.Label(this.tr("Version")).set({
        font: "text-14"
      });
      hBox.add(versionLabel);
      const versionsBox = new osparc.ui.toolbar.SelectBox();
      hBox.add(versionsBox);


      const versions = osparc.service.Utils.getVersions(this.__resourceData["key"]);
      let selectedItem = null;

      // first setSelection
      versions.forEach(version => {
        selectedItem = osparc.service.Utils.versionToListItem(this.__resourceData["key"], version);
        versionsBox.add(selectedItem);
        if (this.__resourceData["version"] === version) {
          versionsBox.setSelection([selectedItem]);
        }
      });
      osparc.utils.Utils.growSelectBox(versionsBox, 200);

      // then listen to changes
      versionsBox.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const serviceVersion = selection[0].version;
          if (serviceVersion !== this.__resourceData["version"]) {
            osparc.service.Store.getService(this.__resourceData["key"], serviceVersion)
              .then(serviceData => {
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
      const tabsView = this.getChildControl("tabs-view");

      // keep selected page
      const selection = tabsView.getSelection();
      const selectedTabId = selection.length ? selection[0]["tabId"] : null;

      // removeAll
      osparc.utils.Utils.removeAllChildren(tabsView);

      // add Open service button
      [
        this.__getInfoPage,
        this.__getBillingPage,
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
            tabsView.add(page);
          }
        }
      });

      if (selectedTabId) {
        const pageFound = tabsView.getChildren().find(page => page.tabId === selectedTabId);
        if (pageFound) {
          tabsView.setSelection([pageFound]);
        }
      }
    },

    __getInfoPage: function() {
      const id = "Information";
      const title = this.tr("Overview");
      const iconSrc = "@FontAwesome5Solid/info/22";
      const page = this.__infoPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      const lazyLoadContent = () => {
        const resourceData = this.__resourceData;
        const resourceModel = this.__resourceModel;
        let infoCard = null;
        if (osparc.utils.Resources.isService(resourceData)) {
          infoCard = new osparc.info.ServiceLarge(resourceData, null, false);
          infoCard.addListener("updateService", e => {
            const updatedData = e.getData();
            if (osparc.utils.Resources.isService(resourceData)) {
              this.fireDataEvent("updateService", updatedData);
            }
          });
        } else {
          infoCard = new osparc.info.StudyLarge(resourceModel, false);
          infoCard.addListener("updateStudy", e => {
            const updatedData = e.getData();
            if (osparc.utils.Resources.isStudy(resourceData)) {
              this.fireDataEvent("updateStudy", updatedData);
            } else if (osparc.utils.Resources.isTemplate(resourceData)) {
              this.fireDataEvent("updateTemplate", updatedData);
            }
          });
          infoCard.addListener("openTags", () => this.openTags());
        }
        infoCard.addListener("openAccessRights", () => this.openAccessRights());
        infoCard.addListener("openClassifiers", () => this.openClassifiers());
        infoCard.addListener("openQuality", () => this.openQuality());
        page.addToContent(infoCard);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getBillingPage: function() {
      if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
        return null;
      }

      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isStudy(resourceData)) {
        const id = "Billing";
        const title = this.tr("Billing Settings");
        const iconSrc = "@FontAwesome5Solid/cogs/22";
        const page = this.__billingSettings = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
        this.__addOpenButton(page);

        if (this.__resourceData["resourceType"] === "study") {
          const studyData = this.__resourceData;
          const canBeOpened = osparc.study.Utils.canShowBillingOptions(studyData);
          page.setEnabled(canBeOpened);
        }

        const lazyLoadContent = () => {
          const billingSettings = new osparc.study.BillingSettings(resourceData);
          const billingScroll = new qx.ui.container.Scroll(billingSettings);
          page.addToContent(billingScroll);
        }
        page.addListenerOnce("appear", lazyLoadContent, this);

        return page;
      } else if (osparc.utils.Resources.isService(resourceData)) {
        const id = "Tiers";
        const title = this.tr("Tiers");
        const iconSrc = "@FontAwesome5Solid/server/22";
        const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
        this.__addOpenButton(page);

        const lazyLoadContent = () => {
          const pricingUnitsList = new osparc.service.PricingUnitsList(resourceData);
          const pricingUnitsListScroll = new qx.ui.container.Scroll(pricingUnitsList);
          page.addToContent(pricingUnitsListScroll);
        }
        page.addListenerOnce("appear", lazyLoadContent, this);

        return page;
      }
      return null;
    },

    __getPreviewPage: function() {
      const resourceData = this.__resourceData;
      if (
        osparc.utils.Resources.isService(resourceData) ||
        !osparc.product.Utils.showStudyPreview() ||
        osparc.data.model.Study.getUiMode(resourceData) === "app"
      ) {
        // there is no pipelining or don't show it
        return null;
      }

      const id = "Pipeline";
      const title = this.tr("Pipeline View");
      const iconSrc = "@FontAwesome5Solid/eye/22";
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      if (this.__resourceData["resourceType"] === "study") {
        const studyData = this.__resourceData;
        const canBeOpened = osparc.study.Utils.canShowPreview(studyData);
        page.setEnabled(canBeOpened);
      }

      const lazyLoadContent = () => {
        const resourceModel = this.__resourceModel;
        const preview = new osparc.study.StudyPreview(resourceModel);
        page.addToContent(preview);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

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
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      const lazyLoadContent = () => {
        const commentsList = new osparc.info.CommentsList(resourceData["uuid"]);
        page.addToContent(commentsList);
        if (osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
          const addComment = new osparc.info.CommentAdd(resourceData["uuid"]);
          addComment.setPaddingLeft(10);
          addComment.addListener("commentAdded", () => commentsList.fetchComments());
          page.addToFooter(addComment);
        }
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

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
      const page = this.__dataPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      if (this.__resourceData["resourceType"] === "study") {
        const studyData = this.__resourceData;
        const canBeOpened = osparc.study.Utils.canShowStudyData(studyData);
        page.setEnabled(canBeOpened);
      }

      const lazyLoadContent = () => {
        const studyDataManager = new osparc.widget.NodeDataManager(resourceData["uuid"]);
        page.addToContent(studyDataManager);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getPermissionsPage: function() {
      const id = "Permissions";
      const title = this.tr("Sharing");
      const iconSrc = "@FontAwesome5Solid/share-alt/22";
      const page = this.__permissionsPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      const lazyLoadContent = () => {
        const resourceData = this.__resourceData;
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
        page.addToContent(permissionsView);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

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
      const page = this.__classifiersPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      const lazyLoadContent = () => {
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
        page.addToContent(classifiers);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getQualityPage: function() {
      if (!osparc.product.Utils.showQuality()) {
        return null;
      }

      const resourceData = this.__resourceData;
      if (
        "quality" in resourceData &&
        (!osparc.utils.Resources.isService(resourceData) || osparc.data.model.Node.isComputational(resourceData))
      ) {
        const id = "Quality";
        const title = this.tr("Quality");
        const iconSrc = "@FontAwesome5Solid/star-half/22";
        const page = this.__qualityPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
        this.__addOpenButton(page);

        const lazyLoadContent = () => {
          const qualityEditor = new osparc.metadata.QualityEditor(resourceData);
          qualityEditor.addListener("updateQuality", e => {
            const updatedData = e.getData();
            if (osparc.utils.Resources.isStudy(resourceData)) {
              this.fireDataEvent("updateStudy", updatedData);
            } else if (osparc.utils.Resources.isTemplate(resourceData)) {
              this.fireDataEvent("updateTemplate", updatedData);
            }
          });
          page.addToContent(qualityEditor);
        }
        page.addListenerOnce("appear", lazyLoadContent, this);

        return page;
      }
      return null;
    },

    __getTagsPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }
      if (!osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
        return null;
      }

      const id = "Tags";
      const title = this.tr("Tags");
      const iconSrc = "@FontAwesome5Solid/tags/22";
      const page = this.__tagsPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      const lazyLoadContent = () => {
        const tagManager = new osparc.form.tag.TagManager(resourceData);
        tagManager.addListener("updateTags", e => {
          const updatedData = e.getData();
          tagManager.setStudyData(updatedData);
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        }, this);
        page.addToContent(tagManager);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getServicesUpdatePage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const id = "ServicesUpdate";
      const title = this.tr("Services Updates");
      const iconSrc = "@MaterialIcons/update/22";
      const page = this.__servicesUpdatePage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      if (this.__resourceData["resourceType"] === "study") {
        const studyData = this.__resourceData;
        const canBeOpened = osparc.study.Utils.canShowServiceUpdates(studyData);
        page.setEnabled(canBeOpened);
      }

      const lazyLoadContent = () => {
        const servicesUpdate = new osparc.metadata.ServicesInStudyUpdate(resourceData);
        servicesUpdate.addListener("updateService", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        });
        page.addToContent(servicesUpdate);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getServicesBootOptionsPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const id = "ServicesBootOptions";
      const title = this.tr("Boot Options");
      const iconSrc = "@FontAwesome5Solid/play-circle/22";
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addOpenButton(page);

      if (this.__resourceData["resourceType"] === "study") {
        const studyData = this.__resourceData;
        const canBeOpened = osparc.study.Utils.canShowServiceBootOptions(studyData);
        page.setEnabled(canBeOpened);
      }

      const lazyLoadContent = () => {
        const servicesBootOpts = new osparc.metadata.ServicesInStudyBootOpts(resourceData);
        servicesBootOpts.addListener("updateService", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        });
        page.addToContent(servicesBootOpts);

        if (osparc.utils.Resources.isStudy(resourceData) || osparc.utils.Resources.isTemplate(resourceData)) {
          if (osparc.product.Utils.showDisableServiceAutoStart()) {
            const study = new osparc.data.model.Study(resourceData);
            const autoStartButton = osparc.info.StudyUtils.createDisableServiceAutoStart(study).set({
              enabled: osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"])
            });
            // eslint-disable-next-line no-underscore-dangle
            servicesBootOpts._add(new qx.ui.core.Spacer(null, 15));
            // eslint-disable-next-line no-underscore-dangle
            servicesBootOpts._add(autoStartButton);
          }
        }
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getSaveAsTemplatePage: function() {
      if (!osparc.utils.Resources.isStudy(this.__resourceData)) {
        return null;
      }

      const canIWrite = osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"]);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (canIWrite && canCreateTemplate) {
        const id = "SaveAsTemplate";
        const iconSrc = "@FontAwesome5Solid/copy/22";
        const title = this.tr("Publish ") + osparc.product.Utils.getTemplateAlias({firstUpperCase: true});
        const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);

        if (this.__resourceData["resourceType"] === "study") {
          const studyData = this.__resourceData;
          const canBeOpened = osparc.study.Utils.canBeDuplicated(studyData);
          page.setEnabled(canBeOpened);
        }

        const lazyLoadContent = () => {
          const saveAsTemplate = new osparc.study.SaveAsTemplate(this.__resourceData);
          saveAsTemplate.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));

          const publishTemplateButton = saveAsTemplate.getPublishTemplateButton();
          osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(publishTemplateButton);
          const toolbar = this.__createToolbar();
          toolbar.add(publishTemplateButton);
          page.addToHeader(toolbar);
          page.addToContent(saveAsTemplate);
        }
        page.addListenerOnce("appear", lazyLoadContent, this);

        return page;
      }
      return null;
    }
  }
});
