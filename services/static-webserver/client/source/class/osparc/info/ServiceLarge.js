/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.ServiceLarge", {
  extend: osparc.info.CardLarge,

  /**
    * @param metadata {Object} Serialized Service Object
    * @param instance {Object} instance related data
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(metadata, instance = null, openOptions = true) {
    this.base(arguments);

    this.setService(metadata);

    if (instance) {
      if ("nodeId" in instance) {
        this.setNodeId(instance["nodeId"]);
      }
      if ("label" in instance) {
        this.setInstanceLabel(instance["label"]);
      }
      if ("studyId" in instance) {
        this.setStudyId(instance["studyId"]);
      }
    }

    if (openOptions !== undefined) {
      this.setOpenOptions(openOptions);
    }

    this._attachHandlers();
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  properties: {
    service: {
      check: "Object",
      init: null,
      nullable: false,
      apply: "_rebuildLayout"
    },

    nodeId: {
      check: "String",
      init: null,
      nullable: true
    },

    instanceLabel: {
      check: "String",
      init: null,
      nullable: true
    },

    studyId: {
      check: "String",
      init: null,
      nullable: true
    }
  },

  statics: {
    popUpInWindow: function(serviceLarge) {
      const metadata = serviceLarge.getService();
      const versionDisplay = osparc.service.Utils.extractVersionDisplay(metadata);
      const title = `${metadata["name"]} ${versionDisplay}`;
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(serviceLarge, title, width, height).set({
        maxHeight: height
      });
    },
  },

  members: {
    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));

      const deprecated = this.__createDeprecated();
      if (deprecated) {
        vBox.add(deprecated);
      }

      const description = this.__createDescription();
      const editInTitle = this.__createViewWithEdit(description.getChildren()[0], this.__openDescriptionEditor);
      description.addAt(editInTitle, 0);

      const copyMetadataButton = new qx.ui.form.Button(this.tr("Copy Raw metadata"), "@FontAwesome5Solid/copy/12").set({
        allowGrowX: false
      });
      copyMetadataButton.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(this.getService())), this);

      if (
        this.getService()["descriptionUi"] &&
        !osparc.service.Utils.canIWrite(this.getService()["accessRights"]) &&
        description.getChildren().length > 1
      ) {
        // Show also the copy Id buttons too
        const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
        if (this.getNodeId()) {
          const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
          const copyStudyIdButton = new qx.ui.form.Button(this.tr(`Copy ${studyAlias} Id`), "@FontAwesome5Solid/copy/12").set({
            toolTipText: qx.locale.Manager.tr("Copy to clipboard"),
          });
          copyStudyIdButton.addListener("execute", this.__copyStudyIdToClipboard, this);
          buttonsLayout.add(copyStudyIdButton);
          vBox.add(buttonsLayout);

          const copyNodeIdButton = new qx.ui.form.Button(this.tr("Copy Service Id"), "@FontAwesome5Solid/copy/12").set({
            toolTipText: qx.locale.Manager.tr("Copy to clipboard"),
          });
          copyNodeIdButton.addListener("execute", this.__copyNodeIdToClipboard, this);
          buttonsLayout.add(copyNodeIdButton);
          vBox.add(buttonsLayout);
        }
        // Also copyMetadataButton if tester
        if (osparc.data.Permissions.getInstance().isTester()) {
          buttonsLayout.add(copyMetadataButton);
          vBox.add(buttonsLayout);
        }
        // Show description only
        vBox.add(description.getChildren()[1]);
      } else {
        const title = this.__createTitle();
        const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
        vBox.add(titleLayout);

        const extraInfo = this.__extraInfo();
        const extraInfoLayout = this.__createExtraInfo(extraInfo);
        const bounds = this.getBounds();
        const offset = 30;
        const maxThumbnailHeight = extraInfo.length*20;
        let widgetWidth = bounds ? bounds.width - offset : 500 - offset;
        let thumbnailWidth = widgetWidth - 2 * osparc.info.CardLarge.PADDING - osparc.info.CardLarge.EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth - 20, osparc.info.CardLarge.THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
        thumbnailLayout.getLayout().set({
          alignX: "center"
        });
        const infoAndThumbnail = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center"
        }));
        infoAndThumbnail.add(extraInfoLayout);
        infoAndThumbnail.add(thumbnailLayout, {
          flex: 1
        });
        vBox.add(infoAndThumbnail);

        if (osparc.service.Utils.canIWrite(this.getService()["accessRights"])) {
          const descriptionUi = this.__createDescriptionUi();
          if (descriptionUi) {
            vBox.add(descriptionUi);
          }
        }
        vBox.add(description);

        if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
          const resources = this.__createResources();
          if (resources) {
            vBox.add(resources);
          }
        }
        vBox.add(copyMetadataButton);
      }

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(vBox);
      this._add(scrollContainer, {
        flex: 1
      });
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view);
      if (osparc.service.Utils.canIWrite(this.getService()["accessRights"])) {
        const editBtn = osparc.utils.Utils.getEditButton();
        editBtn.addListener("execute", () => cb.call(this), this);
        layout.add(editBtn);
      }

      return layout;
    },

    __createDeprecated: function() {
      const isDeprecated = osparc.service.Utils.isDeprecated(this.getService());
      const isRetired = osparc.service.Utils.isRetired(this.getService());
      if (isDeprecated) {
        return osparc.service.StatusUI.createServiceDeprecatedChip();
      } else if (isRetired) {
        return osparc.service.StatusUI.createServiceRetiredChip();
      }
      return null;
    },

    __createTitle: function() {
      const serviceName = this.getService()["name"];
      let text = "";
      if (this.getInstanceLabel()) {
        text = `${this.getInstanceLabel()} [${serviceName}]`;
      } else {
        text = serviceName;
      }
      const title = osparc.info.ServiceUtils.createTitle(text).set({
        font: "text-14"
      });
      return title;
    },

    __extraInfo: function() {
      const extraInfo = [];

      if (this.getNodeId()) {
        extraInfo.push({
          label: this.tr("SERVICE ID"),
          view: this.__createNodeId(),
          action: {
            button: osparc.utils.Utils.getCopyButton(),
            callback: this.__copyNodeIdToClipboard,
            ctx: this
          }
        });
      }

      extraInfo.push({
        label: this.tr("KEY"),
        view: this.__createKey(),
        action: {
          button: osparc.utils.Utils.getCopyButton(),
          callback: this.__copyKeyToClipboard,
          ctx: this
        }
      });

      if (osparc.data.Permissions.getInstance().isTester() || osparc.service.Utils.canIWrite(this.getService()["accessRights"])) {
        extraInfo.push({
          label: this.tr("INTEGRATION VERSION"),
          view: this.__createIntegrationVersion(),
          action: null
        });
      }

      extraInfo.push({
        label: this.tr("VERSION"),
        view: this.__createDisplayVersion(),
        action: {
          button: osparc.service.Utils.canIWrite(this.getService()["accessRights"]) ? osparc.utils.Utils.getEditButton() : null,
          callback: this.__openVersionDisplayEditor,
          ctx: this
        }
      }, {
        label: this.tr("RELEASE DATE"),
        view: this.__createReleasedDate(),
        action: null
      }, {
        label: this.tr("CONTACT"),
        view: this.__createContact(),
        action: null
      }, {
        label: this.tr("AUTHORS"),
        view: this.__createAuthors(),
        action: null
      }, {
        label: this.tr("ACCESS RIGHTS"),
        view: this.__createAccessRights(),
        action: {
          button: osparc.service.Utils.canIWrite(this.getService()["accessRights"]) ? osparc.utils.Utils.getEditButton() : null,
          callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
          ctx: this
        }
      });

      if (
        osparc.product.Utils.showClassifiers() &&
        this.getService()["classifiers"]
      ) {
        extraInfo.push({
          label: this.tr("CLASSIFIERS"),
          view: this.__createClassifiers(),
          action: {
            button: osparc.service.Utils.canIWrite(this.getService()["accessRights"]) ? osparc.utils.Utils.getEditButton() : null,
            callback: this.isOpenOptions() ? this.__openClassifiers : "openClassifiers",
            ctx: this
          }
        });
      }

      if (
        osparc.product.Utils.showQuality() &&
        this.getService()["quality"] &&
        osparc.metadata.Quality.isEnabled(this.getService()["quality"])
      ) {
        extraInfo.push({
          label: this.tr("QUALITY"),
          view: this.__createQuality(),
          action: {
            button: osparc.service.Utils.canIWrite(this.getService()["accessRights"]) ? osparc.utils.Utils.getEditButton() : null,
            callback: this.isOpenOptions() ? this.__openQuality : "openQuality",
            ctx: this
          }
        });
      }

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.info.Utils.extraInfosToGrid(extraInfo).set({
        width: osparc.info.CardLarge.EXTRA_INFO_WIDTH
      });
      return moreInfo;
    },

    __createNodeId: function() {
      return osparc.info.ServiceUtils.createNodeId(this.getNodeId());
    },

    __createKey: function() {
      return osparc.info.ServiceUtils.createKey(this.getService()["key"]);
    },

    __createIntegrationVersion: function() {
      return osparc.info.ServiceUtils.createVersion(this.getService()["version"]);
    },

    __createDisplayVersion: function() {
      return osparc.info.ServiceUtils.createVersionDisplay(this.getService()["key"], this.getService()["version"]);
    },

    __createReleasedDate: function() {
      return osparc.info.ServiceUtils.createReleasedDate(this.getService()["key"], this.getService()["version"]);
    },

    __createContact: function() {
      return osparc.info.ServiceUtils.createContact(this.getService());
    },

    __createAuthors: function() {
      return osparc.info.ServiceUtils.createAuthors(this.getService());
    },

    __createAccessRights: function() {
      return osparc.info.ServiceUtils.createAccessRights(this.getService());
    },

    __createClassifiers: function() {
      return osparc.info.ServiceUtils.createClassifiers(this.getService());
    },

    __createQuality: function() {
      return osparc.info.ServiceUtils.createQuality(this.getService());
    },

    __createThumbnail: function(maxWidth, maxHeight = 160) {
      const serviceData = this.getService();
      const thumbnail = osparc.info.Utils.createThumbnail(maxWidth, maxHeight);
      if (serviceData["thumbnail"]) {
        thumbnail.set({
          source: serviceData["thumbnail"]
        });
      } else {
        const noThumbnail = "osparc/no_photography_black_24dp.svg";
        thumbnail.set({
          source: noThumbnail
        });
        thumbnail.getChildControl("image").set({
          minWidth: Math.max(120, maxWidth),
          minHeight: Math.max(139, maxHeight)
        });
      }
      return thumbnail;
    },

    __createDescriptionUi: function() {
      const cbAutoPorts = new qx.ui.form.CheckBox().set({
        label: this.tr("Show Description only"),
        toolTipText: this.tr("From all the metadata shown in this view,\nonly the Description will be shown to Users."),
        iconPosition: "right",
      });
      cbAutoPorts.setValue(Boolean(this.getService()["descriptionUi"]));
      cbAutoPorts.addListener("changeValue", e => {
        this.__patchService("descriptionUi", e.getData());
      });
      return cbAutoPorts;
    },

    __createDescription: function() {
      return osparc.info.ServiceUtils.createDescription(this.getService());
    },

    __createResources: function() {
      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfoCompact();
      resourcesLayout.exclude();
      let promise = null;
      if (this.getNodeId()) {
        const params = {
          url: {
            studyId: this.getStudyId(),
            nodeId: this.getNodeId()
          }
        };
        promise = osparc.data.Resources.get("nodesInStudyResources", params);
      } else {
        promise = osparc.store.Services.getResources(this.getService()["key"], this.getService()["version"])
      }
      promise
        .then(serviceResources => {
          resourcesLayout.show();
          osparc.info.ServiceUtils.resourcesToResourcesInfoCompact(resourcesLayout, serviceResources);
        })
        .catch(err => console.error(err));
      return resourcesLayout;
    },

    __createRawMetadata: function() {
      const container = new qx.ui.container.Scroll();
      container.add(new osparc.ui.basic.JsonTreeWidget(this.getService(), "serviceDescriptionSettings"));
      return container;
    },

    __openTitleEditor: function() {
      const title = this.tr("Edit Title");
      const titleEditor = new osparc.widget.Renamer(this.getService()["name"], null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__patchService("name", newLabel);
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __copyStudyIdToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getStudyId());
    },

    __copyNodeIdToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getNodeId());
    },

    __copyKeyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getService()["key"]);
    },

    __openVersionDisplayEditor: function() {
      const title = this.tr("Edit Version Display");
      const oldVersionDisplay = osparc.service.Utils.extractVersionDisplay(this.getService());
      const versionDisplayEditor = new osparc.widget.Renamer(oldVersionDisplay, null, title);
      versionDisplayEditor.addListener("labelChanged", e => {
        versionDisplayEditor.close();
        const newVersionDisplay = e.getData()["newLabel"];
        this.__patchService("versionDisplay", newVersionDisplay);
      }, this);
      versionDisplayEditor.center();
      versionDisplayEditor.open();
    },

    __openAccessRights: function() {
      const permissionsView = osparc.info.ServiceUtils.openAccessRights(this.getService());
      permissionsView.addListener("updateAccessRights", e => {
        const updatedServiceData = e.getData();
        this.setService(updatedServiceData);
        this.fireDataEvent("updateService", updatedServiceData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (osparc.service.Utils.canIWrite(this.getService()["accessRights"])) {
        classifiers = new osparc.metadata.ClassifiersEditor(this.getService());
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedServiceData = e.getData();
          this.setService(updatedServiceData);
          this.fireDataEvent("updateService", updatedServiceData);
        }, this);
      } else {
        classifiers = new osparc.metadata.ClassifiersViewer(this.getService());
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
      }
    },

    __openQuality: function() {
      const qualityEditor = osparc.info.ServiceUtils.openQuality(this.getService());
      qualityEditor.addListener("updateQuality", e => {
        const updatedServiceData = e.getData();
        this.setService(updatedServiceData);
        this.fireDataEvent("updateService", updatedServiceData);
      });
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const thumbnailEditor = new osparc.editor.ThumbnailEditor(this.getService()["thumbnail"]);
      const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, 300, 115);
      thumbnailEditor.addListener("updateThumbnail", e => {
        win.close();
        const validUrl = e.getData();
        this.__patchService("thumbnail", validUrl);
      }, this);
      thumbnailEditor.addListener("cancel", () => win.close());
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.editor.MarkdownEditor(this.getService()["description"]);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__patchService("description", newDescription);
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __patchService: function(key, value) {
      this.setEnabled(false);
      const serviceDataCopy = osparc.utils.Utils.deepCloneObject(this.getService());
      osparc.store.Services.patchServiceData(serviceDataCopy, key, value)
        .then(() => {
          this.setService(serviceDataCopy);
          this.fireDataEvent("updateService", this.getService());
        })
        .catch(err => {
          console.error(err);
          const msg = err.message || this.tr("There was an error while updating the information.");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        })
        .finally(() => this.setEnabled(true));
    }
  }
});
