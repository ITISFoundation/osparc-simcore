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


qx.Class.define("osparc.info.MergedLarge", {
  extend: osparc.info.CardLarge,

  /**
    * @param study {osparc.data.model.Study} Study
    */
  construct: function(study) {
    this.base(arguments);

    this.setStudy(study);
    const nodes = study.getWorkbench().getNodes();
    const nodeIds = Object.keys(nodes);
    if (nodeIds.length) {
      this.setService(nodes[nodeIds[0]]);
    }

    this._attachHandlers();
  },

  events: {
    "updateStudy": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false
    },

    service: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false
    }
  },

  members: {
    _rebuildLayout: function() {
      this._removeAll();

      const title = this.__createTitle();
      const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
      this._add(titleLayout);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);
      this._add(extraInfoLayout);

      const bounds = this.getBounds();
      const offset = 30;
      const widgetWidth = bounds ? bounds.width - offset : 500 - offset;
      let thumbnailWidth = widgetWidth - 2 * osparc.info.CardLarge.PADDING;
      const maxThumbnailHeight = extraInfo.length*20;
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
        alignX: "center"
      }));
      hBox.add(extraInfoLayout);
      thumbnailWidth -= osparc.info.CardLarge.EXTRA_INFO_WIDTH;
      thumbnailWidth = Math.min(thumbnailWidth - 20, osparc.info.CardLarge.THUMBNAIL_MAX_WIDTH);
      const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
      const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
      thumbnailLayout.getLayout().set({
        alignX: "center"
      });
      hBox.add(thumbnailLayout, {
        flex: 1
      });
      this._add(hBox);

      const tags = this.__createTags();
      if (this.__canIWrite()) {
        const editInTitle = this.__createViewWithEdit(tags.getChildren()[0], this.__openTagsEditor);
        tags.addAt(editInTitle, 0);
        if (this.__canIWrite()) {
          osparc.utils.Utils.setIdToWidget(editInTitle.getChildren()[1], "editStudyEditTagsBtn");
        }
      }
      this._add(tags);

      const description = this.__createDescription();
      if (this.__canIWrite()) {
        const editInTitle = this.__createViewWithEdit(description.getChildren()[0], this.__openDescriptionEditor);
        description.addAt(editInTitle, 0);
      }
      this._add(description);

      const resources = this.__createResources();
      this._add(resources);

      const rawMetadata = this.__createRawMetadata();
      const more = new osparc.desktop.PanelView(this.tr("Raw metadata"), rawMetadata).set({
        caretSize: 14
      });
      more.setCollapsed(true);
      more.getChildControl("title").setFont("text-12");
      this._add(more, {
        flex: 1
      });
      const copy2Clip = osparc.utils.Utils.getCopyButton();
      copy2Clip.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(this.getService().serialize())), this);
      more.getChildControl("header").add(copy2Clip);
    },

    __canIWrite: function() {
      return osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights());
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view);
      if (this.__canIWrite()) {
        const editBtn = osparc.utils.Utils.getEditButton();
        editBtn.addListener("execute", () => cb.call(this), this);
        layout.add(editBtn);
      }

      return layout;
    },

    __extraInfo: function() {
      const extraInfo = [{
        label: this.tr("Author"),
        view: this.__createOwner(),
        action: null
      }, {
        label: this.tr("Creation Date"),
        view: this.__createCreationDate(),
        action: null
      }, {
        label: this.tr("Last Modified"),
        view: this.__createLastChangeDate(),
        action: null
      }, {
        label: this.tr("Access Rights"),
        view: this.__createAccessRights(),
        action: null
      }];

      if (
        osparc.product.Utils.showQuality() &&
        this.getStudy().getQuality() &&
        osparc.component.metadata.Quality.isEnabled(this.getStudy().getQuality())
      ) {
        extraInfo.push({
          label: this.tr("Quality"),
          view: this.__createQuality(),
          action: null
        });
      }

      if (osparc.product.Utils.showClassifiers()) {
        extraInfo.push({
          label: this.tr("Classifiers"),
          view: this.__createClassifiers(),
          action: null
        });
      }

      let i = 0;
      extraInfo.splice(i++, 0, {
        label: osparc.utils.Utils.capitalize(osparc.product.Utils.getStudyAlias()) + " ID",
        view: this.__createStudyId(),
        action: {
          button: osparc.utils.Utils.getCopyButton(),
          callback: this.__copyUuidToClipboard,
          ctx: this
        }
      });

      extraInfo.splice(i++, 0, {
        label: this.tr("Service ID"),
        view: this.__createNodeId(),
        action: {
          button: osparc.utils.Utils.getCopyButton(),
          callback: this.__copyNodeIdToClipboard,
          ctx: this
        }
      });

      extraInfo.splice(i++, 0, {
        label: this.tr("Service Key"),
        view: this.__createKey(),
        action: {
          button: osparc.utils.Utils.getCopyButton(),
          callback: this.__copyKeyToClipboard,
          ctx: this
        }
      });

      extraInfo.splice(i++, 0, {
        label: this.tr("Service Version"),
        view: this.__createVersion(),
        action: null
      });

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.info.StudyUtils.createExtraInfoGrid(extraInfo).set({
        width: osparc.info.CardLarge.EXTRA_INFO_WIDTH
      });

      return moreInfo;
    },

    __createTitle: function() {
      const title = osparc.info.StudyUtils.createTitle(this.getStudy()).set({
        font: "text-16"
      });
      return title;
    },

    __createStudyId: function() {
      return osparc.info.StudyUtils.createUuid(this.getStudy()).set({
        maxWidth: 200
      });
    },

    __createNodeId: function() {
      return osparc.info.ServiceUtils.createNodeId(this.getService().getNodeId()).set({
        maxWidth: 200
      });
    },

    __createKey: function() {
      return osparc.info.ServiceUtils.createKey(this.getService().getKey());
    },

    __createVersion: function() {
      return osparc.info.ServiceUtils.createVersion(this.getService().getVersion());
    },

    __createOwner: function() {
      return osparc.info.StudyUtils.createOwner(this.getStudy());
    },

    __createCreationDate: function() {
      return osparc.info.StudyUtils.createCreationDate(this.getStudy());
    },

    __createLastChangeDate: function() {
      return osparc.info.StudyUtils.createLastChangeDate(this.getStudy());
    },

    __createAccessRights: function() {
      return osparc.info.StudyUtils.createAccessRights(this.getStudy());
    },

    __createClassifiers: function() {
      return osparc.info.StudyUtils.createClassifiers(this.getStudy());
    },

    __createQuality: function() {
      return osparc.info.StudyUtils.createQuality(this.getStudy());
    },

    __createThumbnail: function(maxWidth, maxHeight = 160) {
      return osparc.info.StudyUtils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
    },

    __createTags: function() {
      return osparc.info.StudyUtils.createTags(this.getStudy());
    },

    __createDescription: function() {
      const maxHeight = 400;
      const descriptionLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Description")).set({
        font: "text-13"
      });
      descriptionLayout.add(label);

      const description = osparc.info.StudyUtils.createDescriptionMD(this.getStudy(), maxHeight);
      description.setValue(this.getStudy().getDescription());
      descriptionLayout.add(description);

      return descriptionLayout;
    },

    __createResources: function() {
      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfo();
      resourcesLayout.exclude();
      let promise = null;
      if (this.getService().getNodeId()) {
        const params = {
          url: {
            studyId: this.getStudy().getUuid(),
            nodeId: this.getService().getNodeId()
          }
        };
        promise = osparc.data.Resources.get("nodesInStudyResources", params);
      } else {
        const params = {
          url: osparc.data.Resources.getServiceUrl(
            this.getService().getKey(),
            this.getService().getVersion()
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
      container.add(new osparc.ui.basic.JsonTreeWidget(this.getService().serialize(), "serviceDescriptionSettings"));
      return container;
    },

    __openTitleEditor: function() {
      const title = this.tr("Edit Title");
      const titleEditor = new osparc.component.widget.Renamer(this.getStudy().getName(), null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__updateStudy({
          "name": newLabel
        });
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __copyUuidToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getStudy().getUuid());
    },

    __copyNodeIdToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getService().getNodeId());
    },

    __copyKeyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getService().getKey());
    },

    __openTagsEditor: function() {
      const tagManager = new osparc.component.form.tag.TagManager(this.getStudy().serialize());
      const win = osparc.component.form.tag.TagManager.popUpInWindow(tagManager);
      tagManager.addListener("updateTags", e => {
        win.close();
        const updatedData = e.getData();
        this.getStudy().setTags(updatedData["tags"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const oldThumbnail = this.getStudy().getThumbnail();
      const suggestions = osparc.component.editor.ThumbnailSuggestions.extractThumbanilSuggestions(this.getStudy());
      const thumbnailEditor = new osparc.component.editor.ThumbnailEditor(oldThumbnail, suggestions);
      const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, suggestions.length > 2 ? 500 : 350, suggestions.length ? 280 : 115);
      thumbnailEditor.addListener("updateThumbnail", e => {
        win.close();
        const validUrl = e.getData();
        this.__updateStudy({
          "thumbnail": validUrl
        });
      }, this);
      thumbnailEditor.addListener("cancel", () => win.close());
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.component.editor.TextEditor(this.getStudy().getDescription());
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__updateStudy({
          "description": newDescription
        });
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __updateStudy: function(params) {
      this.getStudy().updateStudy(params)
        .then(studyData => {
          this.fireDataEvent("updateStudy", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", studyData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    }
  }
});
