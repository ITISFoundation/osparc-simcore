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

    let latestPromise = null;
    switch (resourceData["resourceType"]) {
      case "study":
      case "template":
      case "tutorial":
      case "hypertool": {
        const params = {
          url: {
            "studyId": resourceData["uuid"]
          }
        };
        latestPromise = osparc.data.Resources.fetch("studies", "getOne", params);
        break;
      }
      case "service": {
        latestPromise = osparc.store.Services.getService(resourceData["key"], resourceData["version"]);
        break;
      }
    }

    latestPromise
      .then(latestResourceData => {
        if (!latestResourceData) {
          const msg = this.tr("Data not found, please try again");
          osparc.FlashMessenger.logAs(msg, "WARNING");
          return;
        }
        this.__resourceData = osparc.utils.Utils.deepCloneObject(latestResourceData);
        this.__resourceData["resourceType"] = resourceData["resourceType"];
        switch (resourceData["resourceType"]) {
          case "study":
          case "template":
          case "tutorial":
          case "hypertool":
            // when getting the latest study data, the debt information was lost
            if (osparc.study.Utils.isInDebt(this.__resourceData)) {
              const mainStore = osparc.store.Store.getInstance();
              this.__resourceData["debt"] = mainStore.getStudyDebt(this.__resourceData["uuid"]);
            }
            osparc.store.Services.getStudyServicesMetadata(latestResourceData)
              .finally(() => {
                this.__resourceModel = new osparc.data.model.Study(latestResourceData);
                this.__resourceModel["resourceType"] = resourceData["resourceType"];
                this.__resourceData["services"] = resourceData["services"];
                this.__addPages();
              })
            break;
          case "service": {
            this.__resourceModel = new osparc.data.model.Service(latestResourceData);
            this.__resourceModel["resourceType"] = resourceData["resourceType"];
            this.__addPages();
            break;
          }
        }
      })
      .catch(err => osparc.FlashMessenger.logError(err));
  },

  events: {
    "pagesAdded": "qx.event.type.Event",
    "openStudy": "qx.event.type.Data",
    "openTemplate": "qx.event.type.Data",
    "openTutorial": "qx.event.type.Data",
    "openHypertool": "qx.event.type.Data",
    "openService": "qx.event.type.Data",
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateTutorial": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "updateHypertool": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data",
    "closeWindow": "qx.event.type.Event",
  },


  statics: {
    WIDTH: 830,
    HEIGHT: 700,

    popUpInWindow: function(resourceDetails) {
      // eslint-disable-next-line no-underscore-dangle
      const title = resourceDetails.__resourceData.name;
      const win = osparc.ui.window.Window.popUpInWindow(resourceDetails, title, this.WIDTH, this.HEIGHT).set({
        layout: new qx.ui.layout.Grow(),
      });
      win.set(osparc.ui.window.TabbedWindow.DEFAULT_PROPS);
      win.set({
        width: this.WIDTH,
        height: this.HEIGHT,
      });
      return win;
    },

    createToolbar: function() {
      const toolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
        alignX: "right",
        alignY: "top"
      })).set({
        maxHeight: 40
      });
      return toolbar;
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
    __servicesUpdatePage: null,
    __permissionsPage: null,
    __tagsPage: null,
    __billingSettings: null,
    __classifiersPage: null,
    __qualityPage: null,

    __addToolbarButtons: function(page) {
      const resourceData = this.__resourceData;

      const toolbar = this.self().createToolbar();
      page.addToHeader(toolbar);

      if (["study", "template", "tutorial"].includes(resourceData["resourceType"])) {
        const cantReadServices = osparc.study.Utils.getCantReadServices(resourceData["services"]);
        if (cantReadServices.length) {
          const requestAccessButton = new qx.ui.form.Button(this.tr("Request Apps Access"));
          osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(requestAccessButton);
          requestAccessButton.set({
            minWidth: 170,
            maxWidth: 170,
          });
          requestAccessButton.addListener("execute", () => {
            osparc.share.RequestServiceAccess.openRequestAccess(cantReadServices);
          });
          toolbar.add(requestAccessButton);
        }
      }

      if (this.__resourceData["resourceType"] === "study") {
        const payDebtButton = new qx.ui.form.Button(this.tr("Credits required"));
        page.payDebtButton = payDebtButton;
        osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(payDebtButton);
        payDebtButton.addListener("execute", () => this.openBillingSettings());
        const studyData = this.__resourceData;
        payDebtButton.set({
          visibility: osparc.study.Utils.isInDebt(studyData) ? "visible" : "excluded"
        });
        toolbar.add(payDebtButton);
      }

      if (osparc.utils.Resources.isService(resourceData)) {
        const serviceVersionSelector = this.__createServiceVersionSelector();
        toolbar.add(serviceVersionSelector);
      }

      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      const openText = (this.__resourceData["resourceType"] === "study") ? this.tr("Open") : this.tr("New") + " " + studyAlias;
      const openButton = new osparc.ui.form.FetchButton(openText).set({
        enabled: true
      });
      page.openButton = openButton;
      osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(openButton);
      osparc.utils.Utils.setIdToWidget(openButton, "openResource");
      const store = osparc.store.Store.getInstance();
      store.bind("currentStudy", openButton, "visibility", {
        converter: study => (study === null && this.isShowOpenButton()) ? "visible" : "excluded"
      });
      this.bind("showOpenButton", openButton, "visibility", {
        converter: show => (store.getCurrentStudy() === null && show) ? "visible" : "excluded"
      });
      openButton.addListener("execute", () => this.__openTapped(openButton));

      if (["study", "template"].includes(this.__resourceData["resourceType"])) {
        const studyData = this.__resourceData;
        const enabled = osparc.study.Utils.canBeOpened(studyData);
        openButton.setEnabled(enabled);
      }

      toolbar.add(openButton);
    },

    __openTapped: function(openButton) {
      if (this.__resourceData["resourceType"] !== "study") {
        // Template or Service, nothing to pre-check
        this.__openResource();
        return;
      }
      openButton.setFetching(true);
      const params = {
        url: {
          "studyId": this.__resourceData["uuid"]
        }
      };
      Promise.all([
        osparc.data.Resources.fetch("studies", "getOne", params),
        osparc.store.Services.getStudyServices(this.__resourceData["uuid"]),
      ])
        .then(values => {
          const updatedStudyData = values[0];
          const studyServices = values[1];
          openButton.setFetching(false);
          const updatableServices = osparc.study.Utils.updatableNodeIds(updatedStudyData.workbench, studyServices["services"]);
          if (updatableServices.length && osparc.data.model.Study.canIWrite(updatedStudyData["accessRights"])) {
            this.__confirmUpdate();
          } else {
            this.__openResource();
          }
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          openButton.setFetching(false);
        });
    },

    __confirmUpdate: function() {
      const msg = this.tr("Some of your services are outdated. Please update to the latest version for better performance.\n\nDo you want to update now?");
      const win = new osparc.dashboard.ResourceUpgradeHelper(msg).set({
        primaryAction: "create",
        secondaryAction: "primary"
      });
      win.center();
      win.open();
      win.addListener("changeConfirmed", e => {
        if (win.getConfirmed()) {
          this.openUpdateServices();
        } else {
          this.__openResource();
        }
        win.close();
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
        case "tutorial":
          this.fireDataEvent("openTutorial", this.__resourceData);
          break;
        case "hypertool":
          this.fireDataEvent("openHypertool", this.__resourceData);
          break;
        case "service":
          this.fireDataEvent("openService", this.__resourceData);
          break;
      }
    },

    __openInfo: function() {
      this._openPage(this.__infoPage);
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
      osparc.utils.Utils.setIdToWidget(versionsBox, "serviceSelectBox");
      hBox.add(versionsBox);


      osparc.store.Services.populateVersionsSelectBox(this.__resourceData["key"], versionsBox)
        .then(() => {
          // first setSelection
          const versionFound = versionsBox.getSelectables().find(selectable => selectable.version === this.__resourceData["version"]);
          if (versionFound) {
            versionsBox.setSelection([versionFound]);
          }
          osparc.utils.Utils.growSelectBox(versionsBox, 200);

          // then listen to changes
          versionsBox.addListener("changeSelection", e => {
            const selection = e.getData();
            if (selection.length) {
              const serviceVersion = selection[0].version;
              if (serviceVersion !== this.__resourceData["version"]) {
                osparc.store.Services.getService(this.__resourceData["key"], serviceVersion)
                  .then(serviceData => {
                    serviceData["resourceType"] = "service";
                    this.__resourceData = serviceData;
                    this.__addPages();
                  });
              }
            }
          }, this);
        });

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
        this.__getConversationsPage,
        this.__getPermissionsPage,
        this.__getPublishPage,
        this.__getCreateTemplatePage,
        this.__getCreateFunctionsPage,
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

      if (osparc.product.Utils.showComputationalActivity()) {
        this.__getActivityOverviewPopUp();
      }
      this.__getProjectFilesPopUp();

      if (selectedTabId) {
        const pageFound = tabsView.getChildren().find(page => page.tabId === selectedTabId);
        if (pageFound) {
          tabsView.setSelection([pageFound]);
        }
      }

      this.fireEvent("pagesAdded");
    },

    __fireUpdateEvent: function(resourceData, updatedData) {
      switch (resourceData["resourceType"]) {
        case "study":
          this.fireDataEvent("updateStudy", updatedData);
          break;
        case "template":
          this.fireDataEvent("updateTemplate", updatedData);
          break;
        case "tutorial":
          this.fireDataEvent("updateTutorial", updatedData);
          break;
        case "hypertool":
          this.fireDataEvent("updateHypertool", updatedData);
          break;
        case "service":
          this.fireDataEvent("updateService", updatedData);
          break;
      }
    },

    __getInfoPage: function() {
      const id = "Information";
      const title = this.tr("Overview");
      const iconSrc = "@FontAwesome5Solid/info/22";
      const page = this.__infoPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addToolbarButtons(page);

      const lazyLoadContent = () => {
        const resourceData = this.__resourceData;
        const resourceModel = this.__resourceModel;
        let infoCard = null;
        if (osparc.utils.Resources.isService(resourceData)) {
          infoCard = new osparc.info.ServiceLarge(resourceData, null, false);
          infoCard.addListener("updateService", e => {
            const updatedData = e.getData();
            this.__fireUpdateEvent(resourceData, updatedData);
          });
        } else {
          infoCard = new osparc.info.StudyLarge(resourceModel, false);
          infoCard.addListener("updateStudy", e => {
            const updatedData = e.getData();
            this.__fireUpdateEvent(resourceData, updatedData);
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
        this.__addToolbarButtons(page);

        if (resourceData["resourceType"] === "study") {
          const canBeOpened = osparc.study.Utils.canShowBillingOptions(resourceData);
          page.setEnabled(canBeOpened);
        }

        const lazyLoadContent = () => {
          const billingSettings = new osparc.study.BillingSettings(resourceData);
          billingSettings.addListener("debtPayed", () => {
            page.payDebtButton.set({
              visibility: osparc.study.Utils.isInDebt(resourceData) ? "visible" : "excluded"
            });
            const enabled = osparc.study.Utils.canBeOpened(resourceData);
            page.openButton.setEnabled(enabled);
          })
          billingSettings.addListener("closeWindow", () => {
            this.fireEvent("closeWindow");
          });
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
        this.__addToolbarButtons(page);

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
        ["app", "guided", "standalone"].includes(osparc.study.Utils.getUiMode(resourceData))
      ) {
        // there is no pipelining or don't show it
        return null;
      }

      const id = "Pipeline";
      const title = this.tr("Pipeline View");
      const iconSrc = "@FontAwesome5Solid/eye/22";
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addToolbarButtons(page);

      const studyData = this.__resourceData;
      const enabled = osparc.study.Utils.canShowPreview(studyData);
      page.setEnabled(enabled);

      const lazyLoadContent = () => {
        const resourceModel = this.__resourceModel;
        const preview = new osparc.study.StudyPreview(resourceModel);
        page.addToContent(preview);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getConversationsPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const id = "Conversations";
      const title = this.tr("Conversations");
      const iconSrc = "@FontAwesome5Solid/comments/22";
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addToolbarButtons(page);

      const lazyLoadContent = () => {
        const conversations = new osparc.study.Conversations(resourceData);
        page.addToContent(conversations);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getPermissionsPage: function() {
      const id = "Permissions";
      const title = this.tr("Sharing");
      const iconSrc = "@FontAwesome5Solid/share-alt/22";
      const page = this.__permissionsPage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addToolbarButtons(page);

      const lazyLoadContent = () => {
        const resourceData = this.__resourceData;
        let collaboratorsView = null;
        if (osparc.utils.Resources.isService(resourceData)) {
          collaboratorsView = new osparc.share.CollaboratorsService(resourceData);
          collaboratorsView.addListener("updateAccessRights", e => {
            const updatedData = e.getData();
            this.__fireUpdateEvent(resourceData, updatedData);
          }, this);
        } else {
          collaboratorsView = new osparc.share.CollaboratorsStudy(resourceData);
          if (osparc.utils.Resources.isStudy(resourceData)) {
            collaboratorsView.getChildControl("study-link").show();
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            collaboratorsView.getChildControl("template-link").show();
          } else if (osparc.utils.Resources.isTutorial(resourceData)) {
            collaboratorsView.getChildControl("template-link").show();
          }
          collaboratorsView.addListener("updateAccessRights", e => {
            const updatedData = e.getData();
            this.__fireUpdateEvent(resourceData, updatedData);
          }, this);
        }
        page.addToContent(collaboratorsView);
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
      this.__addToolbarButtons(page);

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
            this.__fireUpdateEvent(resourceData, updatedData);
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
        this.__addToolbarButtons(page);

        const lazyLoadContent = () => {
          const qualityEditor = new osparc.metadata.QualityEditor(resourceData);
          qualityEditor.addListener("updateQuality", e => {
            const updatedData = e.getData();
            this.__fireUpdateEvent(updatedData);
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
      this.__addToolbarButtons(page);

      const lazyLoadContent = () => {
        const tagManager = new osparc.form.tag.TagManager(resourceData);
        tagManager.addListener("updateTags", e => {
          const updatedData = e.getData();
          tagManager.setStudyData(updatedData);
          this.__fireUpdateEvent(resourceData, updatedData);
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
      const iconSrc = "@MaterialIcons/update/24";
      const page = this.__servicesUpdatePage = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addToolbarButtons(page);

      const studyData = this.__resourceData;
      const enabled = osparc.study.Utils.canShowServiceUpdates(studyData);
      page.setEnabled(enabled);

      const lazyLoadContent = () => {
        const servicesUpdate = new osparc.metadata.ServicesInStudyUpdate(resourceData);
        servicesUpdate.addListener("updateService", e => {
          const updatedData = e.getData();
          this.__fireUpdateEvent(resourceData, updatedData);
        });
        page.addToContent(servicesUpdate);
      }
      page.addListenerOnce("appear", lazyLoadContent, this);

      return page;
    },

    __getServicesBootOptionsPage: function() {
      const resourceData = this.__resourceData;
      if (
        osparc.utils.Resources.isService(resourceData) ||
        !osparc.data.Permissions.getInstance().canDo("study.node.bootOptions.read")
      ) {
        return null;
      }

      const id = "ServicesBootOptions";
      const title = this.tr("Boot Options");
      const iconSrc = "@FontAwesome5Solid/play-circle/22";
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      this.__addToolbarButtons(page);

      const studyData = this.__resourceData;
      const enabled = osparc.study.Utils.canShowServiceBootOptions(studyData);
      page.setEnabled(enabled);

      const lazyLoadContent = () => {
        const servicesBootOpts = new osparc.metadata.ServicesInStudyBootOpts(resourceData);
        servicesBootOpts.addListener("updateService", e => {
          const updatedData = e.getData();
          this.__fireUpdateEvent(resourceData, updatedData);
        });
        page.addToContent(servicesBootOpts);

        if (
          osparc.utils.Resources.isStudy(resourceData) ||
          osparc.utils.Resources.isTemplate(resourceData) ||
          osparc.utils.Resources.isTutorial(resourceData) ||
          osparc.utils.Resources.isHypertool(resourceData)
        ) {
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

    __getPublishPage: function() {
      if (
        !osparc.utils.Resources.isStudy(this.__resourceData) ||
        !osparc.product.Utils.showPublicProjects()
      ) {
        return null;
      }

      const canIWrite = osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"]);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (canIWrite && canCreateTemplate) {
        const id = "Publish";
        const iconSrc = "@FontAwesome5Solid/globe/22";
        const title = this.tr("Publish");
        const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);

        const studyData = this.__resourceData;
        const enabled = osparc.study.Utils.canBeDuplicated(studyData);
        page.setEnabled(enabled);

        const lazyLoadContent = () => {
          const makeItPublic = true;
          const saveAsTemplate = new osparc.study.SaveAsTemplate(this.__resourceData, makeItPublic);
          saveAsTemplate.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));

          const publishTemplateButton = saveAsTemplate.getCreateTemplateButton();
          osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(publishTemplateButton);
          const toolbar = this.self().createToolbar();
          toolbar.add(publishTemplateButton);
          page.addToHeader(toolbar);
          page.addToContent(saveAsTemplate);
        }
        page.addListenerOnce("appear", lazyLoadContent, this);

        return page;
      }
      return null;
    },

    __getCreateTemplatePage: function() {
      if (
        !osparc.utils.Resources.isStudy(this.__resourceData) ||
        !osparc.product.Utils.showTemplates()
      ) {
        return null;
      }

      const canIWrite = osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"]);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (canIWrite && canCreateTemplate) {
        const id = "Template";
        const iconSrc = "@FontAwesome5Solid/copy/22";
        const title = this.tr("Template");
        const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);

        const studyData = this.__resourceData;
        const enabled = osparc.study.Utils.canBeDuplicated(studyData);
        page.setEnabled(enabled);

        const lazyLoadContent = () => {
          const makeItPublic = false;
          const saveAsTemplate = new osparc.study.SaveAsTemplate(this.__resourceData, makeItPublic);
          saveAsTemplate.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));

          const createTemplateButton = saveAsTemplate.getCreateTemplateButton();
          osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(createTemplateButton);
          const toolbar = this.self().createToolbar();
          toolbar.add(createTemplateButton);
          page.addToHeader(toolbar);
          page.addToContent(saveAsTemplate);
        }
        page.addListenerOnce("appear", lazyLoadContent, this);

        return page;
      }
      return null;
    },

    __getCreateFunctionsPage: function() {
      if (!osparc.data.Permissions.getInstance().checkFunctionPermissions("writeFunctions")) {
        return null;
      }

      if (!osparc.utils.Resources.isStudy(this.__resourceData)) {
        return null;
      }

      if (!osparc.study.Utils.canCreateFunction(this.__resourceData["workbench"])) {
        return null;
      }

      const id = "CreateFunction";
      const iconSrc = "@MaterialIcons/functions/24";
      const title = this.tr("Create Function");
      const page = new osparc.dashboard.resources.pages.BasePage(title, iconSrc, id);
      const createFunction = new osparc.study.CreateFunction(this.__resourceData);
      const createFunctionButton = createFunction.getCreateFunctionButton();
      osparc.dashboard.resources.pages.BasePage.decorateHeaderButton(createFunctionButton);
      const toolbar = this.self().createToolbar();
      toolbar.add(createFunctionButton);
      page.addToHeader(toolbar);
      page.addToContent(createFunction);
      return page;
    },

    __getProjectFilesPopUp: function() {
      const resourceData = this.__resourceData;
      if (!osparc.utils.Resources.isService(resourceData)) {
        const title = osparc.product.Utils.resourceTypeToAlias(resourceData["resourceType"], {firstUpperCase: true}) + this.tr(" Files");
        const iconSrc = "@FontAwesome5Solid/file/22";
        const dataAccess = new qx.ui.basic.Atom().set({
          label: title + "...",
          icon: iconSrc,
          font: "text-14",
          padding: 8,
          paddingLeft: 12,
          gap: 14,
          cursor: "pointer",
        });
        dataAccess.addListener("tap", () => osparc.widget.StudyDataManager.popUpInWindow(resourceData["uuid"], null, title));
        this.addWidgetToTabs(dataAccess);

        if (resourceData["resourceType"] === "study") {
          const canShowData = osparc.study.Utils.canShowStudyData(resourceData);
          dataAccess.setEnabled(canShowData);
        }
      }
    },

    __getActivityOverviewPopUp: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isStudy(resourceData)) {
        const title = this.tr("Activity Overview...");
        const iconSrc = "@FontAwesome5Solid/tasks/22";
        const dataAccess = new qx.ui.basic.Atom().set({
          label: title,
          icon: iconSrc,
          font: "text-14",
          padding: 8,
          paddingLeft: 10,
          gap: 12, // align with the rest of the tabs
          cursor: "pointer",
        });
        dataAccess.addListener("tap", () => osparc.jobs.ActivityOverview.popUpInWindow(resourceData));
        this.addWidgetToTabs(dataAccess);
      }
    },
  }
});
