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
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Serialized Service Object
    * @param instance {Object} instance related data
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(serviceData, instance = null, openOptions = true) {
    this.base(arguments);

    this.set({
      minHeight: 350,
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.setService(serviceData);

    if (instance) {
      if ("nodeId" in instance) {
        this.setNodeId(instance["nodeId"]);
      }
      if ("label" in instance) {
        this.setInstanceLabel(instance["label"]);
      }
      if ("study" in instance) {
        this.setStudy(instance["study"]);
      }
    }

    if (openOptions !== undefined) {
      this.setOpenOptions(openOptions);
    }

    this.addListenerOnce("appear", () => this.__rebuildLayout(), this);
    this.addListener("resize", () => this.__rebuildLayout(), this);
  },

  events: {
    "openAccessRights": "qx.event.type.Event",
    "openClassifiers": "qx.event.type.Event",
    "openQuality": "qx.event.type.Event",
    "updateService": "qx.event.type.Data"
  },

  properties: {
    service: {
      check: "Object",
      init: null,
      nullable: false,
      apply: "__rebuildLayout"
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

    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: true
    },

    openOptions: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 300,
    THUMBNAIL_MIN_WIDTH: 140,
    THUMBNAIL_MAX_WIDTH: 280
  },

  members: {
    __isOwner: function() {
      return osparc.utils.Services.isOwner(this.getService());
    },

    __rebuildLayout: function() {
      this._removeAll();

      const deprecated = this.__createDeprecated();
      if (deprecated) {
        this._add(deprecated);
      }

      const title = this.__createTitle();
      const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
      this._add(titleLayout);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);

      const bounds = this.getBounds();
      const offset = 30;
      const maxThumbnailHeight = extraInfo.length*20;
      let widgetWidth = bounds ? bounds.width - offset : 500 - offset;
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING - this.self().EXTRA_INFO_WIDTH;
      thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
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
      this._add(hBox);

      const description = this.__createDescription();
      const editInTitle = this.__createViewWithEdit(description.getChildren()[0], this.__openDescriptionEditor);
      description.addAt(editInTitle, 0);
      this._add(description);

      const resources = this.__createResources();
      this._add(resources);

      const rawMetadata = this.__createRawMetadata();
      const more = new osparc.desktop.PanelView(this.tr("Raw metadata"), rawMetadata).set({
        caretSize: 14
      });
      more.setCollapsed(true);
      more.getChildControl("title").setFont("title-12");
      this._add(more, {
        flex: 1
      });
      const copy2Clip = osparc.utils.Utils.getCopyButton();
      copy2Clip.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(this.getService())), this);
      more.getChildControl("header").add(copy2Clip);
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view);
      if (this.__isOwner()) {
        const editBtn = osparc.utils.Utils.getEditButton();
        editBtn.addListener("execute", () => cb.call(this), this);
        layout.add(editBtn);
      }

      return layout;
    },

    __createDeprecated: function() {
      const isDeprecated = osparc.utils.Services.isDeprecated(this.getService());
      if (isDeprecated) {
        return osparc.utils.StatusUI.createServiceDeprecatedChip();
      }
      const isRetired = osparc.utils.Services.isRetired(this.getService());
      if (isRetired) {
        return osparc.utils.StatusUI.createServiceRetiredChip();
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
        font: "title-16"
      });
      return title;
    },

    __extraInfo: function() {
      const extraInfo = [{
        label: this.tr("Version"),
        view: this.__createVersion(),
        action: null
      }, {
        label: this.tr("Contact"),
        view: this.__createContact(),
        action: null
      }, {
        label: this.tr("Authors"),
        view: this.__createAuthors(),
        action: null
      }, {
        label: this.tr("Access Rights"),
        view: this.__createAccessRights(),
        action: {
          button: osparc.utils.Utils.getViewButton(),
          callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
          ctx: this
        }
      }];

      if (this.getService()["classifiers"]) {
        extraInfo.push({
          label: this.tr("Classifiers"),
          view: this.__createClassifiers(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.isOpenOptions() ? this.__openClassifiers : "openClassifiers",
            ctx: this
          }
        });
      }

      if (this.getService()["quality"] && osparc.component.metadata.Quality.isEnabled(this.getService()["quality"])) {
        extraInfo.push({
          label: this.tr("Quality"),
          view: this.__createQuality(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.isOpenOptions() ? this.__openQuality : "openQuality",
            ctx: this
          }
        });
      }

      if (osparc.data.Permissions.getInstance().isTester()) {
        if (this.getNodeId()) {
          extraInfo.splice(0, 0, {
            label: this.tr("Service ID"),
            view: this.__createNodeId(),
            action: {
              button: osparc.utils.Utils.getCopyButton(),
              callback: this.__copyNodeIdToClipboard,
              ctx: this
            }
          });
        }

        extraInfo.splice(1, 0, {
          label: this.tr("Key"),
          view: this.__createKey(),
          action: {
            button: osparc.utils.Utils.getCopyButton(),
            callback: this.__copyKeyToClipboard,
            ctx: this
          }
        });
      }

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.info.ServiceUtils.createExtraInfo(extraInfo).set({
        width: this.self().EXTRA_INFO_WIDTH
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
            studyId: this.getStudy().getUuid(),
            nodeId: this.getNodeId()
          }
        };
        promise = osparc.data.Resources.fetch("nodesInStudyResources", "getResources", params);
      } else {
        const params = {
          url: osparc.data.Resources.getServiceUrl(
            this.getService()["key"],
            this.getService()["version"]
          )
        };
        promise = osparc.data.Resources.fetch("serviceResources", "getResources", params);
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
      const titleEditor = new osparc.component.widget.Renamer(this.getService()["name"], null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__updateService({
          "name": newLabel
        });
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

    __openAccessRights: function() {
      const permissionsView = osparc.info.ServiceUtils.openAccessRights(this.getService());
      permissionsView.addListener("updateService", e => {
        const updatedServiceData = e.getData();
        this.setService(updatedServiceData);
        this.fireDataEvent("updateService", updatedServiceData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (this.__isOwner()) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(this.getService());
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedServiceData = e.getData();
          this.setService(updatedServiceData);
          this.fireDataEvent("updateService", updatedServiceData);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(this.getService());
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
      const thumbnailEditor = new osparc.component.editor.ThumbnailEditor(this.getService()["thumbnail"]);
      const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, 300, 120);
      thumbnailEditor.addListener("updateThumbnail", e => {
        win.close();
        const validUrl = e.getData();
        this.__updateService({
          "thumbnail": validUrl
        });
      }, this);
      thumbnailEditor.addListener("cancel", () => win.close());
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.component.editor.TextEditor(this.getService()["description"]);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__updateService({
          "description": newDescription
        });
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __updateService: function(data) {
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this.getService()["key"],
          this.getService()["version"]
        ),
        data: data
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.setService(serviceData);
          this.fireDataEvent("updateService", serviceData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    }
  }
});
