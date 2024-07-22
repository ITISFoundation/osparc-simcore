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
    * @param serviceData {Object} Serialized Service Object
    * @param instance {Object} instance related data
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(serviceData, instance = null, openOptions = true) {
    this.base(arguments);

    this.setService(serviceData);

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

  members: {
    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));

      const deprecated = this.__createDeprecated();
      if (deprecated) {
        vBox.add(deprecated);
      }

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

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
        alignX: "center"
      }));
      hBox.add(extraInfoLayout);
      hBox.add(thumbnailLayout, {
        flex: 1
      });
      vBox.add(hBox);

      const description = this.__createDescription();
      const editInTitle = this.__createViewWithEdit(description.getChildren()[0], this.__openDescriptionEditor);
      description.addAt(editInTitle, 0);
      vBox.add(description);

      const resources = this.__createResources();
      vBox.add(resources);

      const copyMetadataButton = new qx.ui.form.Button(this.tr("Copy Raw metadata"), "@FontAwesome5Solid/copy/12").set({
        allowGrowX: false
      });
      copyMetadataButton.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(this.getService())), this);
      vBox.add(copyMetadataButton);

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
      }, {
        label: this.tr("VERSION"),
        view: this.__createVersion(),
        action: null
      }, {
        label: this.tr("VERSION DISPLAY"),
        view: this.__createVersionDisplay(),
        action: {
          button: osparc.utils.Utils.getEditButton(),
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
          button: osparc.utils.Utils.getEditButton(),
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
            button: osparc.utils.Utils.getEditButton(),
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
            button: osparc.utils.Utils.getEditButton(),
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

    __createVersion: function() {
      return osparc.info.ServiceUtils.createVersion(this.getService()["version"]);
    },

    __createVersionDisplay: function() {
      const versionDisplayLabel = osparc.info.ServiceUtils.createVersionDisplay(this.getService()["key"], this.getService()["version"]);
      if (versionDisplayLabel.getValue() || osparc.service.Utils.canIWrite(this.getService()["accessRights"])) {
        // show it if it has a value or if the user can write (useful when it is still empty)
        return versionDisplayLabel;
      }
      return null;
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
      return osparc.info.ServiceUtils.createThumbnail(this.getService(), maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.info.ServiceUtils.createDescription(this.getService(), maxHeight);
    },

    __createResources: function() {
      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfo();
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
        const params = {
          url: osparc.data.Resources.getServiceUrl(
            this.getService()["key"],
            this.getService()["version"]
          )
        };
        promise = osparc.data.Resources.get("serviceResources", params);
      }
      promise
        .then(serviceResources => {
          resourcesLayout.show();
          osparc.info.ServiceUtils.resourcesToResourcesInfo(resourcesLayout, serviceResources);
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

    __copyNodeIdToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getNodeId());
    },

    __copyKeyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getService()["key"]);
    },

    __openVersionDisplayEditor: function() {
      const title = this.tr("Edit Version Display");
      const oldVersionDisplay = this.getService()["versionDisplay"] ? this.getService()["versionDisplay"] : "";
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
      const serviceDataCopy = osparc.utils.Utils.deepCloneObject(this.getService());
      osparc.info.ServiceUtils.patchServiceData(serviceDataCopy, key, value)
        .then(() => {
          this.setService(serviceDataCopy);
          this.fireDataEvent("updateService", this.getService());
        })
        .catch(err => {
          console.error(err);
          const msg = err.message || this.tr("There was an error while updating the information.");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
    }
  }
});
