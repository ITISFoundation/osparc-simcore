/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Tag manager server to manage one resource's related tags.
 */
qx.Class.define("osparc.form.tag.TagManager", {
  extend: qx.ui.core.Widget,

  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__selectedTags = new qx.data.Array();
    this.__renderLayout();
    this.__attachEventHandlers();

    this.setStudyData(studyData);
  },

  events: {
    "updateTags": "qx.event.type.Data",
    "changeSelected": "qx.event.type.Data"
  },

  properties: {
    liveUpdate: {
      check: "Boolean",
      event: "changeLiveUpdate",
      init: false
    }
  },

  statics: {
    popUpInWindow: function(tagManager, title) {
      if (!title) {
        title = qx.locale.Manager.tr("Apply Tags");
      }
      return osparc.ui.window.Window.popUpInWindow(tagManager, title, 280, null).set({
        allowMinimize: false,
        allowMaximize: false,
        showMinimize: false,
        showMaximize: false,
        clickAwayClose: true,
        movable: true,
        resizable: true,
        showClose: true
      });
    }
  },

  members: {
    __studyData: null,
    __resourceId: null,
    __selectedTags: null,
    __tagsContainer: null,
    __addTagButton: null,

    __renderLayout: function() {
      const filter = new osparc.filter.TextFilter("name", "studyBrowserTagManager").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      this._add(filter);

      const tagsContainer = this.__tagsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      this._add(tagsContainer, {
        flex: 1
      });

      const addTagButton = this.__addTagButton = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        label: this.tr("New Tag"),
        icon: "@FontAwesome5Solid/plus/14",
        alignX: "center",
        allowGrowX: false
      });
      addTagButton.addListener("execute", () => {
        const newItem = new osparc.form.tag.TagItem().set({
          mode: osparc.form.tag.TagItem.modes.EDIT
        });
        newItem.addListener("tagSaved", () => this.__repopulateTags(), this);
        newItem.addListener("cancelNewTag", e => tagsContainer.remove(e.getTarget()), this);
        newItem.addListener("deleteTag", e => tagsContainer.remove(e.getTarget()), this);
        tagsContainer.add(newItem);
        this.__repopulateTags();
      });
      this._add(addTagButton);

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));
      const saveButton = new osparc.ui.form.FetchButton(this.tr("Save"));
      saveButton.set({
        appearance: "strong-button"
      });
      osparc.utils.Utils.setIdToWidget(saveButton, "saveTagsBtn");
      saveButton.addListener("execute", () => this.__save(saveButton), this);
      buttons.add(saveButton);
      this.bind("liveUpdate", buttons, "visibility", {
        converter: value => value ? "excluded" : "visible"
      });
      this._add(buttons);
    },

    setStudyData: function(studyData) {
      this.__studyData = studyData;
      this.__resourceId = studyData["uuid"];
      this.__selectedTags.removeAll();
      this.__selectedTags.append(studyData["tags"]);
      this.__repopulateTags();
    },

    __repopulateTags: function() {
      this.__tagsContainer.removeAll();
      const tags = osparc.store.Tags.getInstance().getTags();
      tags.forEach(tag => this.__tagsContainer.add(this.__tagButton(tag)));
    },

    __tagButton: function(tag) {
      const tagId = tag.getTagId();
      const tagButton = new osparc.form.tag.TagToggleButton(tag, this.__selectedTags.includes(tagId));
      tagButton.addListener("changeValue", evt => {
        const selected = evt.getData();
        if (this.isLiveUpdate()) {
          tagButton.setFetching(true);
          if (selected) {
            this.__saveAddTag(tagId, tagButton);
          } else {
            this.__saveRemoveTag(tagId, tagButton);
          }
        } else if (selected) {
          this.__selectedTags.push(tagId);
        } else {
          this.__selectedTags.remove(tagId);
        }
      }, this);
      tagButton.subscribeToFilterGroup("studyBrowserTagManager");
      return tagButton;
    },

    __getAddTagPromise: function(tagId) {
      const params = {
        url: {
          tagId,
          studyId: this.__resourceId
        }
      };
      return osparc.data.Resources.fetch("studies", "addTag", params);
    },

    __getRemoveTagPromise: function(tagId) {
      const params = {
        url: {
          tagId,
          studyId: this.__resourceId
        }
      };
      return osparc.data.Resources.fetch("studies", "removeTag", params);
    },

    __saveAddTag: function(tagId, tagButton) {
      this.__getAddTagPromise(tagId)
        .then(() => this.__selectedTags.push(tagId))
        .catch(err => {
          console.error(err);
          tagButton.setValue(false);
        })
        .finally(() => tagButton.setFetching(false));
    },

    __saveRemoveTag: function(tagId, tagButton) {
      this.__getRemoveTagPromise(tagId)
        .then(() => this.__selectedTags.remove(tagId))
        .catch(err => {
          console.error(err);
          tagButton.setValue(true);
        })
        .finally(() => tagButton.setFetching(false));
    },

    __save: async function(saveButton) {
      saveButton.setFetching(true);

      // call them sequentially
      let updatedStudy = null;
      for (let i=0; i<this.__selectedTags.length; i++) {
        const tagId = this.__selectedTags.getItem(i);
        if (!this.__studyData["tags"].includes(tagId)) {
          updatedStudy = await this.__getAddTagPromise(tagId)
            .then(updatedData => updatedData);
        }
      }
      for (let i=0; i<this.__studyData["tags"].length; i++) {
        const tagId = this.__studyData["tags"][i];
        if (!this.__selectedTags.includes(tagId)) {
          updatedStudy = await this.__getRemoveTagPromise(tagId)
            .then(updatedData => updatedData);
        }
      }

      saveButton.setFetching(false);
      if (updatedStudy) {
        this.fireDataEvent("updateTags", updatedStudy);
      }
    },

    __attachEventHandlers: function() {
      this.__selectedTags.addListener("change", evt => {
        this.fireDataEvent("changeSelected", {
          ...evt.getData(),
          selected: this.__selectedTags.toArray()
        });
      }, this);
    }
  }
});
